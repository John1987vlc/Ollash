from flask import Blueprint, jsonify, request
from backend.core.containers import main_container
from backend.utils.core.io.doc_translator import SUPPORTED_LANGUAGES, DocTranslator
from backend.utils.core.system.agent_logger import AgentLogger

translator_bp = Blueprint("translator", __name__)


@translator_bp.route("/api/translator/languages", methods=["GET"])
def get_languages():
    return jsonify({"languages": SUPPORTED_LANGUAGES})


@translator_bp.route("/api/translator/translate", methods=["POST"])
def translate_file():
    """Translates a project file to a target language."""
    data = request.json
    project_name = data.get("project_name")
    file_path = data.get("file_path")
    target_lang = data.get("target_lang")

    if not all([project_name, file_path, target_lang]):
        return jsonify({"error": "Missing parameters"}), 400

    root = main_container.core.ollash_root_dir()
    full_path = root / "generated_projects" / "auto_agent_projects" / project_name / file_path

    if not full_path.exists():
        return jsonify({"error": "File not found"}), 404

    try:
        content = full_path.read_text(encoding="utf-8")

        # Get LLM client from container
        llm_manager = main_container.services.llm_client_manager()
        client = llm_manager.get_default_client()

        translator = DocTranslator(client, AgentLogger("translator_api", root / "logs"))

        # Choose method based on extension
        import asyncio

        if full_path.suffix == ".md":
            translated = asyncio.run(translator.translate_readme(content, target_lang))
        else:
            translated = asyncio.run(translator.translate_code_comments(content, "en", target_lang))

        # Save as new file
        output_name = translator.get_output_filename(full_path.name, target_lang)
        output_path = full_path.parent / output_name
        output_path.write_text(translated, encoding="utf-8")

        return jsonify({"status": "success", "output_file": output_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
