"""
Decision Context Manager for Ollash.

Mantiene un registro de decisiones arquitectónicas, de seguridad y de diseño.
Permite que el agente aprenda patrones y sugiera soluciones basadas en experiencias
anteriores similares.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from src.utils.core.agent_logger import AgentLogger


@dataclass
class Decision:
    """Representa una decisión registrada."""
    id: str
    timestamp: str
    project: str
    category: str  # 'architecture', 'security', 'performance', 'design', 'other'
    decision: str  # Breve descripción de la decisión
    reasoning: str  # Por qué se tomó esta decisión
    context: Dict[str, Any]  # Contexto relevante
    outcome: Optional[Dict[str, Any]] = None  # Resultados posteriores
    tags: List[str] = None
    related_decisions: List[str] = None  # IDs de decisiones relacionadas
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.related_decisions is None:
            self.related_decisions = []
    
    def to_dict(self) -> Dict:
        return asdict(self)


class DecisionContextManager:
    """
    Gestor de contexto de decisiones.
    
    Funcionalidades:
    - Registrar decisiones con contexto y razonamiento
    - Buscar decisiones similares en el historial
    - Sugerir soluciones basadas en patrones previos
    - Almacenar outcomes para aprendizaje continuo
    """
    
    def __init__(self, project_root: Path, logger: AgentLogger, config: Optional[Dict] = None):
        self.project_root = project_root
        self.logger = logger
        self.config = config or {}
        
        # Archivo de almacenamiento
        self.decisions_file = project_root / ".decision_history.json"
        self.decisions: Dict[str, Decision] = {}
        self.current_project = "default"
        
        # Cargar decisiones existentes
        self._load_decisions()
        
        self.logger.info("✓ DecisionContextManager initialized")
    
    def record_decision(
        self,
        decision: str,
        reasoning: str,
        category: str,
        context: Dict[str, Any],
        project: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Registra una nueva decisión.
        
        Args:
            decision: Descripción de la decisión
            reasoning: Razonamiento detrás de la decisión
            category: Categoría (architecture, security, performance, design, other)
            context: Contexto relevante (problema, restricciones, etc.)
            project: Nombre del proyecto (si None, usa predeterminado)
            tags: Tags para clasificación y búsqueda
            
        Returns:
            ID de la decisión registrada
        """
        try:
            project = project or self.current_project
            decision_id = self._generate_decision_id()
            
            dec = Decision(
                id=decision_id,
                timestamp=self._get_timestamp(),
                project=project,
                category=category,
                decision=decision,
                reasoning=reasoning,
                context=context,
                tags=tags or []
            )
            
            self.decisions[decision_id] = dec
            self._save_decisions()
            
            self.logger.info(
                f"✓ Recorded decision [{category}]: {decision[:50]}... (ID: {decision_id})"
            )
            
            return decision_id
            
        except Exception as e:
            self.logger.error(f"Error recording decision: {e}")
            return ""
    
    def find_similar_decisions(
        self,
        problem: str,
        category: Optional[str] = None,
        project: Optional[str] = None,
        max_results: int = 5
    ) -> List[Decision]:
        """
        Busca decisiones similares en el historial.
        
        Args:
            problem: Descripción del problema actual
            category: Filtrar por categoría (opcional)
            project: Filtrar por proyecto (opcional)
            max_results: Máximo número de resultados
            
        Returns:
            Lista de decisiones similares ordenadas por relevancia
        """
        try:
            problem_words = set(problem.lower().split())
            candidates = []
            
            for decision_id, decision in self.decisions.items():
                # Filtrar por categoría si se especifica
                if category and decision.category != category:
                    continue
                
                # Filtrar por proyecto si se especifica
                if project and decision.project != project:
                    continue
                
                # Calcular similitud basada en palabras comunes
                decision_words = set(
                    (decision.decision + " " + decision.reasoning).lower().split()
                )
                
                common = len(problem_words & decision_words)
                if common > 0:
                    # Calcular score de similitud de Jaccard
                    similarity = common / len(problem_words | decision_words)
                    candidates.append((decision, similarity))
            
            # Ordenar por similitud y retornar top N
            candidates.sort(key=lambda x: x[1], reverse=True)
            similar = [d for d, _ in candidates[:max_results]]
            
            self.logger.debug(f"Found {len(similar)} similar decision(s)")
            return similar
            
        except Exception as e:
            self.logger.error(f"Error finding similar decisions: {e}")
            return []
    
    def suggest_based_on_history(
        self,
        question: str,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Sugiere soluciones basadas en decisiones históricas.
        
        Encuentra decisiones relevantes y extrae patrones/lecciones aprendidas.
        """
        try:
            similar_decisions = self.find_similar_decisions(question, category)
            
            suggestions = []
            for decision in similar_decisions:
                suggestion = {
                    'based_on_decision_id': decision.id,
                    'decision': decision.decision,
                    'reasoning': decision.reasoning,
                    'project': decision.project,
                    'timestamp': decision.timestamp,
                    'outcome': decision.outcome,
                    'tags': decision.tags,
                    'relevance': 'based_on_similarity'
                }
                suggestions.append(suggestion)
            
            self.logger.info(f"Generated {len(suggestions)} suggestion(s) from history")
            return suggestions
            
        except Exception as e:
            self.logger.error(f"Error suggesting from history: {e}")
            return []
    
    def update_outcome(
        self,
        decision_id: str,
        outcome: Dict[str, Any]
    ) -> bool:
        """
        Actualiza el outcome de una decisión registrada.
        
        Útil para registrar resultados posteriores y permitir aprendizaje.
        """
        try:
            if decision_id not in self.decisions:
                self.logger.warning(f"Decision {decision_id} not found")
                return False
            
            self.decisions[decision_id].outcome = outcome
            self._save_decisions()
            
            self.logger.info(f"Updated outcome for decision {decision_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating outcome: {e}")
            return False
    
    def get_project_context(self, project: str) -> Dict[str, Any]:
        """
        Obtiene el contexto completo de un proyecto.
        
        Incluye:
        - Todas sus decisiones
        - Patrones identificados
        - Lecciones aprendidas
        """
        try:
            project_decisions = [
                d for d in self.decisions.values()
                if d.project == project
            ]
            
            # Agrupar por categoría
            by_category = {}
            for decision in project_decisions:
                if decision.category not in by_category:
                    by_category[decision.category] = []
                by_category[decision.category].append(decision)
            
            # Extraer patrones (decisiones similares dentro del mismo proyecto)
            patterns = self._extract_patterns(project_decisions)
            
            # Lecciones aprendidas
            lessons = self._extract_lessons(project_decisions)
            
            context = {
                'project': project,
                'total_decisions': len(project_decisions),
                'decisions_by_category': {
                    cat: len(decs)
                    for cat, decs in by_category.items()
                },
                'patterns': patterns,
                'lessons_learned': lessons,
                'timestamp': self._get_timestamp()
            }
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error getting project context: {e}")
            return {}
    
    def get_decision(self, decision_id: str) -> Optional[Decision]:
        """Obtiene una decisión específica por ID."""
        return self.decisions.get(decision_id)
    
    def get_all_decisions(self, project: Optional[str] = None) -> List[Decision]:
        """Obtiene todas las decisiones, opcionalmente filtradas por proyecto."""
        if project:
            return [d for d in self.decisions.values() if d.project == project]
        return list(self.decisions.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas del historial de decisiones."""
        try:
            if not self.decisions:
                return {'total_decisions': 0}
            
            # Agrupar por categoría
            by_category = {}
            by_project = {}
            
            for decision in self.decisions.values():
                by_category[decision.category] = by_category.get(decision.category, 0) + 1
                by_project[decision.project] = by_project.get(decision.project, 0) + 1
            
            # Calcular decisiones con outcomes
            with_outcomes = sum(1 for d in self.decisions.values() if d.outcome)
            
            stats = {
                'total_decisions': len(self.decisions),
                'decisions_with_outcomes': with_outcomes,
                'by_category': by_category,
                'by_project': by_project,
                'projects_count': len(by_project),
                'oldest_decision': min(
                    (d.timestamp for d in self.decisions.values()),
                    default=None
                ),
                'latest_decision': max(
                    (d.timestamp for d in self.decisions.values()),
                    default=None
                )
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}
    
    def export_project_memory(self, project: str, output_path: Optional[Path] = None) -> Dict:
        """
        Exporta la memoria de un proyecto en formato JSON.
        
        Útil para compartir o documentar decisiones tomadas.
        """
        try:
            context = self.get_project_context(project)
            decisions = [d.to_dict() for d in self.get_all_decisions(project)]
            
            export = {
                'project': project,
                'context': context,
                'decisions': decisions,
                'export_timestamp': self._get_timestamp()
            }
            
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(export, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Exported project memory to {output_path}")
            
            return export
            
        except Exception as e:
            self.logger.error(f"Error exporting project memory: {e}")
            return {}
    
    # ============ Métodos privados ============
    
    def _extract_patterns(self, decisions: List[Decision]) -> List[str]:
        """Extrae patrones comunes de un conjunto de decisiones."""
        patterns = []
        
        # Buscar decisiones que se repiten en categorías similares
        categories = {}
        for decision in decisions:
            if decision.category not in categories:
                categories[decision.category] = []
            categories[decision.category].append(decision)
        
        for category, decs in categories.items():
            if len(decs) > 1:
                # Este es un patrón: múltiples decisiones en la misma categoría
                pattern = f"Multiple {category} decisions detected - " \
                         f"this is a recurring concern in this project"
                patterns.append(pattern)
        
        return patterns
    
    def _extract_lessons(self, decisions: List[Decision]) -> List[str]:
        """Extrae lecciones aprendidas de decisiones con outcomes."""
        lessons = []
        
        for decision in decisions:
            if decision.outcome:
                success = decision.outcome.get('success', False)
                lesson_text = decision.outcome.get('lesson', '')
                
                if lesson_text:
                    lessons.append({
                        'lesson': lesson_text,
                        'from_decision': decision.decision,
                        'successful': success
                    })
        
        return lessons
    
    def _generate_decision_id(self) -> str:
        """Genera un ID único para una decisión."""
        import uuid
        return f"dec_{uuid.uuid4().hex[:8]}"
    
    def _save_decisions(self):
        """Guarda las decisiones a archivo JSON."""
        try:
            data = {
                'decisions': {
                    dec_id: dec.to_dict()
                    for dec_id, dec in self.decisions.items()
                },
                'last_updated': self._get_timestamp()
            }
            
            with open(self.decisions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug("Saved decision history")
        except Exception as e:
            self.logger.error(f"Error saving decisions: {e}")
    
    def _load_decisions(self):
        """Carga las decisiones del archivo JSON."""
        try:
            if not self.decisions_file.exists():
                return
            
            with open(self.decisions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for dec_id, dec_data in data.get('decisions', {}).items():
                # Reconstruir Decision object
                decision = Decision(**dec_data)
                self.decisions[dec_id] = decision
            
            self.logger.debug(f"Loaded {len(self.decisions)} decisions from history")
        except Exception as e:
            self.logger.warning(f"Could not load decision history: {e}")
    
    @staticmethod
    def _get_timestamp() -> str:
        """Retorna timestamp actual."""
        return datetime.now().isoformat()
