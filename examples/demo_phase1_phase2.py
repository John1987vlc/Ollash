#!/usr/bin/env python3
"""
Demo de las nuevas características de Ollash - Fases 1 y 2.

Demuestra:
1. Cross-Reference Analysis (Fase 1)
2. Knowledge Graph Building (Fase 1)
3. Decision Context Management (Fase 1)
4. Interactive Artifacts (Fase 2)
"""

import json
import sys
from pathlib import Path

# Agregar raíz del proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.core.agent_logger import AgentLogger
from src.utils.core.cross_reference_analyzer import CrossReferenceAnalyzer
from src.utils.core.knowledge_graph_builder import KnowledgeGraphBuilder
from src.utils.core.decision_context_manager import DecisionContextManager
from src.utils.core.artifact_manager import ArtifactManager


def setup():
    """Configuración inicial."""
    logger = AgentLogger("demo")
    config = {
        "ollama_url": "http://localhost:11434",
        "models": {
            "embedding": "all-minilm",
            "reasoning": "gpt-oss:20b"
        }
    }
    return project_root, logger, config


def demo_cross_reference():
    """Demuestra Cross-Reference Analysis."""
    print("\n" + "="*70)
    print("DEMO 1: CROSS-REFERENCE ANALYSIS")
    print("="*70)
    
    project_root, logger, config = setup()
    
    analyzer = CrossReferenceAnalyzer(project_root, logger, config)
    
    # Buscar referencias cruzadas de "API"
    print("\n🔍 Buscando referencias cruzadas de 'API' en /docs y /src...")
    references = analyzer.find_cross_references(
        "API",
        [project_root / "docs", project_root / "src"],
        context_window=100
    )
    
    print(f"\n✓ Encontradas {len(references)} referencias")
    for i, ref in enumerate(references[:3]):
        print(f"\n  Referencia {i+1}:")
        print(f"    Doc: {ref.source_doc}")
        print(f"    Relevancia: {ref.relevance_score:.2%}")
        print(f"    Contexto: {ref.context[:100]}...")


def demo_knowledge_graph():
    """Demuestra Knowledge Graph Building."""
    print("\n" + "="*70)
    print("DEMO 2: KNOWLEDGE GRAPH BUILDING")
    print("="*70)
    
    project_root, logger, config = setup()
    
    builder = KnowledgeGraphBuilder(project_root, logger, config)
    
    # Agregar relaciones
    print("\n🔗 Agregando relaciones al grafo de conocimiento...")
    
    relationships = [
        ("API", "REST", "implements", 0.95),
        ("REST", "HTTP", "uses", 0.9),
        ("HTTP", "Protocol", "is_a", 0.85),
        ("API", "Database", "communicates_with", 0.7),
        ("Database", "SQL", "can_use", 0.8),
        ("Architecture", "API", "defines", 0.75),
    ]
    
    for term1, term2, rel_type, strength in relationships:
        builder.add_relationship(term1, term2, rel_type, strength)
        print(f"  ✓ {term1} --{rel_type}--> {term2} ({strength:.0%})")
    
    # Obtener conexiones de un concepto
    print("\n🌐 Conectando concepto: 'API' (profundidad 2)...")
    connections = builder.get_concept_connections("API", max_depth=2)
    
    if connections:
        print(f"\n  Concepto: {connections['term']}")
        print(f"  Nodos conectados: {connections['total_connected_nodes']}")
        
        # Mostrar grafo en formato Mermaid
        print("\n📊 Exportando grafo a Mermaid...")
        mermaid = builder.export_graph_mermaid()
        
        if mermaid:
            print("\n--- Mermaid Code ---")
            print(mermaid)
            print("--- End Mermaid Code ---")
    
    # Generar índice temático
    print("\n📑 Generando índice temático...")
    index = builder.generate_thematic_index()
    
    print(f"\n  Temas encontrados: {len(index)}")
    for theme, terms in list(index.items())[:3]:
        print(f"    • {theme}: {len(terms)} términos")


