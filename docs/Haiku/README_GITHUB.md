# Ollash - AI Agent Framework with Cowork-Inspired Knowledge Workspace

An advanced AI agent automation system with knowledge management, multi-format document ingestion, and Anthropic Cowork-inspired features.

## 🚀 Features

### Core Capabilities
- **Dynamic Knowledge Workspace**: Automatic document indexing and semantic search
- **Multi-Format Ingestion**: Support for PDF, DOCX, PPTX, TXT, Markdown documents
- **Cascade Summarizer**: Map-Reduce pipeline for processing large documents (100K+ words)
- **Specialist LLM Roles**: Analyst and Writer roles with task-specific prompting
- **7 Cowork-Inspired Tools**: Document analysis, log examination, task generation, executive summaries
- **Artifact Rendering**: Professional UI display with Markdown, code, JSON, and task planning
- **Automatic Indexing Daemon**: FileSystemWatch-based auto-indexing of new documents
- **RAG (Retrieval-Augmented Generation)**: ChromaDB-based semantic search preventing hallucinations

### Agent System
- Autonomous multi-task execution
- Multi-language code generation (Python, JavaScript, Go)
- Network scanning and discovery
- Project structure analysis and pre-review
- Concurrent operation with rate limiting
- Permission profiles and security enforcement

## 📦 Installation

### Prerequisites
- Python 3.8+
- Ollama (for local LLM inference)
- ChromaDB (vector database, included in dependencies)

### Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/ollash.git
cd ollash

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements-complete.txt

# Verify installation
python -m pytest tests/unit/test_cowork_impl.py -v
```

## 🏗️ Architecture

### Knowledge Workspace System
```
knowledge_workspace/
├── references/           # Source documents (PDF, DOCX, etc.)
├── indexed_cache/       # ChromaDB vector store
└── summaries/          # Generated summaries JSON
```

### Key Components

#### 1. MultiFormatIngester (`src/utils/core/multi_format_ingester.py`)
Extracts text from multiple document formats:
```python
ingester = MultiFormatIngester(logger)
text = ingester.ingest_file(Path("document.pdf"))
metadata = ingester.get_file_metadata(Path("document.pdf"))
```

#### 2. DocumentationWatcher (`src/utils/core/documentation_watcher.py`)
Monitors `references/` folder and auto-indexes new documents:
```python
watcher = DocumentationWatcher(doc_manager)
watcher.add_callback(on_document_indexed)
watcher.start()  # Daemon thread
```

#### 3. CascadeSummarizer (`src/utils/core/cascade_summarizer.py`)
Map-Reduce pipeline for efficient summarization:
```python
summarizer = CascadeSummarizer(ollama_client)
result = summarizer.cascade_summarize(
    long_text,
    title="Document Title",
    chunk_size=2000,
    compression_ratio=10  # Target 10:1 compression
)
# Returns: {original_word_count, summary, compression_ratio, chunk_count}
```

#### 4. Specialist LLM Roles
**Analyst Role** - Synthesizes information:
- Executive summaries
- Key insights extraction
- Risk analysis, gap analysis
- Comparative analysis

**Writer Role** - Refines content:
- Tone adjustment (formal/casual/executive)
- Technical documentation
- Grammar editing
- Audience adaptation

#### 5. Cowork Tools (7 integrated capabilities)
1. **document_to_task** - Convert documents to task lists
2. **analyze_recent_logs** - Identify risks in system logs
3. **generate_executive_summary** - Create condensed overviews
4. **query_knowledge_workspace** - Semantic document search
5. **index_reference_document** - Manual indexing trigger
6. **get_workspace_status** - Return workspace state
7. **refactor_artifact** - Modify generated documents

#### 6. Artifact Renderer (`src/web/static/js/artifact-renderer.js`)
Professional rendering for:
- Markdown with syntax highlighting
- Code blocks with language detection
- JSON with formatting
- Task plans with priority badges
- Refactoring capabilities (shorten/expand/formal/technical)

## 📖 Usage Examples

### 1. Upload and Index a Document

```python
from pathlib import Path
from src.utils.core.documentation_manager import DocumentationManager
from src.utils.core.agent_logger import AgentLogger

logger = AgentLogger("knowledge_test", disable_logging=False)
doc_manager = DocumentationManager(Path("."), logger)

