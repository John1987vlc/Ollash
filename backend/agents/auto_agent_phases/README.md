# auto_agent_phases — 10-Phase AutoAgent Pipeline

Sequential pipeline for project generation optimized for 4B models (qwen3.5:4b).

## Pipeline

| # | Phase | LLM? | Description |
|---|-------|------|-------------|
| 1 | `ProjectScanPhase` | No | Detect project type/stack via keywords; ingest up to 50 existing files |
| 2 | `BlueprintPhase` | Yes (1 call) | Generate full project blueprint as Pydantic-validated JSON (max 20 files) |
| 3 | `ScaffoldPhase` | No | Create directories and write language-specific stub files |
| 4 | `CodeFillPhase` | Yes (1/file) | Generate file content in priority order with language-specific prompts, syntax validation + 1 retry |
| 4b | `CrossFileValidationPhase` | No | **10 zero-LLM contract checks:** HTML↔JS ids (P1), CSS classes (P2), Python imports (P3), JS fetch vs routes (P4), form fields vs Pydantic models (P5), duplicate window.* exports (P6), Python constructor arity (P7), C# class/interface refs (P8), DB-seeded string case (P9), **HTML inline-script vs JS exports (P10)**, **JS cross-global call validation (P11, large models)** |
| 5 | `PatchPhase` | Yes (optional) | Static analysis (ruff/tsc/go vet/…) + DB connection bug detection + **3-round** improvement loop; `id_mismatch`/`window_function_mismatch` errors bypass SEARCH/REPLACE and go directly to full-file regeneration with cross-file context injected; threshold raised to 12 000 chars; rounds 1+ cycle through 6 focused review aspects |
| 6b | `SeniorReviewPhase` | Yes (1–4 calls) | Large models: 2-cycle full review + CodePatcher repair. **Small models**: 2-cycle compact review with actual file content (≤6 files / ≤20K chars). |
| 6 | `InfraPhase` | Yes (1–2 calls) | requirements.txt, Dockerfile, .gitignore, package.json |
| 7 | `TestRunPhase` | Yes (optional) | Run pytest, patch up to 3 failures per iteration, max 3 iterations. **Skipped for ≤8B models.** |
| 8 | `FinishPhase` | No | Write `OLLASH.md` + `.ollash/metrics.json`, fire `project_complete` event |

## Token Budget

Each LLM call stays within ~4K tokens:
- System prompt: ~800 tokens
- User context: ~2200 tokens
- Generation: ~2000 tokens

## Key Files

| File | Purpose |
|------|---------|
| `phase_context.py` | `PhaseContext` dataclass — shared mutable state |
| `base_phase.py` | `BasePhase(ABC)` — `run()`, `_llm_call()`, `_llm_json()`, `_write_file()` |
| `blueprint_models.py` | Pydantic models (`FilePlanModel`, `BlueprintOutput`) — imported only by BlueprintPhase |
| `project_scan_phase.py` | Phase 1 |
| `blueprint_phase.py` | Phase 2 |
| `scaffold_phase.py` | Phase 3 |
| `code_fill_phase.py` | Phase 4 |
| `cross_file_validation_phase.py` | Phase 4b |
| `patch_phase.py` | Phase 5 |
| `infra_phase.py` | Phase 6 |
| `test_run_phase.py` | Phase 7 |
| `finish_phase.py` | Phase 8 |

## PhaseContext

```python
@dataclass
class PhaseContext:
    # Immutable inputs
    project_name: str
    project_description: str
    project_root: Path
    llm_manager: IModelProvider
    file_manager: FileManager
    event_publisher: EventPublisher
    logger: AgentLogger

    # Mutable state (grows through pipeline)
    project_type: str = "unknown"
    tech_stack: List[str] = field(default_factory=list)
    blueprint: List[FilePlan] = field(default_factory=list)
    generated_files: Dict[str, str] = field(default_factory=dict)
    cross_file_errors: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
```

## Model Tiers

- `ctx.is_small()` — True if model ≤8B → skips TestRunPhase; runs compact SeniorReviewPhase
- `ctx.is_micro()` — True if model ≤2B → uses shorter prompts

## Pipeline Improvements (Sprint 10)

11 targeted fixes identified from a real test run (FastAPI + SQLite + HTML/CSS barbershop booking app on `qwen3.5:4b`):

### BlueprintPhase improvements

| ID | Method | What it does |
|----|--------|-------------|
| **M2** | `_dynamic_max_files()` | `python_app`, `api`, `web_app` now return 7 files on small models (was hardcoded 5) |
| **M3** | `_ensure_mandatory_files()` | Auto-injects `static/style.css` post-LLM when CSS is in the stack, HTML is planned, but no CSS file was blueprinted |
| **M4** | `_build_mandatory_hints()` | Large models only: appends `MANDATORY PATTERNS` hint to blueprint prompt for FastAPI+HTML projects (StaticFiles mount, startup event, list endpoint) |