def demo_decision_context():
    """Demuestra Decision Context Management."""
    print("\n" + "="*70)
    print("DEMO 3: DECISION CONTEXT MANAGEMENT")
    print("="*70)
    
    project_root, logger, config = setup()
    
    manager = DecisionContextManager(project_root, logger, config)
    
    # Registrar decisiones
    print("\n📋 Registrando decisiones arquitectónicas...")
    
    decisions_to_record = [
        {
            "decision": "Use Cosmos DB for user profiles",
            "reasoning": "Global distribution required, low latency access needed",
            "category": "architecture",
            "context": {
                "problem": "Multi-region user base",
                "constraints": "Sub-50ms latency SLA"
            },
            "project": "demo_project",
            "tags": ["database", "scalability", "global"]
        },
        {
            "decision": "Implement API rate limiting at gateway",
            "reasoning": "Prevent abuse and ensure fair resource allocation",
            "category": "security",
            "context": {
                "problem": "DDoS vulnerability",
                "constraint": "Must not impact legitimate users"
            },
            "project": "demo_project",
            "tags": ["security", "api", "performance"]
        },
        {
            "decision": "Add caching layer with Redis",
            "reasoning": "Reduce database load and improve response times",
            "category": "performance",
            "context": {
                "problem": "High database query volume",
                "current_latency_ms": 200
            },
            "project": "demo_project",
            "tags": ["performance", "caching", "optimization"]
        }
    ]
    
    decision_ids = []
    for dec_data in decisions_to_record:
        dec_id = manager.record_decision(**dec_data)
        decision_ids.append(dec_id)
        print(f"  ✓ Registrada: {dec_data['decision'][:50]}... (ID: {dec_id})")
    
    # Buscar decisiones similares
    print("\n🔎 Buscando decisiones similares para un problema...")
    problem = "We need to improve database performance significantly"
    similar = manager.find_similar_decisions(problem, category="performance")
    
    print(f"\n  Problema: {problem}")
    print(f"  Decisiones similares encontradas: {len(similar)}")
    
    for similar_dec in similar:
        print(f"\n    • {similar_dec.decision}")
        print(f"      Contexto: {similar_dec.context}")
    
    # Actualizar outcome
    print("\n📊 Actualizando outcome de una decisión...")
    if decision_ids:
        manager.update_outcome(
            decision_ids[0],
            {
                "success": True,
                "lesson": "Cosmos DB reduced latency from 200ms to 45ms",
                "metrics": {
                    "query_latency_ms": 45,
                    "monthly_cost": 1200,
                    "uptime_percent": 99.95
                }
            }
        )
        print(f"  ✓ Actualizado outcome para decisión {decision_ids[0]}")
    
    # Obtener estadísticas
    print("\n📈 Estadísticas del historial de decisiones:")
    stats = manager.get_statistics()
    
    print(f"\n  Total decisiones: {stats.get('total_decisions', 0)}")
    print(f"  Con outcomes: {stats.get('decisions_with_outcomes', 0)}")
    print(f"  Proyectos: {stats.get('projects_count', 0)}")
    
    if 'by_category' in stats:
        print(f"\n  Por categoría:")
        for category, count in stats['by_category'].items():
            print(f"    • {category}: {count}")


