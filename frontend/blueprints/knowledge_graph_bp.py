"""Blueprint for the Knowledge Graph Visualizer (F11)."""

import json
import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

knowledge_graph_bp = Blueprint("knowledge_graph_bp", __name__, url_prefix="/api/knowledge-graph")

_kg_builder = None


def init_app(app):
    """Initialize knowledge graph blueprint with app context."""
    global _kg_builder
    try:
        from backend.utils.core.knowledge_graph_builder import KnowledgeGraphBuilder

        root = app.config.get("ollash_root_dir")
        if root:
            from backend.core.containers import main_container

            _kg_builder = KnowledgeGraphBuilder(
                workspace_path=root / "knowledge_workspace",
                logger=main_container.core.logger(),
            )
            logger.info("Knowledge Graph builder initialized")
    except Exception as e:
        logger.warning(f"Knowledge graph init skipped: {e}")


@knowledge_graph_bp.route("/data", methods=["GET"])
def get_graph_data():
    """Return full knowledge graph as vis.js-compatible JSON."""
    if not _kg_builder:
        return jsonify({"nodes": [], "edges": [], "error": "Knowledge graph not initialized"}), 200

    try:
        graph = _kg_builder.get_graph()
        nodes = []
        for node in graph.get("nodes", {}).values():
            vis_node = {
                "id": node.get("id", ""),
                "label": node.get("label", ""),
                "group": node.get("node_type", "concept"),
                "title": json.dumps(node.get("metadata", {}), indent=2),
            }
            nodes.append(vis_node)

        edges = []
        for edge in graph.get("edges", []):
            vis_edge = {
                "from": edge.get("source", ""),
                "to": edge.get("target", ""),
                "label": edge.get("relationship", ""),
                "value": edge.get("strength", 0.5),
                "title": edge.get("context", ""),
            }
            edges.append(vis_edge)

        return jsonify({"nodes": nodes, "edges": edges})
    except Exception as e:
        logger.error(f"Error fetching graph data: {e}")
        return jsonify({"nodes": [], "edges": [], "error": str(e)}), 500


@knowledge_graph_bp.route("/search", methods=["GET"])
def search_nodes():
    """Search nodes in the knowledge graph."""
    query = request.args.get("q", "").strip()
    if not query or not _kg_builder:
        return jsonify({"results": []})

    try:
        graph = _kg_builder.get_graph()
        results = []
        query_lower = query.lower()
        for node in graph.get("nodes", {}).values():
            label = node.get("label", "").lower()
            if query_lower in label:
                results.append(
                    {
                        "id": node.get("id"),
                        "label": node.get("label"),
                        "type": node.get("node_type"),
                    }
                )
        return jsonify({"results": results[:20]})
    except Exception as e:
        return jsonify({"results": [], "error": str(e)}), 500


@knowledge_graph_bp.route("/neighborhood/<node_id>", methods=["GET"])
def get_neighborhood(node_id):
    """Get the neighborhood of a specific node."""
    depth = int(request.args.get("depth", 2))
    if not _kg_builder:
        return jsonify({"nodes": [], "edges": []})

    try:
        graph = _kg_builder.get_graph()
        visited = set()
        result_nodes = {}
        result_edges = []

        def _traverse(nid, current_depth):
            if current_depth > depth or nid in visited:
                return
            visited.add(nid)
            if nid in graph.get("nodes", {}):
                result_nodes[nid] = graph["nodes"][nid]

            for edge in graph.get("edges", []):
                if edge.get("source") == nid:
                    result_edges.append(edge)
                    _traverse(edge.get("target"), current_depth + 1)
                elif edge.get("target") == nid:
                    result_edges.append(edge)
                    _traverse(edge.get("source"), current_depth + 1)

        _traverse(node_id, 0)

        nodes = [
            {"id": n.get("id"), "label": n.get("label"), "group": n.get("node_type")} for n in result_nodes.values()
        ]
        edges = [{"from": e.get("source"), "to": e.get("target"), "label": e.get("relationship")} for e in result_edges]
        return jsonify({"nodes": nodes, "edges": edges})
    except Exception as e:
        return jsonify({"nodes": [], "edges": [], "error": str(e)}), 500