# Upload document
doc_manager.upload_to_workspace(Path("whitepaper.pdf"))

# It auto-indexes via DocumentationWatcher daemon
# Or manually trigger:
doc_manager.index_documentation(Path("knowledge_workspace/references/whitepaper.pdf"))
```

### 2. Query Knowledge Base

```python
# Semantic search across indexed documents
results = doc_manager.query_documentation(
    query="What are the main architectural components?",
    n_results=3
)

for result in results:
    print(f"Source: {result['source']}")
    print(f"Content: {result['document']}")
    print(f"Relevance: {1 - result['distance']}")
```

### 3. Summarize Large Documents

```python
from src.utils.core.cascade_summarizer import CascadeSummarizer
from src.utils.core.ollama_client import OllamaClient

ollama = OllamaClient(model="ministral-3:8b", logger=logger)
summarizer = CascadeSummarizer(ollama)

# Process 50K-word document efficiently
summary = summarizer.cascade_summarize(
    long_text,
    title="Technical Specification",
    chunk_size=2000
)

print(f"Compression: {summary['compression_ratio']}:1")
print(f"Summary: {summary['summary']}")
```

### 4. Use Cowork Tools

```python
from src.utils.domains.bonus.cowork_impl import CoworkTools

tools = CoworkTools(doc_manager)

# Generate tasks from document
result = tools.document_to_task(
    document_name="requirements.docx",
    task_category="feature_development",
    priority="high"
)
print(f"Generated {result['tasks_generated']} tasks")

# Analyze logs
risks = tools.analyze_recent_logs(
    log_type="security",
    time_period="1d",
    top_n=5
)
for risk in risks['risks']:
    print(f"Risk: {risk['type']} (Severity: {risk['severity']})")
```

### 5. Render Artifacts in UI

```javascript
// JavaScript - src/web/static/js/artifact-renderer.js

// Register artifact
artifactRenderer.registerArtifact(
    "plan-001",
    "## Project Plan\n- Phase 1: ...",
    "markdown"
);

// Render to DOM
const container = document.getElementById("artifacts");
artifactRenderer.renderArtifact("plan-001", container);

// Refactor artifact
artifactRenderer.refactorArtifact("plan-001", "executive");

// Download as file
artifactRenderer.downloadArtifact("plan-001");
```

## 🧪 Testing

### Run All Tests

**Windows:**
```bash
run_tests.bat
```

**Linux/macOS:**
```bash
./run_tests.sh
```

### Run Specific Test Suite

```bash
# Cowork improvements tests only
pytest tests/unit/test_cowork_impl.py tests/unit/test_artifact_renderer.py -v

# Multi-format ingestion tests
pytest tests/unit/test_multi_format_ingester.py -v

# Cascade summarizer tests
pytest tests/unit/test_cascade_summarizer.py -v

# Knowledge watcher tests
pytest tests/unit/test_documentation_watcher.py -v

# All tests with coverage
pytest tests/unit/ -v --cov=src --cov-report=html
```

### Test Coverage

Current coverage of new modules:
- `test_cowork_impl.py`: 15 tests ✓
- `test_artifact_renderer.py`: 20 tests ✓
- `test_documentation_watcher.py`: 9 tests ✓
- `test_multi_format_ingester.py`: 9 tests ✓
- `test_prompt_templates.py`: 22 tests ✓
- `test_cascade_summarizer.py`: 18 tests ✓

**Total: 93+ tests covering new Cowork improvements**

## 📁 Project Structure

```
ollash/
├── src/
│   ├── agents/
│   │   ├── prompt_templates.py         # 30+ specialized prompts
│   │   ├── core_agent.py               # Base agent with analyst/writer roles
│   │   └── ...
│   ├── utils/
│   │   ├── core/
│   │   │   ├── multi_format_ingester.py      # PDF, DOCX, PPTX support
│   │   │   ├── documentation_watcher.py      # Auto-indexing daemon
│   │   │   ├── cascade_summarizer.py         # Map-Reduce pipeline
│   │   │   ├── documentation_manager.py      # Knowledge workspace hub
│   │   │   └── all_tool_definitions.py       # Integrated tool registry
│   │   └── domains/
│   │       └── bonus/
│   │           ├── cowork_tools.py          # 7 tool definitions
│   │           └── cowork_impl.py           # Implementations
│   └── web/
│       ├── static/
│       │   ├── js/artifact-renderer.js      # Frontend rendering engine
│       │   └── css/artifact-renderer.css    # Professional styling
│       └── templates/index.html             # Enhanced UI
├── tests/
│   └── unit/
│       ├── test_cowork_impl.py
│       ├── test_artifact_renderer.py
│       ├── test_cascade_summarizer.py
│       ├── test_documentation_watcher.py
│       ├── test_multi_format_ingester.py
│       ├── test_prompt_templates.py
│       └── ...
├── knowledge_workspace/                     # Dynamic knowledge store
│   ├── references/                          # Source documents
│   ├── indexed_cache/                       # ChromaDB vectors
│   └── summaries/                           # Generated summaries
├── pytest.ini                               # Test configuration
├── requirements-complete.txt                # All dependencies
├── KNOWLEDGE_WORKSPACE_GUIDE.md            # Detailed user guide
├── COWORK_IMPROVEMENTS.md                  # Architecture documentation
└── GITHUB_DEPLOYMENT.md                    # GitHub setup guide
```

## 🔧 Configuration

### Environment Variables

```bash
# Ollama configuration
export OLLASH_OLLAMA_URL=http://localhost:11434

