# Ollash CLI Reference Guide

The `ollash_cli.py` is the official enterprise-grade CLI for managing the Ollash AI IT Agent. It provides direct access to the backend systems for automation, security, and maintenance.

## Global Options

- `--gpu-limit <float>`: Sets the GPU memory limit for the internal rate limiter.
- `--model-fallback`: Enables automatic model routing if the primary model fails.
- `--debug`: Activates verbose debug logging.

---

## Subcommands

### 1. `agent <task>`
Orchestrates a full autonomous project creation pipeline.
- **Arguments**:
  - `task`: Detailed description of the project to generate.
  - `--name <name>`: Custom name for the project directory.
- **Example**:
  ```bash
  python ollash_cli.py agent "Create a high-performance REST API with FastAPI and PostgreSQL" --name fast_api_project
  ```

### 2. `swarm <task>`
Invokes Cowork/Swarm tools for knowledge workspace operations.
- **Arguments**:
  - `task`: Specific swarm operation (Summarization, Log Analysis, Task Generation).
- **Example**:
  ```bash
  python ollash_cli.py swarm "Summarize architecture_overview.pdf"
  python ollash_cli.py swarm "Analyze recent system logs"
  ```

### 3. `security scan <path>`
Performs an AST and pattern-based security scan on the specified path.
- **Arguments**:
  - `path`: File or directory to scan.
- **Example**:
  ```bash
  python ollash_cli.py security scan ./backend/core
  ```

### 4. `git pr --auto`
Automatically creates a Pull Request for local changes.
- **Flags**:
  - `--auto`: Triggers the autonomous PR workflow (Branch -> Commit -> Push -> PR).
- **Example**:
  ```bash
  python ollash_cli.py git pr --auto
  ```

### 5. `cron add "<expr>" "<task>"`
Schedules a recurring task using a cron expression.
- **Arguments**:
  - `expr`: Standard cron expression (e.g., `"0 0 * * *"`).
  - `task`: Prompt or task to execute.
- **Example**:
  ```bash
  python ollash_cli.py cron add "0 22 * * *" "Perform security audit on knowledge_workspace"
  ```

### 6. `vision ocr <file>`
Processes an image or PDF file to extract text.
- **Arguments**:
  - `file`: Path to the image (PNG, JPG, WebP) or PDF.
- **Example**:
  ```bash
  python ollash_cli.py vision ocr screenshot.png
  ```

### 7. `benchmark`
Executes the model benchmarking suite to evaluate performance.
- **Example**:
  ```bash
  python ollash_cli.py benchmark
  ```

### 8. `test-gen <file> [--lang <lang>]`
Generates comprehensive unit tests for a source file.
- **Arguments**:
  - `file`: Source file path.
  - `--lang <lang>`: (Optional) Force a specific language/framework.
- **Example**:
  ```bash
  python ollash_cli.py test-gen backend/utils/core/io/file_manager.py
  ```
