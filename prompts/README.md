# prompts/

Templates de prompts en YAML organizados por dominio. Cargados por `PromptLoader` (singleton DB-first).

## Estructura

```
prompts/
└── domains/
    └── auto_generation/
        ├── code_gen.yaml         Generación de archivos de código
        ├── planning.yaml         Planificación de proyectos y lógica
        ├── structure.yaml        Generación de estructura de directorios
        ├── refinement.yaml       Refinamiento de código existente
        ├── review.yaml           Revisión y feedback de código
        ├── small_model_prompts.yaml  Prompts compactos para modelos ≤8B
        └── ...
```

## Formato de un prompt

```yaml
# Nombre del template: {domain}_{version}
file_gen_v2:
  system: |
    Eres un experto generador de código.
    Genera código limpio, tipado y sin TODOs.
    # {additional_context}
  user: |
    ## FILE: {file_path}
    ## PURPOSE: {purpose}
    ## LOGIC PLAN:
    {logic_plan}

    Genera el archivo completo.
```

## Cómo se cargan

`PromptLoader` (singleton en `backend/utils/core/llm/prompt_loader.py`) busca en este orden:

1. **SQLite** (`PromptRepository`) — permite editar prompts en runtime desde el Prompt Studio UI
2. **Filesystem** (`prompts/domains/...`) — fuente de verdad en git

```python
loader = PromptLoader.get_instance()
system, user = loader.get_prompt("file_gen_v2", variables={
    "file_path": "src/auth.py",
    "purpose": "JWT authentication",
    "logic_plan": "1. Validate token..."
})
```

## Prompts para modelos pequeños (≤8B)

`small_model_prompts.yaml` contiene variantes compactas de los prompts principales. Se usan automáticamente cuando `_is_small_model()` es `True` (modelos ≤8B). Características:
- Sin ejemplos extensos
- Instrucciones más cortas y directas
- Sin cadenas de razonamiento largas
- Output format simplificado

## Editar prompts en runtime

Desde el Prompt Studio (`/prompts` en la UI), los prompts se guardan en SQLite y tienen precedencia sobre los YAML. Para revertir a los YAMLs, eliminar el registro de SQLite.

## Añadir un prompt nuevo

1. Añadir entrada al YAML correspondiente o crear nuevo archivo en `prompts/domains/{dominio}/`
2. Si es para un dominio nuevo, crear el directorio
3. Usar `{variable}` para placeholders
4. Los nombres de variables deben coincidir exactamente con los `variables={}` del caller
