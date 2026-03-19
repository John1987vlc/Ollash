# auto_agent_phases — 10-Phase AutoAgent Pipeline

Sequential pipeline for project generation optimized for 4B models (qwen3.5:4b).

## Pipeline

| # | Phase | LLM? | Description |
|---|-------|------|-------------|
| 1 | `ProjectScanPhase` | No | Detect project type/stack via keywords; ingest up to 50 existing files |
| 2 | `BlueprintPhase` | Yes (1 call) | Generate full project blueprint as Pydantic-validated JSON (max 20 files); algorithm/game files required to list function signatures in `key_logic` |
| 3 | `ScaffoldPhase` | No | Create directories and write language-specific stub files |
| 4 | `CodeFillPhase` | Yes (1/file) | Generate file content in priority order with language-specific prompts, syntax validation + 1 retry; JS/TS brace-balance check triggers retry on truncated output |
| 4b | `CrossFileValidationPhase` | No | **11 zero-LLM contract checks:** HTML↔JS ids (P1), CSS classes (P2), Python imports (P3), JS fetch vs routes (P4), form fields vs Pydantic models (P5), duplicate window.* exports (P6), Python constructor arity (P7), C# class/interface refs (P8), DB-seeded string case (P9), HTML inline-script vs JS exports (P10), JS cross-global call validation (P11, large models) |
| 4c | `ExportValidationPhase` | No (large: optional) | Verifies every declared blueprint export exists in generated content; large models repair via `CodePatcher.inject_missing_function()`; small models push gaps to `cross_file_errors` for PatchPhase |
| 4d | `DuplicateSymbolPhase` | No | Removes duplicate top-level JS/TS/Python definitions that arise from multi-block LLM output; keeps FIRST occurrence (complete); removes subsequent stubs |
| 5 | `PatchPhase` | Yes (optional) | Static analysis (ruff/tsc/go vet/…) + DB connection bug detection + **3-round** improvement loop; after each round re-runs all CrossFileValidation passes; `id_mismatch`/`window_function_mismatch` errors bypass SEARCH/REPLACE for full-file regeneration |
| 6b | `SeniorReviewPhase` | Yes (1–4 calls) | Security prescan (zero-LLM) + large-model full review + CodePatcher repair; `"file"` list normalization prevents JSON parse failures; compact review for small models (≤8 files / ≤32K chars) |
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
| `phase_helpers.py` | Shared utilities: `deduplicate_python_content()`, `get_type_info_if_active()`, `filter_structure_by_type()` |
| `blueprint_models.py` | Pydantic models (`FilePlanModel`, `BlueprintOutput`) — imported only by BlueprintPhase |
| `project_scan_phase.py` | Phase 1 |
| `blueprint_phase.py` | Phase 2 |
| `scaffold_phase.py` | Phase 3 |
| `code_fill_phase.py` | Phase 4 |
| `cross_file_validation_phase.py` | Phase 4b |
| `export_validation_phase.py` | Phase 4c (Sprint 19) |
| `duplicate_symbol_phase.py` | Phase 4d (Sprint 19) |
| `patch_phase.py` | Phase 5 |
| `senior_review_phase.py` | Phase 6b |
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

---

## Pipeline Quality Improvements (Sprint 17)

6 targeted fixes from JuegoPokerTexas run log analysis (`qwen3.5:4b`, 5-file JS game, 3 refine loops).

### CrossFileValidationPhase — Pass 10 + Pass 11

| ID | Pass | Error type | What it catches |
|----|------|-----------|----------------|
| **P10** | Pass 10 | `inline_script_vs_export` | HTML `<script>` tags that define a function already exported by a standalone `.js` file — would shadow the file-based export at runtime |
| **P11** | Pass 11 | `cross_global_call` | JS file A calls `window.B.method()` but file B never sets `window.B` — catches missing global namespace wiring. Large models only. |

### BlueprintPhase — DOM-ID pre-sync

`_validate_and_patch_html_entrypoint_key_logic()` now runs before `ScaffoldPhase`. IDs extracted from every JS file's `key_logic` are injected into `index.html`'s `key_logic` before any file is written — reducing `id_mismatch` errors in CrossFileValidationPhase from ~7 to ~0.

