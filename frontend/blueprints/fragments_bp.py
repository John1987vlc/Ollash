from flask import Blueprint, jsonify, request
from backend.core.containers import main_container
from backend.utils.core.memory.fragment_cache import FragmentCache
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.structured_logger import StructuredLogger

fragments_bp = Blueprint("fragments", __name__)
_cache: FragmentCache = None


def get_cache():
    global _cache
    if _cache is None:
        root = main_container.core.ollash_root_dir()
        sl = StructuredLogger(root / "logs" / "fragments.log")
        _cache = FragmentCache(root / ".cache" / "fragments", AgentLogger(sl, "fragments_api"))
    return _cache


@fragments_bp.route("/api/fragments", methods=["GET"])
def list_fragments():
    cache = get_cache()
    # Convert memory cache to list
    fragments = []
    for key, data in cache._memory_cache.items():
        fragments.append(
            {
                "key": key,
                "type": data.get("fragment_type"),
                "language": data.get("language"),
                "content": data.get("content"),
                "hits": data.get("hits"),
                "favorite": data.get("metadata", {}).get("favorite", False),
            }
        )
    return jsonify({"fragments": fragments})


@fragments_bp.route("/api/fragments/favorite", methods=["POST"])
def favorite_fragment():
    data = request.json
    key = data.get("key")
    is_favorite = data.get("favorite", True)

    cache = get_cache()
    if key in cache._memory_cache:
        if "metadata" not in cache._memory_cache[key]:
            cache._memory_cache[key]["metadata"] = {}
        cache._memory_cache[key]["metadata"]["favorite"] = is_favorite
        cache._save_to_disk()
        return jsonify({"status": "success"})
    return jsonify({"error": "Fragment not found"}), 404
