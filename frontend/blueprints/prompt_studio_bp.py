from flask import Blueprint, render_template, request, jsonify
from pathlib import Path
import json

prompt_studio_bp = Blueprint('prompt_studio', __name__, url_prefix='/prompts')

_repository = None
_prompts_dir = None

def init_app(app):
    global _repository, _prompts_dir
    from backend.core.containers import main_container
    try:
        if hasattr(main_container, "core"):
            _repository = main_container.core.prompt_repository()
        elif hasattr(main_container, "prompt_repository"):
            _repository = main_container.prompt_repository()
        
        _prompts_dir = Path(app.config.get('ollash_root_dir', '.')) / "prompts"
    except Exception as e:
        app.logger.error(f"Failed to initialize Prompt Studio repository: {e}")

@prompt_studio_bp.route('/')
def prompt_studio():
    return render_template('pages/prompts.html')

@prompt_studio_bp.route('/api/roles', methods=['GET'])
def list_roles():
    """List all available roles (from filesystem and DB)."""
    roles = set()
    
    # 1. From filesystem
    if _prompts_dir and _prompts_dir.exists():
        for f in _prompts_dir.glob("**/*.yaml"):
            roles.add(f.stem)
        for f in _prompts_dir.glob("**/*.json"):
            roles.add(f.stem)
            
    # 2. Add any roles only in DB (though they usually match files)
    # (Optional: implement list_all_roles in repository)
    
    return jsonify({"roles": sorted(list(roles))})

@prompt_studio_bp.route('/api/load/<role>', methods=['GET'])
def load_role_prompt(role):
    """Load the active prompt for a role (DB preferred, then filesystem)."""
    # 1. Try DB
    if _repository:
        active = _repository.get_active_prompt(role)
        if active:
            return jsonify({"role": role, "prompt": active, "source": "database"})
            
    # 2. Try Filesystem fallback
    if _prompts_dir:
        # Search for yaml then json
        for ext in ['.yaml', '.json']:
            # Search recursively
            found = list(_prompts_dir.glob(f"**/{role}{ext}"))
            if found:
                try:
                    with open(found[0], 'r', encoding='utf-8') as f:
                        if ext == '.yaml':
                            import yaml
                            content = yaml.safe_load(f)
                        else:
                            content = json.load(f)
                        
                        # Return string representation for editor
                        text = content.get('prompt') or content.get('system_prompt') or json.dumps(content, indent=2)
                        return jsonify({"role": role, "prompt": text, "source": "filesystem"})
                except Exception as e:
                    return jsonify({"error": str(e)}), 500
                    
    return jsonify({"error": "Prompt not found"}), 404

@prompt_studio_bp.route('/api/save', methods=['POST'])
def save_prompt():
    """Save a modified prompt to the database."""
    data = request.json
    role = data.get('role')
    prompt_text = data.get('prompt')
    
    if not role or not prompt_text:
        return jsonify({"error": "Missing role or prompt text"}), 400
        
    if _repository:
        try:
            prompt_id = _repository.save_prompt(role, prompt_text, is_active=True)
            return jsonify({"success": True, "id": prompt_id, "message": f"Prompt for '{role}' saved and activated."})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "Repository not available"}), 503

@prompt_studio_bp.route('/api/history/<role>', methods=['GET'])
def get_history(role):
    """Get version history for a role from the DB."""
    if _repository:
        history = _repository.get_history(role)
        return jsonify({"history": history})
    return jsonify({"history": []})

@prompt_studio_bp.route('/api/validate', methods=['POST'])
def validate_prompt():
    """Validation logic."""
    data = request.json
    prompt_text = data.get('prompt', '')
    
    warnings = []
    if len(prompt_text) < 50:
        warnings.append({"severity": "warning", "message": "Prompt is too short. Context may be lost."})
    if "ignore previous instructions" in prompt_text.lower():
        warnings.append({"severity": "critical", "message": "Potential Prompt Injection detected."})
    if "{{" not in prompt_text and "{" not in prompt_text:
        warnings.append({"severity": "info", "message": "No dynamic variables found."})

    return jsonify({"valid": len(warnings) == 0, "warnings": warnings})
