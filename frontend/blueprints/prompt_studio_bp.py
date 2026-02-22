from flask import Blueprint, render_template, request, jsonify

prompt_studio_bp = Blueprint('prompt_studio', __name__, url_prefix='/prompts')

@prompt_studio_bp.route('/')
def prompt_studio():
    return render_template('pages/prompts.html')

@prompt_studio_bp.route('/api/validate', methods=['POST'])
def validate_prompt():
    """Mock validation of a prompt."""
    data = request.json
    prompt_text = data.get('prompt', '')
    
    warnings = []
    
    if len(prompt_text) < 50:
        warnings.append({"severity": "warning", "message": "Prompt is too short. Context may be lost."})
    
    if "ignore previous instructions" in prompt_text.lower():
        warnings.append({"severity": "critical", "message": "Potential Prompt Injection detected."})
        
    if "{{" not in prompt_text:
        warnings.append({"severity": "info", "message": "No dynamic variables ({{variable}}) found."})

    return jsonify({"valid": len(warnings) == 0, "warnings": warnings})

def init_app(app):
    pass
