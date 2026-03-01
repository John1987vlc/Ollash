# <img src="Ollash.jpg" width="48" height="48" valign="middle"> Ollash - Local IT Agent

**Ollash** is an advanced AI-powered Code and IT Assistant designed to operate entirely on your local infrastructure using **Ollama**. It combines multiple specialized agents into a cohesive "Agent-per-Domain" architecture to handle everything from complex software development to network analysis and cybersecurity audits.

---

## 🚀 Key Features

### 🧠 Specialized Multi-Agent Swarm
Ollash doesn't rely on a single generic prompt. It employs a team of specialized agents coordinated by a central orchestrator:
*   **Architect Agent:** Designs project structures and identifies dependencies.
*   **Developer Agent:** Writes, refines, and patches code across multiple languages.
*   **DevOps Agent:** Manages CI/CD pipelines and infrastructure generation.
*   **Auditor Agent:** Performs security scans and code quality reviews.
*   **Security Agent:** Monitors for vulnerabilities and enforces safety policies.

### 🏗️ Auto-Agent Project Pipeline
Generate complete, production-ready projects from a single text description through a rigorous 8-phase pipeline:
1.  **Analysis & Planning:** Detailed requirement breakdown.
2.  **Structure Generation:** Scaffolding the entire project tree.
3.  **Logic Design:** Planning function-level logic before coding.
4.  **Content Generation:** Parallelized file content creation.
5.  **Iterative Refinement:** Multiple passes to improve code quality.
6.  **Verification:** Automated testing and syntax validation.
7.  **Security & Compliance:** Vulnerability scanning and license checks.
8.  **Final Review:** Senior-level holistic project audit.

### 🌐 Modern Web UI (SPA)
A rich, interactive Single Page Application built with Flask and Vanilla CSS:
*   **Real-time Chat:** Interactive terminal-like chat with tool-calling capabilities.
*   **Architecture Visualization:** Dynamic graphs of your project's structure.
*   **Intelligence Hub:** Explore the agent's Knowledge Base (RAG), Episodic Memory, and Learned Error Patterns.
*   **Time Machine:** Create and restore project checkpoints.
*   **Ops Center:** Monitor background jobs and automation triggers.
*   **Model Benchmarker:** Compare local LLM performance on standardized tasks.

### 🛠️ Advanced Infrastructure
*   **Smart RAG (ChromaDB):** Semantic search over project documentation.
*   **Self-Healing Loops:** Automatically detects and fixes errors during generation.
*   **Safe Sandbox:** Executes commands in a controlled environment with policy enforcement.
*   **Hybrid Model Routing:** Automatically selects the best model for each specific task (e.g., Qwen3-Coder for coding, Ministral for planning).

---

## 💻 CLI Usage Examples

Ollash provides a powerful CLI to interact with its multi-agent swarm and utility tools.

### 💬 Interactive Chat
Enter an interactive chat session with specialized agents:
```bash
# Start a chat session similar to gemini-cli
python ollash_cli.py chat
```

### 🛠️ Project Generation (Multi-Agent Swarm)
Kickstart a new project with parallel Developer Agents:
```bash
# Generate a modern dashboard with 5 parallel developer agents
python ollash_cli.py agent "Create a React dashboard with TailwindCSS and Chart.js" --name dashboard_pro --pool-size 5
```

### 🐝 Swarm Tasks
Invoke the swarm for quick data processing tasks:
```bash
# Summarize a large document and extract key tasks
python ollash_cli.py swarm "Summarize docs/api_specification.pdf and list required endpoints"
```

### 🛡️ Security Operations
Perform automated vulnerability scans:
```bash
# Scan a directory for common security issues
python ollash_cli.py security scan ./my_new_project
```

### 📊 Benchmarking & Testing
Test local models or generate test suites:
```bash
# Run the model benchmarking suite
python ollash_cli.py benchmark

# Generate unit tests for a Python project
python ollash_cli.py test-gen ./src/core_logic.py
```

### 📁 Git Management
Automate PR creation and management:
```bash
# Prepare a PR description from recent changes
python ollash_cli.py git pr prepare
```

---

## 🛠️ Technology Stack
*   **Backend:** Python 3.x, Flask, Dependency Injector.
*   **LLM Engine:** Ollama (Default: `qwen3-coder:30b` and `ministral-3:8b`).
*   **Vector DB:** ChromaDB (for long-term memory and RAG).
*   **Memory:** SQLite (for episodic logs and decision tracking).
*   **Frontend:** HTML5, Vanilla CSS, Modern JavaScript (SPA architecture).

