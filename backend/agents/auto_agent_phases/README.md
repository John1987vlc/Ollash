# auto_agent_phases — 8-Phase AutoAgent Pipeline

Sequential pipeline for project generation optimized for 4B models (qwen3.5:4b).

## Pipeline

| # | Phase | LLM? | Description |
|---|-------|------|-------------|
| 1 | `ProjectScanPhase` | No | Detect project type/stack via keywords; ingest up to 50 existing files |
| 2 | `BlueprintPhase` | Yes (1 call) | Generate full project blueprint as Pydantic-validated JSON (max 20 files) |
| 3 | `ScaffoldPhase` | No | Create directories and write language-specific stub files |
| 4 | `CodeFillPhase` | Yes (1/file) | Generate file content in priority order with syntax validation + 1 retry |
| 5 | `PatchPhase` | Yes (optional) | `ruff`/`tsc` static analysis + `CodePatcher` targeted fixes, max 2 passes |
| 6 | `InfraPhase` | Yes (1-2 calls) | requirements.txt, Dockerfile, .gitignore, package.json |
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
| `base_phase.py` | `BasePhase(ABC)` — `execute()`, `_llm_call()`, `_llm_json()`, `_write_file()` |
| `blueprint_models.py` | Pydantic models (`FilePlanModel`, `BlueprintOutput`) — imported only by BlueprintPhase |
| `project_scan_phase.py` | Phase 1 |
| `blueprint_phase.py` | Phase 2 |
| `scaffold_phase.py` | Phase 3 |
| `code_fill_phase.py` | Phase 4 |
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
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
```

## Model Tiers

- `ctx.is_small()` — True if model ≤8B → skips TestRunPhase
- `ctx.is_micro()` — True if model ≤2B → uses shorter prompts
