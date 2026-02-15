"""
Knowledge Graph Builder for Ollash.

Construye un grafo de conocimiento que mapea relaciones entre términos,
documentos y secciones. Facilita navegación conceptual y descubrimiento
de conexiones entre diferentes partes del sistema.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from collections import defaultdict

from backend.utils.core.agent_logger import AgentLogger


@dataclass
class GraphNode:
    """Representa un nodo en el grafo de conocimiento."""
    id: str
    label: str
    node_type: str  # 'term', 'document', 'section', 'concept'
    metadata: Dict[str, Any]
    created_at: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class GraphEdge:
    """Representa una arista en el grafo de conocimiento."""
    source: str
    target: str
    relationship: str  # 'defines', 'references', 'relates_to', 'contradicts', 'extends'
    strength: float  # 0.0 a 1.0, qué tan fuerte es la relación
    context: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class KnowledgeGraphBuilder:
    """
    Construye y mantiene un grafo de conocimiento basado en documentación
    y código del proyecto.
    
    Estructura:
    - Nodes: Términos, documentos, secciones, conceptos
    - Edges: Relaciones entre nodos (defines, references, relates_to, etc.)
    """
    
    def __init__(self, project_root: Path, logger: AgentLogger, config: Optional[Dict] = None):
        self.project_root = project_root
        self.logger = logger
        self.config = config or {}
        
        # Estructura del grafo
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.node_index: Dict[str, str] = {}  # label -> id para búsqueda rápida
        self.relationships: Dict[str, Set[str]] = defaultdict(set)  # node_id -> {related_ids}
        
        # Paths
        self.graph_dir = project_root / "knowledge_workspace" / "graphs"
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        self.graph_file = self.graph_dir / "knowledge_graph.json"
        self.index_file = self.graph_dir / "thematic_index.json"
        
        # Cargar grafo existente si existe
        self._load_graph()
        
        self.logger.info("✓ KnowledgeGraphBuilder initialized")
    
    def build_from_documentation(self, doc_paths: Optional[List[Path]] = None) -> Dict[str, Any]:
        """
        Construye el grafo a partir de documentación.
        
        Args:
            doc_paths: Rutas específicas a documentos. Si None, busca en docs/
            
        Returns:
            Estadísticas de construcción
        """
        try:
            if doc_paths is None:
                doc_dir = self.project_root / "docs"
                if not doc_dir.exists():
                    self.logger.warning("No docs/ directory found")
                    return {}
                doc_paths = list(doc_dir.rglob("*.md")) + list(doc_dir.rglob("*.txt"))
            
            stats = {
                'nodes_created': 0,
                'edges_created': 0,
                'documents_processed': 0,
                'timestamp': self._get_timestamp()
            }
            
            # Procesar cada documento
            for doc_path in doc_paths:
                try:
                    content = self._read_document(doc_path)
                    if not content:
                        continue
                    
                    # Crear nodo para el documento
                    doc_node_id = self._add_document_node(doc_path, content)
                    stats['nodes_created'] += 1
                    
                    # Extraer secciones
                    sections = self._extract_sections(content, doc_path)
                    for section in sections:
                        section_node_id = self._add_section_node(section, doc_path)
                        self._add_edge(
                            doc_node_id, section_node_id,
                            'contains', 0.95,
                            context="Section in document"
                        )
                        stats['nodes_created'] += 1
                        stats['edges_created'] += 1
                    
                    # Extraer términos y conceptos
                    terms = self._extract_terms(content)
                    for term in terms:
                        term_node_id = self._add_term_node(term, content)
                        self._add_edge(
                            doc_node_id, term_node_id,
                            'mentions', 0.7,
                            context=f"Term mentioned in {doc_path.name}"
                        )
                        stats['nodes_created'] += 1
                        stats['edges_created'] += 1
                    
                    stats['documents_processed'] += 1
                    
                except Exception as e:
                    self.logger.warning(f"Error processing {doc_path}: {e}")
            
            # Buscar relaciones entre términos
            self._build_term_relationships()
            stats['edges_created'] = len(self.edges)
            
            # Guardar grafo
            self._save_graph()
            
            self.logger.info(
                f"✓ Knowledge graph built: "
                f"{stats['nodes_created']} nodes, "
                f"{stats['edges_created']} edges"
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error building knowledge graph: {e}")
            return {}
    
    def add_relationship(
        self,
        term1: str,
        term2: str,
        relationship: str,
        strength: float = 0.7,
        context: Optional[str] = None
    ) -> bool:
        """
        Añade una relación entre dos términos.
        
        Args:
            term1: Primer término
            term2: Segundo término
            relationship: Tipo de relación
            strength: Fuerza de la relación (0.0-1.0)
            context: Contexto de la relación
        """
        try:
            # Buscar o crear nodos
            node1_id = self.node_index.get(term1)
            if not node1_id:
                node1_id = self._add_term_node(term1, "")
            
            node2_id = self.node_index.get(term2)
            if not node2_id:
                node2_id = self._add_term_node(term2, "")
            
            # Añadir arista
            self._add_edge(node1_id, node2_id, relationship, strength, context)
            
            self.logger.debug(f"Added relationship: {term1} --{relationship}--> {term2}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding relationship: {e}")
            return False
    
    def get_concept_connections(
        self,
        term: str,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Obtiene todas las conexiones de un concepto hasta cierta profundidad.
        
        Args:
            term: Término a consultar
            max_depth: Profundidad máxima de búsqueda
            
        Returns:
            Estructura con el término central y sus conexiones
        """
        try:
            node_id = self.node_index.get(term)
            if not node_id:
                self.logger.debug(f"Term '{term}' not found in graph")
                return {}
            
            connections = self._traverse_graph(node_id, max_depth)
            
            result = {
                'term': term,
                'node_id': node_id,
                'connections': connections,
                'total_connected_nodes': len(set(
                    c['target_id'] for conn in connections.values()
                    for c in conn.get('edges', [])
                )),
                'timestamp': self._get_timestamp()
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting concept connections: {e}")
            return {}
    
    def find_knowledge_paths(
        self,
        start_term: str,
        end_term: str
    ) -> List[List[Tuple[str, str]]]:
        """
        Busca caminos de conocimiento entre dos términos.
        
        Returns:
            Lista de rutas (cada ruta es lista de (nodo, relación))
        """
        try:
            start_id = self.node_index.get(start_term)
            end_id = self.node_index.get(end_term)
            
            if not start_id or not end_id:
                return []
            
            # BFS para encontrar caminos
            paths = []
            queue = [(start_id, [start_id])]
            
            while queue:
                current, path = queue.pop(0)
                
                if current == end_id:
                    paths.append(path)
                    continue
                
                if len(path) > 5:  # Limitar profundidad
                    continue
                
                # Buscar vecinos
                for edge in self.edges:
                    if edge.source == current and edge.target not in path:
                        queue.append((edge.target, path + [edge.target]))
            
            # Convertir ruta de IDs a términos
            readable_paths = []
            for path in paths:
                readable_path = []
                for i, node_id in enumerate(path):
                    node = self.nodes.get(node_id)
                    if node:
                        readable_path.append(node.label)
                readable_paths.append(readable_path)
            
            self.logger.info(f"Found {len(readable_paths)} path(s) between '{start_term}' and '{end_term}'")
            return readable_paths
            
        except Exception as e:
            self.logger.error(f"Error finding knowledge paths: {e}")
            return []
    
    def generate_thematic_index(self) -> Dict[str, Any]:
        """
        Genera un índice temático basado en el grafo.
        
        Agrupar términos por tema/categoría automáticamente.
        """
        try:
            # Agrupar por tipo de nodo
            themes = defaultdict(list)
            
            for node_id, node in self.nodes.items():
                theme = node.metadata.get('theme', 'general')
                themes[theme].append({
                    'term': node.label,
                    'node_id': node_id,
                    'type': node.node_type
                })
            
            # Ordenar alfabéticamente
            thematic_index = {
                theme: sorted(terms, key=lambda t: t['term'])
                for theme, terms in sorted(themes.items())
            }
            
            # Guardar índice
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(thematic_index, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"✓ Generated thematic index with {len(thematic_index)} themes")
            return thematic_index
            
        except Exception as e:
            self.logger.error(f"Error generating thematic index: {e}")
            return {}
    
    def export_graph_mermaid(self, output_path: Optional[Path] = None) -> str:
        """
        Exporta el grafo en formato Mermaid para visualización.
        """
        try:
            mermaid_code = "graph LR\n"
            
            # Limitar grafo para claridad
            node_ids = set()
            for edge in self.edges[:50]:  # Primeras 50 aristas
                node_ids.add(edge.source)
                node_ids.add(edge.target)
                
                source_label = self.nodes[edge.source].label if edge.source in self.nodes else "?"
                target_label = self.nodes[edge.target].label if edge.target in self.nodes else "?"
                
                mermaid_code += f'    {source_label} -->|{edge.relationship}| {target_label}\n'
            
            if output_path:
                output_path.write_text(mermaid_code, encoding='utf-8')
                self.logger.info(f"✓ Exported Mermaid diagram to {output_path}")
            
            return mermaid_code
            
        except Exception as e:
            self.logger.error(f"Error exporting Mermaid: {e}")
            return ""
    
    # ============ Métodos privados ============
    
    def _add_document_node(self, doc_path: Path, content: str) -> str:
        """Añade un nodo para un documento."""
        node_id = f"doc_{doc_path.stem}_{hash(str(doc_path)) % 10000}"
        
        if node_id not in self.nodes:
            node = GraphNode(
                id=node_id,
                label=doc_path.name,
                node_type='document',
                metadata={
                    'path': str(doc_path.relative_to(self.project_root)),
                    'length': len(content)
                },
                created_at=self._get_timestamp()
            )
            self.nodes[node_id] = node
            self.node_index[doc_path.name] = node_id
        
        return node_id
    
    def _add_section_node(self, section: Dict, doc_path: Path) -> str:
        """Añade un nodo para una sección de documento."""
        section_id = f"sec_{section['id']}"
        
        if section_id not in self.nodes:
            node = GraphNode(
                id=section_id,
                label=section['title'],
                node_type='section',
                metadata={
                    'document': str(doc_path.name),
                    'level': section['level']
                },
                created_at=self._get_timestamp()
            )
            self.nodes[section_id] = node
            self.node_index[section['title']] = section_id
        
        return section_id
    
    def _add_term_node(self, term: str, context: str) -> str:
        """Añade un nodo para un término."""
        term_lower = term.lower()
        node_id = f"term_{hash(term_lower) % 100000}"
        
        if node_id not in self.nodes:
            node = GraphNode(
                id=node_id,
                label=term,
                node_type='term',
                metadata={
                    'appearances': 1,
                    'theme': self._infer_theme(term, context)
                },
                created_at=self._get_timestamp()
            )
            self.nodes[node_id] = node
            self.node_index[term] = node_id
        else:
            # Incrementar apariciones
            self.nodes[node_id].metadata['appearances'] += 1
        
        return node_id
    
    def _add_edge(
        self,
        source: str,
        target: str,
        relationship: str,
        strength: float,
        context: Optional[str] = None
    ):
        """Añade una arista al grafo."""
        # Evitar duplicados
        for edge in self.edges:
            if edge.source == source and edge.target == target and edge.relationship == relationship:
                return  # Ya existe
        
        edge = GraphEdge(
            source=source,
            target=target,
            relationship=relationship,
            strength=strength,
            context=context
        )
        self.edges.append(edge)
        self.relationships[source].add(target)
    
    def _read_document(self, doc_path: Path) -> str:
        """Lee un documento."""
        try:
            return doc_path.read_text(encoding='utf-8', errors='ignore')
        except:
            return ""
    
    def _extract_sections(self, content: str, doc_path: Path) -> List[Dict]:
        """Extrae secciones de un documento Markdown."""
        sections = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('# ').strip()
                sections.append({
                    'title': title,
                    'level': level,
                    'id': f"{doc_path.stem}_{i}",
                    'start_line': i
                })
        
        return sections
    
    def _extract_terms(self, content: str) -> List[str]:
        """Extrae términos clave del contenido."""
        terms = set()
        
        # Palabras capitalizadas
        import re
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', content)
        terms.update(capitalized)
        
        # Términos entre backticks
        backtick_terms = re.findall(r'`([^`]+)`', content)
        terms.update(backtick_terms)
        
        return list(terms)
    
    def _build_term_relationships(self):
        """Construye relaciones entre términos basadas en co-ocurrencia."""
        # Implementación básica
        pass
    
    def _traverse_graph(self, node_id: str, max_depth: int, current_depth: int = 0, visited: Optional[Set[str]] = None) -> Dict:
        """Recorre el grafo desde un nodo."""
        if visited is None:
            visited = set()
        
        if current_depth > max_depth or node_id in visited:
            return {}
        
        visited.add(node_id)
        
        connections = {
            'edges': [],
            'depth': current_depth
        }
        
        for edge in self.edges:
            if edge.source == node_id:
                connections['edges'].append({
                    'target_label': self.nodes.get(edge.target, GraphNode('', '', '', {}, '')).label,
                    'target_id': edge.target,
                    'relationship': edge.relationship
                })
                
                if current_depth < max_depth:
                    sub_connections = self._traverse_graph(edge.target, max_depth, current_depth + 1, visited)
                    if sub_connections:
                        connections['children'] = sub_connections
        
        return connections
    
    def _infer_theme(self, term: str, context: str) -> str:
        """Infiere el tema de un término."""
        keywords = {
            'network': ['IP', 'port', 'protocol', 'bandwidth', 'latency', 'DNS'],
            'security': ['encryption', 'SSL', 'TLS', 'auth', 'password', 'certificate'],
            'architecture': ['API', 'architecture', 'microservice', 'module', 'component'],
            'database': ['database', 'query', 'table', 'schema', 'transaction']
        }
        
        for theme, words in keywords.items():
            if any(word.lower() in term.lower() for word in words):
                return theme
        
        return 'general'
    
    def _save_graph(self):
        """Guarda el grafo a archivo."""
        try:
            data = {
                'nodes': [n.to_dict() for n in self.nodes.values()],
                'edges': [e.to_dict() for e in self.edges],
                'timestamp': self._get_timestamp()
            }
            
            with open(self.graph_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Saved knowledge graph to {self.graph_file}")
        except Exception as e:
            self.logger.error(f"Error saving graph: {e}")
    
    def _load_graph(self):
        """Carga el grafo del archivo si existe."""
        try:
            if not self.graph_file.exists():
                return
            
            with open(self.graph_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Cargar nodos
            for node_data in data.get('nodes', []):
                node = GraphNode(**node_data)
                self.nodes[node.id] = node
                self.node_index[node.label] = node.id
            
            # Cargar aristas
            for edge_data in data.get('edges', []):
                edge = GraphEdge(**edge_data)
                self.edges.append(edge)
            
            self.logger.info(f"Loaded knowledge graph: {len(self.nodes)} nodes, {len(self.edges)} edges")
        except Exception as e:
            self.logger.warning(f"Could not load existing graph: {e}")
    
    @staticmethod
    def _get_timestamp() -> str:
        """Retorna timestamp actual."""
        from datetime import datetime
        return datetime.now().isoformat()
