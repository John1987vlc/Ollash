# prompts — YAML Prompt Templates

All LLM prompt templates live here as YAML files, organized by domain.

## Format

Each file contains named templates with `system:` and `user:` keys using `{variable}` placeholders:

```yaml
generate_blueprint:
  system: |
    # ROLE
    Software Architect. Output JSON only.
    ...
  user: |
    Project: {project_name}
    Description: {project_description}
```

## Loading

`PromptLoader` (singleton) loads prompts DB-first (SQLite `PromptRepository`), then falls back to filesystem YAML. Phases call `loader.load_file(path)` and access keys directly.

## Auto-Generation Prompts

| File | Keys | Used by |
|------|------|---------|
| `blueprint.yaml` | `generate_blueprint`, `generate_blueprint_small` | BlueprintPhase |
| `code_fill.yaml` | `generate_file`, `generate_file_small`, `generate_config_file` | CodeFillPhase |
| `patch.yaml` | `fix_error`, `fix_batch` | PatchPhase |
| `infra.yaml` | `infer_requirements`, `infer_package_json`, `generate_readme` | InfraPhase |
| `small_model_prompts.yaml` | Compact prompts for ≤8B models | Various phases |
| `code_gen.yaml` | Legacy generator prompts | EnhancedFileContentGenerator |
| `planning.yaml` | Planning prompts | ProjectPlanner |
| `structure.yaml` | Structure generation | StructureGenerator |

## Token Budget

System prompts must stay under ~800 tokens (~3200 chars). User messages under ~2200 tokens. Phase code truncates automatically via `BasePhase._truncate_to_tokens()`.