### PatchPhase — structural-rename bypass

`id_mismatch` and `window_function_mismatch` error types now bypass `SEARCH/REPLACE` patching entirely. Instead, the entire file is regenerated (≤12 000 chars) with the correct HTML IDs / JS export names injected directly into the prompt. Prevents partial renames that leave half the codebase using old names.

### CodeFillPhase — description budget raised

| Model tier | Before | After |
|-----------|--------|-------|
| small (≤8B) | 400 chars | **800 chars** |
| large (>8B) | 800 chars | **1 600 chars** |

---

## Pipeline Quality Improvements (Sprint 18)

5 fixes targeting a critical class of failure: the patch phase misdiagnosing complete files as truncated due to an insufficient content budget.

### Root cause (JuegoPokerTexas)

PatchPhase used an 18K char budget to show the reviewer all file contents. With 5 JS/HTML files totalling ~35K chars, `game.js` was sliced mid-function at `let flush` in the prompt. The reviewer correctly said "truncated" — but the actual file on disk was complete. All 3 patch rounds were consumed chasing a false positive.

| Fix | File | Change |
|-----|------|--------|
| **#S18-1** | `patch_phase.py` | Content budget in reviewer prompt: 18K→36K; gate constant 50K→80K |
| **#S18-2** | `code_fill_phase.py` | `_validate_syntax_detailed` now checks JS/TS/JSX/TSX brace balance — unbalanced braces trigger the existing retry loop |
| **#S18-3** | `auto_agent.py` | `SeniorReviewPhase` restored to `SMALL_PHASE_ORDER` (compact review was coded but not called) |
| **#S18-4** | `blueprint_phase.py` | `_SYSTEM_FALLBACK_SMALL` rule 6 now requires function signatures in `key_logic` for algorithm/game files |
| **#S18-5** | `code_fill_phase.py` | Description budget for small models: 800→1 200 chars |

---

## Pipeline Quality Improvements (Sprint 18b)

4 fixes targeting SeniorReview quality and static analysis completeness.

| Fix | File | Change |
|-----|------|--------|
| **#S18b-A** | `senior_review_phase.py` | `_CHAR_BUDGET` 20K→40K · `_COMPACT_CONTENT_MAX_FILES` 6→8 · `_COMPACT_CONTENT_MAX_CHARS` 20K→32K. JuegoPokerTexas (5 files, ~35K) now falls inside the content-aware threshold. |
| **#S18b-B** | `small_model_prompts.yaml` | `senior_review_compact` output format changed to `[{"file": "...", "description": "..."}]` objects — gives `_run_compact_review` a `file_hint` to target the right file |
| **#S18b-C** | `patch_phase.py` | Ruff error cap `raw[:20]` → `raw[:50]` — Python projects no longer silently drop errors 21+ |
| **#S18b-D** | `patch_phase.py` | `_warn_missing_tools()` called at start of `_collect_static_errors` — warns in log if ruff/node/tsc aren't installed for the project's language |

---

## Pipeline Quality Improvements (Sprint 19)

9 targeted fixes addressing systematic quality failures observed in `JuegoPokerTexas` generated project and the benchmark suite (SeniorReviewPhase scoring 0.2 across 11 models).

Root causes identified:
- 4 blueprint-declared exports (`initGame`, `calculatePot`, `makeMove`, `renderCards`) absent from generated code
- Stub placeholders (`// ... betting logic ...`) in `processBettingRound`; `makeDecision` cut mid-function
- `HAND_TYPES` declared twice in `game.js`; second declaration inside a function body broke the file
- `client/package.json` failing JSON parse on all 3 retries (unterminated string) with no syntax error feedback in the retry prompt
- SeniorReviewPhase: LLM emits `"file": ["a.js","b.js"]` instead of `"file": "a.js"` → 9× list-field warning → review aborted with `ERROR: manual intervention required`

### New Phase 4c — ExportValidationPhase (zero-LLM + optional repair)

