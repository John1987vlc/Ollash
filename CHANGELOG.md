# Changelog - Ollash

## [1.3.0] - 2026-03-15 (Quality Pipeline — Cross-File Validation + Senior Review)

### ✨ New Features

#### 10-Phase AutoAgent Pipeline
The project generation pipeline grows from 8 to **10 phases** with two new quality phases that catch semantic bugs static analysis cannot:

- **`CrossFileValidationPhase` (4b)** — Zero-LLM contract checker inserted between CodeFill and Patch:
  - **HTML ↔ JS ID contract**: detects `getElementById("chess-board")` when HTML only has `id="board"`. Auto-fixes mismatches with similarity > 50% using `difflib.SequenceMatcher` (JS is treated as the spec). Unfixable cases are seeded into PatchPhase for LLM repair.
  - **HTML ↔ CSS class contract**: flags HTML class attributes with no corresponding CSS selector (advisory).
  - **Python relative imports**: verifies that `from .module import Name` resolves to a name actually defined in the target module.
  - Runs on **all model tiers** including 4B (zero LLM cost). Stores errors in `ctx.cross_file_errors` for downstream phases.

- **`SeniorReviewPhase` (6b)** — Activates the existing `SeniorReviewer` utility (previously never called from the pipeline), inserted between Patch and Infra:
  - Up to 2 review + CodePatcher repair cycles per generation.
  - Fixes critical/high severity issues (missing game logic, wrong data flow, incomplete state machines) automatically.
  - Respects a 20K character budget when sending files to the 32K-context reviewer to prevent OOM.
  - Skipped automatically for ≤8B models. Results stored in `ctx.metrics["senior_review"]`.

#### Enhanced PatchPhase — Multi-Round Improvement
`_iterative_improvement()` now runs **3 rounds** (was 1), 2 for small models:
- **Round 0** consumes `ctx.cross_file_errors` as seed — no extra LLM call needed when CrossFileValidation found issues.
- **Content inclusion**: for projects ≤ 6 files and ≤ 8 000 total chars (typical for HTML/JS games), the LLM receives **actual file content**, not just path+purpose — enabling it to spot HTML id mismatches, truncated SVGs, etc.
- **Between rounds**: zero-LLM HTML↔JS ID re-check refreshes `ctx.cross_file_errors` so each round has fresh data.
- Metrics: `ctx.metrics["iterative_improvement_rounds"]` records how many rounds ran.

#### PhaseContext — `cross_file_errors` field
New pipeline communication channel (`List[Dict[str, Any]]`) written by CrossFileValidationPhase and consumed by PatchPhase. Not persisted in checkpoint (transient state).

### ✅ Tests
- `tests/unit/backend/agents/auto_agent_phases/test_cross_file_validation_phase.py` — 13 tests covering ID detection, auto-fix, CSS/Python checks, metrics, internal key stripping.
- `tests/unit/backend/agents/auto_agent_phases/test_senior_review_phase.py` — 10 tests covering small model skip, pass/fail cycles, repair loop, robustness on import failures and missing files.
- **1 129 unit tests passing** (was 1 106).

### 🏗️ Architecture
- `auto_agent.py` `FULL_PHASE_ORDER` extended to 10 entries; `SMALL_PHASE_ORDER` to 8 (adds CrossFileValidationPhase, keeps SeniorReviewPhase out).
- Phase IDs: `CrossFileValidationPhase = "4b"`, `SeniorReviewPhase = "6b"` (preserve existing phase numbering).
- All new phases follow best-effort pattern: wrapped in `try/except Exception`, never abort the pipeline.

---

## [1.2.0] - 2026-02-22 (Architecture Cleanup & Code Quality)

### 🏗️ Refactoring & Code Quality
- **Eliminated Merge Artifacts:** Removed duplicate `_validate_content` and `_generate_fallback_skeleton` methods from `EnhancedFileContentGenerator` (left over from a bad Git merge). Moved `import re` to module level.
- **SRP Enforcement:** Extracted all code patching and merging logic into a new dedicated `CodePatcher` class (`backend/utils/domains/auto_generation/code_patcher.py`), leaving `EnhancedFileContentGenerator` focused solely on creating files from plans.
- **Safe Code Merging:** Replaced dangerous length-ratio and brace-counting heuristics in `_smart_merge` and `_is_better_line` with `difflib.SequenceMatcher` for structural comparison. Code with < 30% similarity to the original is rejected; code with > 70% similarity is accepted directly; intermediate cases use opcode-level line merging.
- **Unified AI Strategy:** Added optional `documentation_manager` (RAG) parameter to `EnhancedFileContentGenerator`. When provided, it queries the knowledge base for relevant code examples and injects them into the generation context alongside the structured `logic_plan`.

