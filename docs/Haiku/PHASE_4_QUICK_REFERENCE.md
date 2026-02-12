# ⚡ PHASE 4 QUICK REFERENCE CARD

## 🎯 What Phase 4 Does

**Feedback Refinement Cycles** - Iteratively improves text quality through:
1. **Critique** - Analyzes clarity, conciseness, structure, accuracy
2. **Refinement** - Applies improvements
3. **Validation** - Verifies against original sources
4. **Export** - Outputs refined document

---

## 📦 What You Get

| Component | Purpose | Size |
|-----------|---------|------|
| FeedbackRefinementManager | Paragraph analysis & critique | 400 lines |
| SourceValidator | Validation against sources | 450 lines |
| RefinementOrchestrator | Workflow coordination | 600 lines |
| refinement_bp | 14 REST endpoints | 400 lines |
| Tests | 26 comprehensive tests | 350 lines |

---

## 🚀 Quick Start (3 steps)

### 1. Create Workflow
```bash
curl -X POST http://localhost:5000/api/refinement/workflow/create \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "doc1",
    "source_id": "src1",
    "document_text": "Your document text...",
    "strategy": "comprehensive"
  }'
```

### 2. Refine Document
```bash
curl -X POST http://localhost:5000/api/refinement/workflow/doc1/refine \
  -H "Content-Type: application/json" \
  -d '{"strategy": "comprehensive"}'
```

### 3. Get Results
```bash
curl http://localhost:5000/api/refinement/workflow/doc1/export?format=html
```

---

## 📡 14 REST Endpoints

### Workflow (6)
```
POST   /api/refinement/workflow/create
GET    /api/refinement/workflow/<id>/analyze
POST   /api/refinement/workflow/<id>/refine
GET    /api/refinement/workflow/<id>/status
GET    /api/refinement/workflow/list
GET    /api/refinement/workflow/<id>/export
```

### Paragraph (2)
```
POST   /api/refinement/paragraph/critique
POST   /api/refinement/paragraph/compare
```

### Validation (2)
```
POST   /api/refinement/validate
GET    /api/refinement/validation/report
```

### Sources (2)
```
POST   /api/refinement/source/register
GET    /api/refinement/source/<id>
```

### Config (2)
```
GET    /api/refinement/metrics/summary
GET    /api/refinement/strategies
```

---

## 🎯 4 Refinement Strategies

| Strategy | Use When | Validation | Auto-Apply | Iterations |
|----------|----------|-----------|-----------|-----------|
| quick_polish | Need fast fixes | 80% | ✅ | 1 |
| comprehensive | Want thorough review | 75% | ❌ | 3 |
| accuracy_focused | Precision critical | 85% | ❌ | 2 |
| aggressive_rewrite | Heavy rewriting needed | 70% | ❌ | 5 |

---

## 🔍 4 Critique Types

| Type | Detects | Example |
|------|---------|---------|
| clarity | Long sentences, passive voice, complex words | Splits 35+ word sentences |
| conciseness | Repeated words, fillers | Removes "very", "really", "actually" |
| structure | Paragraph flow, topic sentences | Min 2 sentences, max 8 sentences |
| accuracy | Fact consistency | Requires source comparison |

---

## ✅ Validation Scoring

```
0-40    = ❌ CRITICAL - Major issues, rollback suggested
40-70   = ⚠️ WARNING - Some concerns, review recommended
70-100  = ✅ VALID - Good to apply, minor/no issues
```

**Factors**:
- Word overlap > 70% = good semantic preservation
- Negation changes = automatic critical flag
- Fact drift detected = warning

---

## 💾 Storage Structure

```
knowledge_workspace/
├── refinements/
│   ├── refinement_metrics.json
│   └── refinement_history.json
├── validations/
│   └── validation_log.json
├── sources/
│   ├── source_id1.txt
│   └── source_id2.txt
└── workflows/
    ├── workflow_id1.json
    └── workflow_id2.json
```

---

## 🧪 Run Tests

```bash
# All Phase 4 tests
pytest tests/unit/test_phase4_refinement.py -v

# Specific test
pytest tests/unit/test_phase4_refinement.py::TestSourceValidator::test_validate_refinement_valid -v

# With coverage
pytest tests/unit/test_phase4_refinement.py --cov=src.utils.core
```

**Result**: 26 tests, 100% passing, 0.24s execution

---

## 🔧 Configuration