Runs after `CrossFileValidationPhase`, before `DuplicateSymbolPhase`.

For each `FilePlan` with declared `exports`, checks that every export name appears in the generated content. Skips config/doc extensions (`.json`, `.yaml`, `.md`, etc.).

| Model tier | Action on missing export |
|-----------|--------------------------|
| Small (≤8B) | Writes `error_type: "missing_export"` to `ctx.cross_file_errors` — picked up by PatchPhase round 0 |
| Large (>8B) | Calls `CodePatcher.inject_missing_function()`; verifies injection succeeded; falls back to `cross_file_errors` if not |

Metrics: `ctx.metrics["export_validation"] = {checked, missing: ["file:name", ...], repaired: N}`. Fully non-fatal.

### New Phase 4d — DuplicateSymbolPhase (zero-LLM)

Runs after `ExportValidationPhase`, before `PatchPhase`.

Detects and removes duplicate top-level symbol definitions that arise when the LLM re-emits a function/class it already wrote (typically a shorter stub appended when the token budget ran out).

| Language | Detection | Keeps |
|----------|-----------|-------|
| JS/TS/JSX/TSX | `function X()`, `window.X =`, `class X`, top-level `const/let/var X` | FIRST occurrence |
| Python | AST-based via `phase_helpers.deduplicate_python_content()` | LAST occurrence |

Guard: skips removal if the line before the duplicate contains `if (typeof`, `if (!window.`, or `/* istanbul ignore */`.

Metrics: `ctx.metrics["duplicate_symbols"] = {js_cleaned: {path: [names]}, py_cleaned: {path: [names]}}`. Fully non-fatal.

### CodeFillPhase — 3 sub-improvements

| ID | Method | What it does |
|----|--------|-------------|
| **A-1** | `_fill_one()` + `_build_signature_context()` | After writing each file, stores real extracted signatures in `ctx.metrics["actual_signatures"]`. Signature context builder prefers these over blueprint declarations. Injects `# WARNING: does NOT export: {missing}` for any promised export absent from actual code. |
| **A-2** | `_generate_with_retry()` | Anti-stub guard: if file >50 lines and `_STUB_PATTERNS` matches on attempt 0, forces a retry with the matched placeholder lines listed explicitly. Patterns include `// ... X logic ...`, `# TODO`, `raise NotImplementedError`, `console.log('placeholder')`. |
| **A-3** | `_generate_config()` | JSON syntax guard: `json.loads()` after generation; passes the full parse error (`line X, col Y: MSG`) to the retry prompt. YAML guard via `yaml.safe_load()`. Failures logged to `ctx.metrics["config_syntax_failures"]`. |

### PatchPhase — full CrossFileValidation re-check between rounds (D)

After each patch round, `_refresh_cross_file_errors()` now calls `CrossFileValidationPhase()._run_validation(ctx)` — all 11 passes — instead of only the HTML↔JS ID check. New violations discovered between rounds are logged and fed into the next round's seed. Only runs when `.html`, `.js`, or `.ts` files are in the project. Non-fatal.

### SeniorReviewPhase — 2 fixes (E)

**E-1 — `"file"` list normalization:** When the LLM returns `"file": ["a.js","b.js"]` (a list), `_call_senior_reviewer()` now expands each list element into a separate issue entry before processing. A Pydantic `field_validator("file", mode="before")` in `SeniorReviewIssue` provides a second defensive coerce. `review.yaml` prompt updated with explicit `# MUST be a single filename string, NOT a list`.

**E-2 — SecurityPatternScan pre-step (zero-LLM, all tiers):** `_run_security_prescan()` runs before the LLM review call and detects:

| Pattern | Error type | Severity |
|---------|-----------|----------|
| `f"SELECT...{` | `sql_injection` | high |
| `innerHTML =` with variable | `xss_vulnerability` | medium |
| `eval(` | `code_injection` | high |
| `password/api_key/secret = "..."` | `hardcoded_credential` | critical |

Findings are added to `ctx.cross_file_errors` and logged to `ctx.metrics["security_prescan_findings"]`.