### CodeFillPhase improvements

| ID | Method | What it does |
|----|--------|-------------|
| **M7** | `_is_fastapi_entry_point()` / `_build_fastapi_mandatory_block()` | Injects a `## MANDATORY PATTERNS` section into the user prompt for FastAPI entry files (`app.py`, `main.py`) on large models |
| **M8** | `_is_shared_js()` | Detects JS files imported by 2+ HTML pages and injects null-guard instructions: `const el = getElementById('x'); if (!el) return;` |
| —  | `_is_browser_js()` | Extended to treat `python_app` and `api` project types as browser JS contexts (so `app.js` gets the browser system prompt, not the Node.js one) |

### CrossFileValidationPhase improvements (new passes)

| ID | Pass | Error type | What it catches |
|----|------|-----------|----------------|
| **M5** | Pass 4 | `missing_api_route` | JS `fetch('/api/login')` when backend only defines `/admin/login`; uses `_normalize_route_path()` to match parameterized routes (`/api/bookings/{id}` ↔ `/api/bookings/42`) |
| **M6** | Pass 5 | `form_field_mismatch` | HTML `<form action="/api/...">` input `name="client_name"` when Pydantic model defines `name`; uses `_best_match()` for rename suggestions |

### PatchPhase improvements

| ID | Method | What it does |
|----|--------|-------------|
| **M1** | `_CONTENT_INCLUDE_MAX_CHARS` | Raised from 8 000 → **50 000** chars (file limit ≤10); multi-file projects now include full file content in the LLM reviewer prompt instead of summaries |
| **M9** | `_build_patch_context()` | For HTML files ≤5 000 chars, passes the **complete HTML** as context to `CodePatcher` — prevents `<section>` insertions after `</footer>` |
| **M10** | `_check_python_connection_bugs()` | Detects `USE_AFTER_CLOSE` (`conn.close()` + `cursor.execute()` within 10 lines) and `INIT_DB_ONLY_IN_MAIN` (`init_db()` only called inside `if __name__ == '__main__':`) |

### PhaseContext improvement

| ID | Method | What it does |
|----|--------|-------------|
| **M11** | `description_complexity()` | High-complexity domain words (admin, login, booking, availability, …) now score **+2 each** (was +1); multi-page bonus (+1 for ≥2 navigation keywords); barbershop booking app now correctly scores ≥6 instead of 3 |

## Pipeline Quality Improvements (Sprint 12)

Targeted fixes to make small-model (≤8B) output significantly better without touching code generation prompts.

### Default refinement loops raised

| Setting | Before | After |
|---------|--------|-------|
| UI slider default | 1 | **3** |
| UI slider max | 5 | **8** |
| API `num_refine_loops` default | 1 | **3** |
| `_MAX_IMPROVEMENT_ROUNDS_SMALL` | 2 | **3** |

### PatchPhase — focused aspects always active

Previously, the 6 targeted review aspects (HTML IDs vs JS, missing DOM elements, game loop, event listeners, CSS classes, duplicate exports) only activated when the user explicitly set `num_refine_loops > default_max`. The gate (`user_requested_extra`) has been removed — rounds 1+ now **always** cycle through focused aspects whenever the generic reviewer says "no issues".

With default 3 loops on a 4B model:
- Round 0: generic review or seed from `cross_file_errors`
- Round 1: focused → HTML IDs vs `getElementById` calls
- Round 2: focused → missing DOM container elements

### SeniorReviewPhase — compact review upgraded

| Aspect | Before | After |
|--------|--------|-------|
| Input to reviewer | File names + purposes only | **Full file content** (≤6 files / ≤20K chars) |
| Repair cycles | 1 | **2** (exits early if clean or nothing fixable) |

## Pipeline Quality Improvements (Sprint 14)

8 targeted fixes across BlueprintPhase, CodeFillPhase, PatchPhase, CrossFileValidationPhase, PhaseContext, ProjectScanPhase, and CodePatcher. All changes are backward-compatible; 1267 unit tests pass.

### BlueprintPhase improvements

| ID | Method | What it does |
|----|--------|-------------|
| **I1** | `run()` — deduplication block | Before converting to `FilePlan`, removes duplicate paths from the LLM response — keeps last occurrence (more refined), logs warning |
| **I2** | `_dynamic_max_files()` | api+db combo detection: large model floor raised to 14; small models with db in stack get 9 instead of 7 |
| **I4** | `_enforce_described_files()` | Auto-injected files now derive `key_logic` from description context (was `""`); LLM gets meaningful implementation guidance instead of empty string |