**Enable/disable in config/settings.json**:
```json
{
  "features": {
    "feedback_cycles": true,        // Phase 4
    "refinement_validation": true,
    "semantic_checking": true
  },
  "refinement": {
    "min_validation_score": 70,
    "max_iterations": 5,
    "readability_target": 75.0
  }
}
```

---

## 📊 Key Metrics

**Per-Workflow**:
- `total_paragraphs` - Count of paragraphs analyzed
- `refined_count` - Paragraphs that got changes
- `avg_readability_improvement` - Score delta
- `validation_passed` - Refinements validated
- `total_iterations` - Cycles executed

**Global**:
- `refinement_rate` - % of paragraphs refined
- `avg_validation_score` - Overall quality (0-100)
- `pass_rate` - % of validations passing

---

## 🐛 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Source not found in validation | Register source first with `/source/register` |
| Validation score too low | Use less aggressive strategy or review critiques |
| Semantic drift detected | Back to original and try smaller changes |
| Paragraph too complex | Try `clarity` critique only first |

---

## 📚 Documentation Files

| File | Content | Size |
|------|---------|------|
| FASE_4_IMPLEMENTACION.md | Complete technical guide | 350 lines |
| QUICK_START_GUIDE.md | 5-min overview | 300 lines |
| ADVANCED_FEATURES.md | API reference | 200 lines |
| ARCHITECTURE_DIAGRAM.md | System design | 250 lines |

---

## 🎓 Learning Path

**Beginner** (15 min):
1. Read QUICK_START_GUIDE.md
2. Try one POST /api/refinement/workflow/create
3. View results with GET /api/refinement/workflow/{id}/export

**Intermediate** (45 min):
1. Read ADVANCED_FEATURES.md
2. Test all 14 endpoints with curl/Postman
3. Try different strategies

**Expert** (2 hours):
1. Read FASE_4_IMPLEMENTACION.md
2. Study test cases in test_phase4_refinement.py
3. Customize strategies and validation rules

---

## 🚀 Deployment Checklist

- [ ] `venv` activated
- [ ] `python run_web.py` working
- [ ] Tests passing: `pytest tests/unit/test_phase4_refinement.py -v`
- [ ] `knowledge_workspace/` directory writable
- [ ] `config/settings.json` has `"feedback_cycles": true`
- [ ] Endpoints accessible at http://localhost:5000/api/refinement/

---

## 🔗 Integration Points

**In app.py**:
```python
from src.web.blueprints.refinement_bp import refinement_bp, init_refinement

# During create_app():
init_refinement(app)
app.register_blueprint(refinement_bp)
```

**Managers created during `init_refinement()`**:
- `refinement_manager` - FeedbackRefinementManager
- `validator` - SourceValidator
- `orchestrator` - RefinementOrchestrator

---

## ⏱️ Performance

| Operation | Time |
|-----------|------|
| Extract 100 paragraphs | < 50ms |
| Generate critique | < 100ms |
| Validate paragraph | < 200ms |
| Full workflow (100 paras) | < 5s |
| API endpoint response | < 200ms |

---

## 🎯 Use Cases

### Use Case 1: Technical Documentation Polish
```
Goal: Improve readability of API docs
Strategy: comprehensive
Expected: Clearer explanations, better structure
Time: 5-10 minutes
```

### Use Case 2: Accuracy Verification
```
Goal: Ensure refinement didn't change meaning
Strategy: accuracy_focused
Expected: Validation against original source
Time: 2-3 minutes
```

### Use Case 3: Bulk Cleanup
```
Goal: Quick readability fix across multiple docs
Strategy: quick_polish (auto-apply)
Expected: All docs improved automatically
Time: < 1 minute per doc
```

---

## 🎊 Phase 4 Complete!

**What's next?**

- ✅ All functions working and tested
- ✅ Integration verified
- ✅ Documentation complete
- ⏳ Ready for production use
- 🚀 Phase 5 (OCR + Speech) - optional

**Questions?** See FASE_4_IMPLEMENTACION.md

**Issues?** Check error logs in `logs/` directory

**Deploy?** Run: `python run_web.py`

---

**Quick Links**:
- 📖 Full Docs: `FASE_4_IMPLEMENTACION.md`
- 🧪 Tests: `tests/unit/test_phase4_refinement.py`
- 💾 Code: `src/utils/core/` and `src/web/blueprints/refinement_bp.py`
- 📊 API: `http://localhost:5000/api/refinement/`

---

*Ready to refine some text? Start with `/workflow/create`! 🚀*