---

## ⚡ Quick Start

### Prerequisites
1.  Install [Ollama](https://ollama.ai/).
2.  Pull the required models:
    ```bash
    ollama pull qwen3-coder:30b
    ollama pull ministral-3:8b
    ollama pull qwen3-embedding:4b
    ```

### Installation
1.  Clone the repository:
    ```bash
    git clone https://github.com/your-repo/ollash.git
    cd ollash
    ```
2.  Set up a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: .\venv\Scripts\activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Configure your environment:
    ```bash
    cp .env.example .env
    # Edit .env to set your OLLAMA_URL
    ```

### Execution
*   **Start the Web UI:** `python run_web.py`
*   **Start the CLI Agent:** `python ollash_cli.py --chat`
*   **Generate a Project:** `python backend/agents/auto_agent.py "Create a FastAPI app with SQLite and JWT"`

---

## 📂 Project Structure
```text
ollash/
├── backend/            # Core logic, agents, and utilities
│   ├── agents/         # specialized agent implementations
│   ├── config/         # JSON configurations and policies
│   ├── core/           # Kernel, containers, and loaders
│   └── utils/          # Domain-specific tools (git, code, net, etc.)
├── frontend/           # Web UI (Flask templates, static assets)
├── docs/               # Detailed documentation and status reports
├── prompts/            # System prompts for all agent roles
└── .ollash/            # Local data (ChromaDB, logs, checkpoints)
```

---

## ⚡ Optimizaciones para Modelos Pequeños (≤4B)

Ollash incluye 6 optimizaciones ortogonales diseñadas para que modelos pequeños (Qwen3 3B, Ministral 3B, etc.) generen código de calidad sin saturar su ventana de contexto ni reescribir código ya funcional.

| # | Optimización | Descripción |
|---|---|---|
| **F1** | **Interface Skeleton Scaffolding** | Antes de generar implementaciones, `InterfaceScaffoldingPhase` crea archivos `.pyi` (Python) y `.d.ts` (TypeScript) a partir de los exports del `logic_plan`. El LLM solo "rellena los huecos" de un contrato ya definido. Cero llamadas al LLM — completamente determinístico. |
| **F2** | **TDD Agéntico en Caliente** | Tras generar cada archivo `.py`, `FileContentGenerationPhase._run_tdd_loop()` genera un test mínimo con el prompt `tdd_minimal_test`, lo ejecuta con `pytest` en un directorio temporal y corrige el código si falla, con hasta 2 reintentos automáticos. |
| **F3** | **API Maps (Compresión de Contexto)** | `PhaseContext.build_api_map()` precomputa un mapa `{ruta → firmas}` una sola vez por pasada. `_is_small_model()` detecta automáticamente modelos ≤4B (regex sobre el nombre del modelo) y activa `select_related_files(signatures_only=True)`, reduciendo el contexto a solo cabeceras de funciones/clases. |
| **F4** | **Capas de Abstracción (TACTICAL/CRITIC)** | Dos nuevos tipos de agente en el swarm: `TacticalAgent` implementa una sola función por turno usando `ast` + `CodePatcher.apply_search_replace()` con contexto mínimo; `CriticAgent` escanea todos los archivos generados contra `ErrorKnowledgeBase` y escribe advertencias en el `Blackboard` bajo `critique/` — sin ninguna llamada al LLM. |
| **F5** | **Blackboard como Memoria de Corto Plazo** | Tras completar cada nodo del `TaskDAG`, el agente escribe en el Blackboard una nota concisa (`context_notes/{node_id}`) con las librerías usadas y los exports creados. El `DomainAgentOrchestrator` inyecta las notas de dependencias directas como contexto previo en la tarea siguiente. |
| **F6** | **Parches SEARCH/REPLACE (Diff Quirúrgico)** | `CodePatcher` soporta una nueva estrategia `search_replace` donde el LLM devuelve bloques `<<<SEARCH>>>...<<<REPLACE>>>...<<<END>>>`. `parse_search_replace_patch()` y `apply_search_replace()` aplican los cambios quirúrgicamente sin tocar el resto del archivo. `FileValidator.validate_patch_applicable()` verifica que el bloque buscado existe antes de modificar nada. |

### Activación automática

```python
# F3 se activa automáticamente según el tamaño del modelo configurado
# en backend/config/llm_models.json para el rol "coder"
phase_context._is_small_model("coder")  # → True si modelo ≤ 4B

# F1 se ejecuta automáticamente en el pipeline entre LogicPlanningPhase y StructurePreReviewPhase
# F4 se activa cuando el ArchitectAgent emite nodos AgentType.TACTICAL o AgentType.CRITIC
# F5 y F6 son siempre activos — forman parte del flujo estándar del swarm
```

---

## 🔬 Agent Reliability Pack — Small Model Closed-Loop Features

Six orthogonal features that turn small Ollama models (≤4B/7B) into reliable code generators by adding self-correction, memory, predictive loading, chaos testing, live task visibility, and cognitive-load guards. All features are **fail-safe**: any exception inside them is swallowed so the existing pipeline is never aborted.

| # | Feature | File | Default |
|---|---------|------|---------|
| **R1** | **Critic-Correction Closed Loop** | `backend/utils/core/analysis/critic_loop.py` | ✅ enabled |
| **R2** | **Few-Shot Dynamic Store** | `backend/utils/core/memory/fragment_cache.py` | ✅ enabled |
| **R3** | **Predictive Context Loading** | `backend/agents/auto_agent_phases/phase_context.py` | ✅ always-on |
| **R4** | **Chaos Engineering Mode** | `backend/agents/auto_agent_phases/chaos_injection_phase.py` | ❌ disabled |
| **R5** | **HITL Micro-Level DAG Dashboard** | `frontend/blueprints/hil_bp.py` · `chat.js` | ✅ always-on |
| **R6** | **Context Saturation Alerts** | `backend/utils/core/llm/context_saturation.py` | ✅ enabled |

### R1 — Critic-Correction Closed Loop

After each file is generated and shadow-validated, a second nano-LLM call checks for syntax errors, missing imports, and indentation issues. If errors are found the feedback is injected as `last_error` and the generation retries (max 2 additional attempts). The critic never aborts the pipeline — on any exception it returns `None` and generation proceeds normally.

```json
// backend/config/agent_features.json
"critic_loop": { "enabled": true }
```

### R2 — Few-Shot Dynamic Store

Every file that passes all validations is stored in `FragmentCache` as a `successful_task_example` keyed by language and purpose. Before generating the next file the system queries for the top-2 keyword-overlap examples and injects them into the prompt as few-shot demonstrations.

```json
"few_shot_store": { "enabled": true }
```

### R3 — Predictive Context Loading

After each pipeline phase completes, `AutoAgent` peeks at the next phase class and pre-computes API-map signatures (function/class headers) for every file the next phase is likely to read. Results are stored in `PhaseContext.prefetched_context`. `FileContentGenerationPhase` checks this cache first, skipping redundant `select_related_files()` calls on cache hits.

### R4 — Chaos Engineering Mode

`ChaosInjectionPhase` runs after `FileContentGenerationPhase` and intentionally corrupts a configurable fraction of generated files (removes a random import, renames a local variable to `__chaos_<name>_x`). The downstream `ShadowEvaluator` and `ExhaustiveReviewRepairPhase` must detect and heal these faults. Disabled by default; enable only in test environments.

```json
"chaos_engineering": { "enabled": false, "injection_rate": 0.2 }
```

### R5 — HITL Micro-Level DAG Dashboard

A collapsible panel in the chat UI shows every `TaskDAG` node in real-time via `task_status_changed` SSE events. PENDING nodes expose an **Edit Instruction** button that calls:

```http
PUT /api/hil/edit-task/<task_id>
Content-Type: application/json
{"instruction": "use asyncpg instead of psycopg2"}
```

Returns `409` if the node is no longer PENDING, `404` if not found.

### R6 — Context Saturation Alerts

Before every `OllamaClient.achat()` / `chat()` call the prompt length is estimated (`word_count × 1.3` tokens) and compared to the inferred model context window (parsed from the model name: `3b`→4096, `7b`→8192, `14b`→16384, `30b`→32768, `70b`→65536). If usage exceeds the configured threshold a `context_saturation_alert` event is published → SSE → browser toast.

```json
"context_saturation": { "enabled": true, "threshold": 0.6 }
```

---

## 🛡️ Security & Safety
Ollash is built with security in mind. It includes a **Policy Enforcer** that intercepts all system commands, a **Code Quarantine** for analyzing suspicious snippets, and a **Vulnerability Scanner** to ensure generated code follows best practices.

---

## 📜 License
This project is licensed under the MIT License - see the LICENSE file for details.
