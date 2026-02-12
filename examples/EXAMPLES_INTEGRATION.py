#!/usr/bin/env python3
"""
Ejemplo de integración de las nuevas capacidades Fase 1 y 2 
con el sistema de chat/agente existente.

Demuestra cómo el agente puede:
1. Analizar documentos del usuario
2. Consultar decisiones previas
3. Crear artefactos para mostrar resultados
"""

import json
from pathlib import Path
from typing import Dict, Any, List

# Simular las clases (en realidad importarías desde src)
# from src.utils.core.cross_reference_analyzer import CrossReferenceAnalyzer
# from src.utils.core.knowledge_graph_builder import KnowledgeGraphBuilder
# from src.utils.core.decision_context_manager import DecisionContextManager
# from src.utils.core.artifact_manager import ArtifactManager


class AgentWithAdvancedAnalysis:
    """
    Ejemplo de cómo un agente podría usar las nuevas capacidades.
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        
        # Estos serían instancias reales:
        # self.analyzer = CrossReferenceAnalyzer(...)
        # self.kg = KnowledgeGraphBuilder(...)
        # self.decisions = DecisionContextManager(...)
        # self.artifacts = ArtifactManager(...)
    
    def process_user_query(self, query: str) -> Dict[str, Any]:
        """
        Ejemplo: Procesa una pregunta del usuario usando las nuevas capacidades.
        
        Casos de uso:
        - "Compara la documentación con la configuración"
        - "¿Cuál fue la decisión similar anterior?"
        - "Crea un diagrama de la arquitectura"
        """
        
        # Detectar tipo de pregunta
        if "compara" in query.lower():
            return self._handle_comparison(query)
        elif "decisión" in query.lower() or "similar" in query.lower():
            return self._handle_decision_lookup(query)
        elif "diagrama" in query.lower() or "dibuja" in query.lower():
            return self._handle_diagram_request(query)
        elif "checklist" in query.lower() or "lista" in query.lower():
            return self._handle_checklist_request(query)
        else:
            return {"response": "Pregunta no reconocida"}
    
    def _handle_comparison(self, query: str) -> Dict[str, Any]:
        """
        Ejemplo: Usuario pregunta comparar documentación con configuración.
        
        Usuario: "Compara el manual de red con la configuración actual"
        """
        return {
            "action": "cross_reference_analysis",
            "method": "compare_documents",
            "docs": ["docs/network_manual.md", "config/settings.json"],
            "explanation": "Analizando inconsistencias entre documentación teórica y configuración real...",
            "expected_output": {
                "artifact_type": "report",
                "title": "Network Manual vs Current Configuration",
                "sections": [
                    "Similarities Found",
                    "Key Differences",
                    "Configuration Gaps",
                    "Recommendations"
                ]
            }
        }
    
    def _handle_decision_lookup(self, query: str) -> Dict[str, Any]:
        """
        Ejemplo: Usuario pregunta sobre decisiones similares.
        
        Usuario: "¿Hay alguna decisión anterior similar sobre base de datos?"
        """
        return {
            "action": "decision_context_lookup",
            "method": "find_similar_decisions",
            "query": query,
            "explanation": "Buscando en historial de decisiones previas...",
            "expected_output": {
                "artifact_type": "comparison",
                "title": "Similar Architecture Decisions",
                "items": [
                    {"name": "Decision A", "values": {"Date": "2025-12-10", "Outcome": "Success"}},
                    {"name": "Decision B", "values": {"Date": "2025-11-20", "Outcome": "Success"}},
                    {"name": "Current", "values": {"Date": "2026-02-11", "Outcome": "Pending"}}
                ]
            }
        }
    
    def _handle_diagram_request(self, query: str) -> Dict[str, Any]:
        """
        Ejemplo: Usuario pide un diagrama.
        
        Usuario: "Dibuja la arquitectura del sistema según la documentación"
        """
        return {
            "action": "artifact_creation",
            "method": "create_diagram",
            "explanation": "Analizando documentación de arquitectura y creando diagrama...",
            "expected_output": {
                "artifact_type": "diagram",
                "title": "System Architecture",
                "content": {
                    "mermaid_code": """
                    graph LR
                        Client["Client Apps"]
                        Gateway["API Gateway"]
                        API["API Servers"]
                        DB["Cosmos DB"]
                        
                        Client -->|REST| Gateway
                        Gateway -->|Route| API
                        API -->|Query| DB
                    """,
                    "diagram_type": "graph"
                }
            }
        }
    
    def _handle_checklist_request(self, query: str) -> Dict[str, Any]:
        """
        Ejemplo: Usuario pide un checklist.
        
        Usuario: "Crea un checklist de seguridad del sistema"
        """
        return {
            "action": "artifact_creation",
            "method": "create_checklist",
            "explanation": "Creando checklist de seguridad basado en mejores prácticas...",
            "expected_output": {
                "artifact_type": "checklist",
                "title": "Security Checklist",
                "content": {
                    "items": [
                        {"id": "auth", "label": "Implement OAuth 2.0", "completed": False},
                        {"id": "ssl", "label": "Configure SSL/TLS", "completed": True},
                        {"id": "rate_limit", "label": "API Rate Limiting", "completed": False},
                        {"id": "firewall", "label": "Setup WAF", "completed": False},
                        {"id": "audit", "label": "Audit Logging", "completed": True}
                    ]
                }
            }
        }


def example_workflow():
    """
    Ejemplo de un workflow completo usando las nuevas capacidades.
    """
    
    print("\n" + "="*70)
    print("EJEMPLO: Cómo usar las nuevas capacidades en workflows")
    print("="*70)
    
    project_root = Path.cwd()
    agent = AgentWithAdvancedAnalysis(project_root)
    
    # Caso 1: Análisis de documentación
    print("\n1️⃣  COMPARAR DOCUMENTACIÓN CON CONFIGURACIÓN")
    print("-" * 70)
    
    query1 = "Compara el manual de red con la configuración actual"
    print(f"Usuario: {query1}")
    
    result1 = agent.process_user_query(query1)
    print(f"\nAgent Action: {result1['action']}")
    print(f"Method: {result1['method']}")
    print(f"Explanation: {result1['explanation']}")
    print(f"\nArtefacto que se crearía:")
    print(f"  - Tipo: {result1['expected_output']['artifact_type']}")
    print(f"  - Título: {result1['expected_output']['title']}")
    print(f"  - Secciones: {', '.join(result1['expected_output']['sections'])}")
    
    # Caso 2: Consulta de decisiones
    print("\n\n2️⃣  BUSCAR DECISIONES SIMILARES")
    print("-" * 70)
    
    query2 = "¿Hay alguna decisión anterior sobre escalabilidad de base de datos?"
    print(f"Usuario: {query2}")
    
    result2 = agent.process_user_query(query2)
    print(f"\nAgent Action: {result2['action']}")
    print(f"Method: {result2['method']}")
    print(f"Explanation: {result2['explanation']}")
    print(f"\nArtefacto que se crearía:")
    print(f"  - Tipo: {result2['expected_output']['artifact_type']}")
    print(f"  - Título: {result2['expected_output']['title']}")
    print(f"  - Ítems a comparar: {len(result2['expected_output']['items'])}")
    
    # Caso 3: Creación de diagrama
    print("\n\n3️⃣  CREAR DIAGRAMA DE ARQUITECTURA")
    print("-" * 70)
    
    query3 = "Dibuja la arquitectura del sistema basada en la documentación"
    print(f"Usuario: {query3}")
    
    result3 = agent.process_user_query(query3)
    print(f"\nAgent Action: {result3['action']}")
    print(f"Method: {result3['method']}")
    print(f"Explanation: {result3['explanation']}")
    print(f"\nArtefacto que se crearía:")
    print(f"  - Tipo: {result3['expected_output']['artifact_type']}")
    print(f"  - Título: {result3['expected_output']['title']}")
    print(f"  - Tipo de diagrama: {result3['expected_output']['content']['diagram_type']}")
    
    # Caso 4: Checklist interactivo
    print("\n\n4️⃣  CREAR CHECKLIST DE SEGURIDAD")
    print("-" * 70)
    
    query4 = "Crea un checklist de seguridad del sistema"
    print(f"Usuario: {query4}")
    
    result4 = agent.process_user_query(query4)
    print(f"\nAgent Action: {result4['action']}")
    print(f"Method: {result4['method']}")
    print(f"Explanation: {result4['explanation']}")
    print(f"\nArtefacto que se crearía:")
    print(f"  - Tipo: {result4['expected_output']['artifact_type']}")
    print(f"  - Título: {result4['expected_output']['title']}")
    print(f"  - Items: {len(result4['expected_output']['content']['items'])}")


def example_integration_with_llm():
    """
    Ejemplo de cómo integrar con un LLM para respuestas inteligentes.
    """
    
    print("\n" + "="*70)
    print("EXEMPLO: Integración con LLM para respuestas inteligentes")
    print("="*70)
    
    # Pseudocódigo de cómo sería:
    
    workflow = """
    
    1. Usuario pregunta en el chat:
       "¿Debería usar Cosmos DB o PostgreSQL para los datos de usuarios?"
    
    2. Agent detecta que es una pregunta de arquitectura
    
    3. Agent ejecuta:
       a) decision_manager.find_similar_decisions(query)
          → Encuentra 2 decisiones similares previas
       
       b) artifact_mgr.create_comparison(
           items=["Cosmos DB", "PostgreSQL", "Previous Decision A"],
           characteristics=["Cost", "Scalability", "GeoDistribution", "Latency"]
       )
          → Crea tabla comparativa interactiva
       
       c) LLM genera respuesta:
          "Basándote en decisión similar del Proyecto A (Dic 2025):
           Usamos Cosmos DB y redujo latencia de 200ms a 45ms,
           pero el costo aumentó un 15%.
           
           Recomendación: Usa Cosmos DB si la latencia es crítica.
           Si el costo es prioritario: PostgreSQL + caching + read replicas."
       
       d) System retorna al usuario:
          - Respuesta conversacional (chat)
          - Tabla comparativa interactiva (panel derecho)
          - Link a documentación previas decisiones
    
    """
    
    print(workflow)


def example_api_calls():
    """
    Ejemplo de cómo se verían las llamadas API.
    """
    
    print("\n" + "="*70)
    print("EJEMPLO: Cómo se vería en llamadas API")
    print("="*70)
    
    # Simular análisis de documentación
    print("\n📡 REQUEST 1: Comparar documentos")
    print("-" * 70)
    
    request1 = {
        "method": "POST",
        "endpoint": "/api/analysis/cross-reference/compare",
        "payload": {
            "doc1_path": "docs/network_manual.md",
            "doc2_path": "config/settings.json"
        }
    }
    
    print(f"{request1['method']} {request1['endpoint']}")
    print(json.dumps(request1['payload'], indent=2))
    
    response1 = {
        "similarities": ["Both mention 'protocol', 'configuration'"],
        "differences": [
            {"term": "timeout_ms", "in_doc1": False, "in_doc2": True},
            {"term": "DNS_resolver", "in_doc1": True, "in_doc2": False}
        ],
        "similarity_score": 0.67,
        "gaps": {
            "configured_but_not_documented": [
                {"key": "rate_limit", "value": 1000}
            ],
            "documented_but_not_configured": [
                {"key": "ssl_version", "severity": "warning"}
            ]
        }
    }
    
    print(f"\n✅ RESPONSE:")
    print(json.dumps(response1, indent=2)[:200] + "...\n")
    
    # Registrar decisión
    print("\n📡 REQUEST 2: Registrar decisión")
    print("-" * 70)
    
    request2 = {
        "method": "POST",
        "endpoint": "/api/analysis/decisions/record",
        "payload": {
            "decision": "Use Cosmos DB for user profiles",
            "reasoning": "Global distribution, <50ms latency requirement",
            "category": "architecture",
            "context": {
                "problem": "Multi-region user base",
                "constraints": "SLA: <50ms"
            },
            "project": "current_project",
            "tags": ["database", "scalability"]
        }
    }
    
    print(f"{request2['method']} {request2['endpoint']}")
    print(json.dumps(request2['payload'], indent=2))
    
    response2 = {
        "status": "success",
        "decision_id": "dec_a1b2c3d4",
        "timestamp": "2026-02-11T10:30:00"
    }
    
    print(f"\n✅ RESPONSE:")
    print(json.dumps(response2, indent=2))
    
    # Crear artefacto
    print("\n\n📡 REQUEST 3: Crear artefacto (informe)")
    print("-" * 70)
    
    request3 = {
        "method": "POST",
        "endpoint": "/api/artifacts/report",
        "payload": {
            "title": "Performance Optimizations Applied",
            "sections": [
                {
                    "heading": "Executive Summary",
                    "content": "Implemented caching layer, reduced latency by 45%"
                },
                {
                    "heading": "Technical Details",
                    "content": "Redis 7.0 deployed, TTL set to 24h for user profiles"
                }
            ]
        }
    }
    
    print(f"{request3['method']} {request3['endpoint']}")
    print(json.dumps(request3['payload'], indent=2)[:250] + "...\n")
    
    response3 = {
        "status": "created",
        "artifact_id": "art_e5f6g7h8",
        "type": "report"
    }
    
    print(f"✅ RESPONSE:")
    print(json.dumps(response3, indent=2))


def main():
    """Ejecuta todos los ejemplos."""
    
    print("\n" + "🎓 "*35)
    print("\nEJEMPLOS DE INTEGRACIÓN - Fase 1 y 2")
    print("\n" + "🎓 "*35)
    
    example_workflow()
    example_integration_with_llm()
    example_api_calls()
    
    print("\n" + "="*70)
    print("✅ CONCLUSIÓN")
    print("="*70)
    print("""
Las nuevas capacidades se integran perfectamente con workflows existentes.

El agente puede ahora:
1. Analizar múltiples fuentes de información automáticamente
2. Recordar decisiones previas y aprender de ellas
3. Generar visualizaciones interactivas
4. Proporcionar respuestas más contextualizadas

Todo sin cambiar la API básica del chat.
    """)


if __name__ == "__main__":
    main()
