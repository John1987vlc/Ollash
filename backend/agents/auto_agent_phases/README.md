# auto_agent_phases — 10-Phase AutoAgent Pipeline

Sequential pipeline for project generation optimized for 4B models (qwen3.5:4b).

## Pipeline

| # | Phase | LLM? | Description |
|---|-------|------|-------------|
| 1 | `ProjectScanPhase` | No | Detect project type/stack via keywords; ingest up to 50 existing files |
| 2 | `BlueprintPhase` | Yes (1 call) | Generate full project blueprint as Pydantic-validated JSON (max 20 files) |
| 3 | `ScaffoldPhase` | No | Create directories and write language-specific stub files |
| 4 | `CodeFillPhase` | Yes (1/file) | Generate file content in priority order with language-specific prompts, syntax validation + 1 retry |
| 4b | `CrossFileValidationPhase` | No | 6 zero-LLM contract checks: HTML↔JS ids, CSS classes, Python imports, JS fetch vs routes, form fields vs Pydantic models, duplicate window.* exports |
| 5 | `PatchPhase` | Yes (optional) | Static analysis (ruff/tsc/go vet/…) + DB connection bug detection + **3-round** improvement loop; rounds 1+ cycle through 6 focused review aspects (HTML IDs, DOM, game loop, event listeners, CSS classes, duplicates) |
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