### CodeFillPhase improvements

| ID | Location | What it does |
|----|---------|-------------|
| **I8** | `_fill_one()` — truncation limits | `project_description` limit raised: small models 200→400 chars, large models 400→800 chars |
| **I8** | `_fill_one()` — key_logic fallback | Empty `key_logic` now falls back to `"implement {path} as described in the project"` instead of the generic `"implement as described"` |

### PatchPhase + ProjectScanPhase improvements

| ID | File | What it does |
|----|------|-------------|
| **I3** | `project_scan_phase.py` `_ingest_existing()` | `OLLASH_RUN_LOG.md` excluded from ingested source files — prevents pipeline metadata from polluting `ctx.generated_files` |
| **I3** | `patch_phase.py` `_ask_llm_for_issue()` + `_build_file_summary()` | `OLLASH_RUN_LOG.md` filtered from both content-inclusion loop and file summary — saves tokens, avoids confusing the reviewer LLM |

### CodePatcher improvements

| ID | Method | What it does |
|----|--------|-------------|
| **I5** | `_check_brace_balance()` (new static) | Soft brace/bracket balance validator: tolerance=5, checks `{}`, `()`, `[]`; applies to `.py .js .ts .tsx .cs .go .java .rs` |
| **I5** | `apply_search_replace()` | Accepts optional `file_ext`; reverts to original content and logs warning if balance check fails after all patches applied |
| **I5** | `apply_unique_edit()` | Same balance guard; reverts to original + returns empty diff on failure |

### PhaseContext improvement

| ID | Method | What it does |
|----|--------|-------------|
| **I6** | `description_complexity()` | When `project_type == "csharp_app"`: C#-specific high-complexity (+2) keywords — `controller`, `middleware`, `dependency injection`, `entity framework`, `migration`, `service`, `repository`, `interface`; standard (+1) — `namespace`, `linq`, `model`, `dto`, `swagger`, `configuration` |

### CrossFileValidationPhase improvement

| ID | Pass | Error type | What it catches |
|----|------|-----------|----------------|
| **I7** | Pass 8 (extended) | `cs_duplicate_type` | Two or more `.cs` files that define a `public class/interface/record/struct/enum` with the same name — would cause `CS0101` at compile time. Returned before undefined-reference errors so PatchPhase fixes structural issues first |

---

## Pipeline Quality Improvements (Sprint 13)

Targeted fixes for C# project generation, validated via the CRM básico C# test run.

### Fix 1 — `LLMResponseParser.extract_code_block_for_file` — lang_map + anchor fix

| Problem | Root cause | Fix |
|---------|-----------|-----|
| `csharp` fence → first word was `"harp..."` | `\b` word-boundary matched middle of `csharp` | Anchor changed to `(?:[^\w\-]\|\n)` |
| 11 languages missing from `lang_map` | `csharp`, `kotlin`, `cpp`, `ruby`, `dart`, `swift`, `scala`, etc. not mapped | Extended map with canonical aliases |

File: `backend/utils/core/llm/llm_response_parser.py` · Tests: `TestExtractCodeBlockForFileCsharp` (8 tests)

### Fix 2 — BlueprintPhase: `_enforce_described_files`

- Renamed `_warn_missing_described_files` → `_enforce_described_files`
- Extracts file paths from the project description (regex `[\w/\-\.]+\.\w+`) and auto-injects missing entries as `FilePlan` objects
- Cap: ≤3 injections for small models (≤8B); unlimited for large models
- Injected files get `priority = max_existing + 1`

File: `backend/agents/auto_agent_phases/blueprint_phase.py` · Tests: 5 new tests

### Fix 3 — CodeFillPhase: expanded C# system prompt

- `_SYSTEM_CSHARP` now explicitly warns against `RemoveAsync()` (EF Core has no such method), enforces `AddControllers()` before `MapControllers()`, and includes HTTP verb guidance (`[HttpGet]` = read-only only)
- Compact variant in `_SYSTEM_BY_EXT_SMALL[".cs"]` mirrors the same 3 rules

File: `backend/agents/auto_agent_phases/code_fill_phase.py` · Tests: 9 tests in `test_code_fill_prompts.py`

### Fix 4 — InfraPhase: `_get_csharp_assembly_name`

Resolution priority:
1. Stem of any `.csproj` file path in `generated_files`
2. `<AssemblyName>` tag inside `.csproj` content
3. `project_name` with all spaces stripped

Prevents `ENTRYPOINT ["dotnet", "app.dll"]` — Dockerfile now uses the real assembly name.