# Embedding model (used by DocumentationManager)
export EMBEDDING_MODEL=all-minilm

# LLM models
export MINISTRAL_SMALL=ministral-3:8b   # For chunks, writers
export MINISTRAL_LARGE=ministral-3:14b  # For synthesis, analysis
```

### Document Indexing

Configure in `src/utils/core/documentation_manager.py`:
```python
# Chunk configuration
CHUNK_SIZE = 1000  # Words per chunk
OVERLAP = 200      # Overlap between chunks (20%)

# Min search relevance threshold
MIN_DISTANCE = 0.5  # 0.0-1.0 (higher = more relevant)
```

## 📚 Documentation

- [**KNOWLEDGE_WORKSPACE_GUIDE.md**](KNOWLEDGE_WORKSPACE_GUIDE.md) - Complete user guide
- [**COWORK_IMPROVEMENTS.md**](COWORK_IMPROVEMENTS.md) - Architecture & technical details
- [**GITHUB_DEPLOYMENT.md**](GITHUB_DEPLOYMENT.md) - GitHub setup instructions
- [**API Reference**](docs/) - Detailed API documentation

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Code style (PEP 8, Black formatter)
- Testing requirements (pytest, >80% coverage)
- Pull request process
- Commit message format

## 🔒 Security

See [SECURITY.md](SECURITY.md) for:
- Security best practices
- Ollama LLM model safety
- ChromaDB data isolation
- Permission profiles
- Sensitive data handling

## 📊 Benchmarks

### Performance Metrics
- Document ingestion: ~50KB/sec (PDF extraction)
- Knowledge search query: <500ms (100K+ indexed documents)
- Cascade summarization: ~2K words/minute
- Artifact rendering: <100ms client-side

### Tested Scenarios
- ✅ 50K-word document summarization with 10:1 compression
- ✅ 1000+ files auto-indexed without performance degradation
- ✅ Parallel document uploads with queued indexing
- ✅ Real-time chat interaction with artifact rendering

## 🛠️ Troubleshooting

### ChromaDB Errors

```
ValueError: "You are using a deprecated configuration of Chroma"
```

**Solution:**
```bash
pip install --upgrade chromadb
# Or: pip install chroma-db==0.4.24
```

### Document Won't Index

```python
# Check workspace status
status = doc_manager.get_knowledge_workspace_status()
print(status)
# Verify file in references/
print(list(Path("knowledge_workspace/references").iterdir()))
```

### LLM Connection Issues

```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Check models available
ollama list

# Pull required models
ollama pull ministral-3:8b
ollama pull all-minilm
```

## 📄 License

[MIT License](LICENSE) - See LICENSE file for details

## 🙏 Acknowledgments

- Anthropic Cowork feature inspiration
- ChromaDB for vector embeddings
- Ollama for local LLM inference
- PyPDF2, python-docx, python-pptx for document processing
- pytest community for testing framework

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/ollash/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_USERNAME/ollash/discussions)
- **Documentation**: [Full Docs](docs/)

---

**Ollash v2.0** - Enterprise-grade AI Agent with Knowledge Management
Built with ❤️ for knowledge workers and AI enthusiasts.