### 🗄️ Preference System
- **Deprecated `PreferenceManager`:** Added `DeprecationWarning` to `PreferenceManager.__init__` pointing users to `PreferenceManagerExtended`.
- **Migration Utility:** Added `migrate_preferences(project_root, logger, user_id)` function to port legacy `.ollash_preferences.json` flat key-value data into `PreferenceManagerExtended` profile format.

### 🛡️ CI/CD
- **Fixed deploy condition:** Corrected `deploy` job trigger condition from `refs/heads/main` to `refs/heads/master`, aligning with the actual default branch.

### ✅ Tests
- New `test_enhanced_file_content_generator.py`: regression tests for duplicate methods, RAG injection, and delegation pattern.
- New `test_code_patcher.py`: structural tests for `_smart_merge` (difflib) and `_is_better_line` (no brace counting).
- New `test_preference_manager_deprecation.py`: deprecation warning and migration utility tests.

---

## [1.1.0] - 2026-02-22 (Agile Refactor & SLM Optimization)

### 🏗️ Agile & Iterative Engine
- **Micro-task Backlog:** Migration from waterfall file generation to an Agile backlog of atomic tasks. The agent now decomposes projects into a `BACKLOG.json` before execution.
- **Iterative Execution Loop:** Sequential execution of micro-tasks with dedicated context injection for each step, preventing LLM context saturation.
- **Context Distillation:** AST-based code skeleton extraction (`ContextDistiller`) to reduce token usage by sending only class/method signatures of related files.

### 🧠 SLM Reliability & Performance
- **High-End Hardware Tuning:** Optimized defaults for high-end GPUs (RTX 5080/4090):
  - Context window increased to **16,384 tokens**.
  - Precision tuning: Temperature `0.1`, Repeat Penalty `1.15`.
- **Structural XML Prompting:** Rigid response format using `<thinking_process>` (Chain of Thought) and `<code_created>` tags to ensure reliable code extraction.
- **AST Self-Correction Loop:** 3-attempt iterative loop with native Python syntax validation. The agent now receives tracebacks and self-corrects code before saving.
- **Model Standardization:** Standardized on `qwen3-coder:30b` as the primary coding engine across all configurations.

### 📊 UX & Frontend
- **Real-time Kanban Board:** New Agile dashboard in the UI to monitor task states (Todo, In Progress, Done) via SSE events.
- **Progress Tracking:** Granular event system (`agent_board_update`) for real-time task movement visualization.
- **Improved Workspace:** Integrated new `auto_agent.html` view for better monitoring of autonomous projects.

### 🛡️ DevSecOps & CI/CD
- **Master Branch CI Alignment:** Updated GitHub Actions to correctly trigger on the `master` branch.
- **Test Suite Revamp:** Fixed multiple regression bugs in unit and integration tests related to Phase Context and API endpoint remapping.
- **Enhanced Validation:** Stricter validation rules for main entry-point files (minimum payload checks, hallucination detection).

## [1.0.0] - 2026-02-22 (Release)

### ✨ Major Architectural Improvements
- **Frontend Refactoring:** Migration to a modern, modular Vanilla JS architecture with clear separation of concerns (Modules, Core, Services).
- **Centralized Backend:** Unified Flask-based API for all agent interactions, system monitoring, and project management.
- **Agent Roles System:** Introduction of specialized personas:
  - **Analyst:** Information synthesis and risk assessment.
  - **Writer:** High-quality documentation and audience adaptation.
  - **Senior Reviewer:** Code quality gates and architectural oversight.
  - **Orchestrator:** Intelligent task decomposition and routing.
- **Centralized Prompt Management:** All agent prompts migrated from hardcoded Python strings to a structured YAML hierarchy in `/prompts/`, allowing for easier maintenance and tuning without code changes.

### 🛡️ DevSecOps & Stability
- **E2E Testing Suite:** Implementation of Playwright-based end-to-end tests covering Chat, Project Generation, and Wizard flows.
- **Self-Healing CI/CD:** Integrated `CICDHealer` and `VulnerabilityScanner` modules.
- **Resource Management:** New GPU-aware rate limiting and concurrent session management.
- **Security Audit:** Elimination of absolute machine paths and improved secret handling via `.env`.

### 🚀 Features & UX
- **Real-time SSE Streaming:** Enhanced feedback loop for agent actions and logs.
- **Knowledge Graph:** Automated extraction of entities and relationships from generated code.
- **Automatic Learning System:** Vector-based memory for error resolution and pattern recognition.
- **Modular Toolset:** Organized domain-specific tools (Cybersecurity, Network, System, Infrastructure).

### 🧹 Cleanup
- Archived legacy debug scripts.
- Optimized `requirements.txt` and `.env.example`.
- Pristine root directory structure.

---
**Ollash v1.0.0: The Autonomous IT & Development Assistant.**