File: `backend/agents/auto_agent_phases/infra_phase.py` · Tests: 7 tests in `test_infra_phase_csharp.py`

### Fix 5 — CrossFileValidationPhase: Pass 8 — C# class/interface refs

- Collects all `public class/interface/record/struct/enum` names across `.cs` files
- Scans each file for constructor calls (`new TypeName(`), field types, base class declarations
- Flags any PascalCase name that is not in the defined set and not in the BCL exclusion list (~50 known .NET types)
- Deduplicates errors per `(file, type_name)` pair

File: `backend/agents/auto_agent_phases/cross_file_validation_phase.py` · Tests: 5 new tests

### Fix 6 — PatchPhase: `_check_csharp_static` (zero-LLM, no dotnet toolchain)

| Code | What it detects |
|------|----------------|
| `CS-EF001` | `.RemoveAsync(` — EF Core has no such method; use `.Remove()` + `SaveChangesAsync()` |
| `CS-REST002` | `[HttpGet]` on a method whose name contains `Update/Delete/Toggle/Set/Mark/Remove/Create/Add` |
| `CS-DI003` | `app.MapControllers()` without `builder.Services.AddControllers()` in Program.cs |
| `CS-DB004` | `AddDbContext` without `EnsureCreated`/`Migrate` (advisory — logged as warning, not auto-patched) |

File: `backend/agents/auto_agent_phases/patch_phase.py` · Tests: 7 new tests

---

## Pipeline Quality Improvements (Sprint 15)

3 targeted fixes identified from a real poker game test run (`JuegoPokerTexas`, `qwen3.5:4b`, 3 refine loops). All changes are backward-compatible; 1267 unit tests pass.

### Fix B4a — BlueprintPhase: skip JS merge for explicitly-named files

**Problem:** `_merge_dependent_js_for_small_models()` removed `static/ai.js` by merging it into `static/game.js`, even though the project description explicitly listed `static/ai.js (AI decision engine)` as a required file. The merged file was never generated, leaving the project with 4 files instead of 5.

**Fix:** Before merging, extract filenames mentioned in the description with the same regex as `_enforce_described_files`. If the importer file is explicitly named, log and skip the merge — the user's multi-file intent is respected.

| Condition | Before | After |
|-----------|--------|-------|
| Importer file unnamed in description | Merge proceeds | Merge proceeds (unchanged) |
| Importer file explicitly named in description | Merge proceeds, file deleted | **Merge skipped**, file preserved |

File: `backend/agents/auto_agent_phases/blueprint_phase.py` · `_merge_dependent_js_for_small_models()` lines 284–290

### Fix B4b — BlueprintPhase: deduplicate imports after merge redirect

**Problem:** When the merge redirected `ai.js → game.js`, files that already imported `game.js` ended up with `["static/game.js", "static/game.js"]` in their imports list. CodeFillPhase fed the duplicate signatures twice to the LLM, which caused `ui.js` to re-implement the entire poker engine internally instead of calling `window.PokerEngine`.

**Fix:** After replacing `A` with `B` in any file's imports, wrap the result in `list(dict.fromkeys(...))` to deduplicate while preserving insertion order.

File: `backend/agents/auto_agent_phases/blueprint_phase.py` · `_merge_dependent_js_for_small_models()` lines 313–315

### Fix BP8 — Blueprint prompt: DOM element ID consistency instruction

**Problem:** `ui.js` was generated with `#bigBlind`, `#dealer`, `#nextBtn`, `#pot`, `#resetBtn`, `#sidePots`, `#smallBlind` — but `index.html` was generated independently with different IDs, producing 7 `id_mismatch` cross-file validation errors that the patch phase couldn't resolve.

**Root cause:** Neither the `key_logic` for the JS files nor the `key_logic` for `index.html` explicitly listed the DOM element IDs, so each LLM call invented its own set.

**Fix:** Added instruction 8 to both `blueprint.yaml` (`generate_blueprint_small`) and the inline `_SYSTEM_FALLBACK_SMALL`:

> *For frontend JS files that use getElementById/querySelector: key_logic MUST list every DOM element ID accessed (e.g. `"reads #pot, #player-hand; writes #status, #action-buttons"`). index.html key_logic MUST include a matching `<div id=xxx>` for EVERY id that JS files reference.*

Updated Example 2 to demonstrate the pattern — the JS file now shows `reads #community-cards, #player-hand, #pot, #action-buttons, #status, #btn-fold, #btn-call, #btn-raise` and index.html explicitly lists all matching elements.

Files: `prompts/domains/auto_generation/blueprint.yaml` · `backend/agents/auto_agent_phases/blueprint_phase.py` (`_SYSTEM_FALLBACK_SMALL`)