def demo_artifacts():
    """Demuestra Interactive Artifacts."""
    print("\n" + "="*70)
    print("DEMO 4: INTERACTIVE ARTIFACTS")
    print("="*70)
    
    project_root, logger, config = setup()
    
    artifact_mgr = ArtifactManager(project_root, logger, config)
    
    # Crear informe
    print("\n📄 Creando informe ejecutivo...")
    report_id = artifact_mgr.create_report(
        title="Network Performance Analysis",
        sections=[
            {
                "heading": "Executive Summary",
                "content": "Analysis shows 23% improvement in latency after implementing caching layer."
            },
            {
                "heading": "Key Findings",
                "content": "• Database query time reduced from 200ms to 45ms\n"
                          "• Cache hit rate: 78%\n"
                          "• Cost increase: 12% (acceptable trade-off)"
            },
            {
                "heading": "Recommendations",
                "content": "1. Expand caching strategy to all endpoints\n"
                          "2. Monitor cache eviction patterns\n"
                          "3. Consider distributed caching for failover"
            }
        ]
    )
    print(f"  ✓ Informe creado (ID: {report_id})")
    
    # Crear diagrama
    print("\n📊 Creando diagrama de arquitectura...")
    diagram_id = artifact_mgr.create_diagram(
        title="System Architecture Overview",
        mermaid_code="""
graph LR
    Client["Client Apps"]
    Gateway["API Gateway"]
    Cache["Redis Cache"]
    API["API Servers"]
    DB["Cosmos DB"]
    
    Client -->|HTTP/REST| Gateway
    Gateway -->|Check cache| Cache
    Cache -->|Hit/Miss| API
    API -->|Query| DB
    API -->|Store result| Cache
        """,
        diagram_type="graph"
    )
    print(f"  ✓ Diagrama creado (ID: {diagram_id})")
    
    # Crear checklist
    print("\n✅ Creando checklist de seguridad...")
    checklist_id = artifact_mgr.create_checklist(
        title="Security Checklist",
        items=[
            {
                "id": "auth",
                "label": "Implement OAuth 2.0 authentication",
                "completed": True,
                "category": "Authentication"
            },
            {
                "id": "ssl",
                "label": "Configure SSL/TLS certificates",
                "completed": True,
                "category": "Encryption"
            },
            {
                "id": "rate_limit",
                "label": "Enable API rate limiting",
                "completed": True,
                "category": "Protection"
            },
            {
                "id": "firewall",
                "label": "Setup WAF rules",
                "completed": False,
                "category": "Protection"
            },
            {
                "id": "audit",
                "label": "Enable audit logging",
                "completed": False,
                "category": "Monitoring"
            }
        ]
    )
    print(f"  ✓ Checklist creado (ID: {checklist_id})")
    
    # Crear código
    print("\n💻 Creando artefacto de código...")
    code_id = artifact_mgr.create_code_artifact(
        title="Cache Configuration Example",
        code="""import redis
from functools import wraps

cache = redis.Redis(host='localhost', port=6379)

def cached(ttl=3600):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            result = cache.get(key)
            
            if result:
                return result
            
            result = func(*args, **kwargs)
            cache.setex(key, ttl, result)
            return result
        return wrapper
    return decorator

@cached(ttl=300)
def get_user_profile(user_id):
    # Database query
    return fetch_from_db(user_id)
        """,
        language="python"
    )
    print(f"  ✓ Código creado (ID: {code_id})")
    
    # Crear comparación
    print("\n🔄 Creando tabla de comparación...")
    comparison_id = artifact_mgr.create_comparison(
        title="Database Solutions Comparison",
        items=[
            {
                "name": "PostgreSQL",
                "values": {
                    "Scalability": "Vertical (good)",
                    "Global Distribution": "Requires replication",
                    "Cost": "Low",
                    "Latency": "Depends on region",
                    "Consistency": "ACID"
                }
            },
            {
                "name": "Cosmos DB",
                "values": {
                    "Scalability": "Horizontal (excellent)",
                    "Global Distribution": "Built-in",
                    "Cost": "Higher",
                    "Latency": "Sub-10ms globally",
                    "Consistency": "Tunable"
                }
            },
            {
                "name": "DynamoDB",
                "values": {
                    "Scalability": "Automatic",
                    "Global Distribution": "DynamoDB Streams + replication",
                    "Cost": "Pay per request",
                    "Latency": "Good",
                    "Consistency": "Eventually consistent"
                }
            }
        ],
        characteristics=[
            "Scalability",
            "Global Distribution",
            "Cost",
            "Latency",
            "Consistency"
        ]
    )
    print(f"  ✓ Comparación creada (ID: {comparison_id})")
    
    # Renderizar artefactos
    print("\n🎨 Renderizando artefactos a HTML...")
    
    for art_type, art_id in [
        ("Report", report_id),
        ("Diagram", diagram_id),
        ("Checklist", checklist_id),
        ("Code", code_id),
        ("Comparison", comparison_id)
    ]:
        html = artifact_mgr.render_artifact_html(art_id)
        preview = html[:100].replace('\n', ' ')
        print(f"  ✓ {art_type} renderizado: {preview}...")
    
    # Listar todos los artefactos
    print("\n📚 Listado de artefactos creados:")
    all_artifacts = artifact_mgr.list_artifacts()
    
    print(f"\n  Total: {len(all_artifacts)} artefactos")
    
    type_counts = {}
    for art in all_artifacts:
        type_counts[art.type] = type_counts.get(art.type, 0) + 1
    
    for art_type, count in type_counts.items():
        print(f"    • {art_type}: {count}")


def main():
    """Ejecuta todas las demos."""
    print("\n" + "="*70)
    print("OLLASH - Advanced Features Demo (Phases 1 & 2)")
    print("="*70)
    
    try:
        demo_cross_reference()
        demo_knowledge_graph()
        demo_decision_context()
        demo_artifacts()
        
        print("\n" + "="*70)
        print("✅ TODAS LAS DEMOS COMPLETADAS EXITOSAMENTE")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error durante la demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
