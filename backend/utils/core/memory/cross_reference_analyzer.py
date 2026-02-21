"""
Cross-Reference Analyzer for Ollash.

Permite análisis transversal entre múltiples documentos, identificando:
- Similitudes y diferencias conceptuales
- Inconsistencias terminológicas
- Gaps entre documentación teórica y configuración real
- Referencias cruzadas entre fuentes
"""

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.ollama_client import OllamaClient


@dataclass
class Difference:
    """Representa una diferencia encontrada entre documentos."""

    term: str
    in_doc1: bool
    in_doc2: bool
    definition1: Optional[str] = None
    definition2: Optional[str] = None
    similarity_score: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CrossReference:
    """Representa una referencia cruzada entre documentos."""

    term: str
    source_doc: str
    target_doc: str
    context: str
    relevance_score: float

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Inconsistency:
    """Representa una inconsistencia en terminología o conceptos."""

    issue_type: str  # 'terminology', 'definition', 'structure', 'metadata'
    severity: str  # 'critical', 'warning', 'info'
    term: str
    locations: List[str]  # Dónde aparece
    description: str
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


class CrossReferenceAnalyzer:
    """
    Analiza relaciones cruzadas entre múltiples documentos.

    Capacidades:
    - Comparar documentos y extraer similitudes/diferencias
    - Mapear conceptos compartidos
    - Identificar inconsistencias terminológicas
    - Detectar gaps entre teoría y práctica
    """

    def __init__(
        self,
        project_root: Path,
        logger: AgentLogger,
        config: Optional[Dict] = None,
        llm_recorder: Any = None,
    ):
        self.project_root = project_root
        self.logger = logger
        self.config = config or {}
        self.llm_recorder = llm_recorder  # Store llm_recorder

        # Output directory
        self.analysis_dir = project_root / "knowledge_workspace" / "cross_references"
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

        # Embedding client
        # Create a consolidated config dictionary for OllamaClient
        ollama_client_config_dict = {
            "ollama_max_retries": self.config.get("ollama_max_retries", 5),
            "ollama_backoff_factor": self.config.get("ollama_backoff_factor", 1.0),
            "ollama_retry_status_forcelist": self.config.get(
                "ollama_retry_status_forcelist", [429, 500, 502, 503, 504]
            ),
            "embedding_cache": self.config.get("embedding_cache", {}),
            "project_root": str(self.project_root),
            "ollama_embedding_model": self.config.get("ollama_embedding_model", "all-minilm"),
        }
        ollama_url = self.config.get("ollama_url", "http://localhost:11434")
        ollama_timeout = self.config.get("timeout", 300)  # Extract timeout here
        self.embedding_client = OllamaClient(
            url=ollama_url,
            model=self.config.get("embedding", "all-minilm"),
            timeout=ollama_timeout,  # Pass as positional argument
            logger=self.logger,
            config=ollama_client_config_dict,
            llm_recorder=self.llm_recorder,
        )

        # LLM para análisis semántico
        llm_url = self.config.get("ollama_url", "http://localhost:11434")
        llm_timeout = self.config.get("timeout", 300)  # Extract timeout here
        self.llm_client = OllamaClient(
            url=llm_url,
            model=self.config.get("reasoning", "gpt-oss:20b"),
            timeout=llm_timeout,  # Pass as positional argument
            logger=self.logger,
            config=ollama_client_config_dict,  # Use the same consolidated config dict
            llm_recorder=self.llm_recorder,  # Pass llm_recorder
        )

        self.logger.info("✓ CrossReferenceAnalyzer initialized")

    def compare_documents(self, doc1_path: Path, doc2_path: Path, chunk_size: int = 500) -> Dict[str, Any]:
        """
        Compara dos documentos y extrae similitudes y diferencias.

        Returns:
            {
                'similarities': List[str],
                'differences': List[Difference],
                'shared_concepts': List[str],
                'doc1_unique': List[str],
                'doc2_unique': List[str],
                'similarity_score': float
            }
        """
        try:
            # Leer documentos
            doc1_content = self._read_document(doc1_path)
            doc2_content = self._read_document(doc2_path)

            if not doc1_content or not doc2_content:
                self.logger.error("Cannot read one or both documents")
                return {}

            # Chunkarizar
            chunks1 = self._chunk_text(doc1_content, chunk_size)
            chunks2 = self._chunk_text(doc2_content, chunk_size)

            self.logger.debug(f"Doc1: {len(chunks1)} chunks, Doc2: {len(chunks2)} chunks")

            # Extraer términos/conceptos clave
            concepts1 = self._extract_concepts(doc1_content)
            concepts2 = self._extract_concepts(doc2_content)

            # Análisis de similitud
            similarities = self._find_similarities(chunks1, chunks2)
            differences = self._find_differences(concepts1, concepts2)
            shared_concepts = list(set(concepts1) & set(concepts2))
            unique_to_doc1 = list(set(concepts1) - set(concepts2))
            unique_to_doc2 = list(set(concepts2) - set(concepts1))

            # Similarity score general
            similarity_score = self._calculate_similarity_score(chunks1, chunks2)

            result = {
                "doc1": str(doc1_path.name),
                "doc2": str(doc2_path.name),
                "similarities": similarities,
                "differences": [d.to_dict() for d in differences],
                "shared_concepts": shared_concepts,
                "doc1_unique": unique_to_doc1,
                "doc2_unique": unique_to_doc2,
                "similarity_score": similarity_score,
                "timestamp": self._get_timestamp(),
            }

            # Guardar resultado
            output_file = self.analysis_dir / f"comparison_{Path(doc1_path).stem}_vs_{Path(doc2_path).stem}.json"
            self._save_json(output_file, result)

            self.logger.info(f"✓ Comparison complete: {similarity_score:.2%} similarity")
            return result

        except Exception as e:
            self.logger.error(f"Error comparing documents: {e}")
            return {}

    def find_cross_references(
        self, term: str, source_dirs: List[Path], context_window: int = 100
    ) -> List[CrossReference]:
        """
        Busca referencias cruzadas de un término en múltiples directorios.

        Args:
            term: Término a buscar
            source_dirs: Directorios a analizar
            context_window: Caracteres de contexto alrededor del término

        Returns:
            Lista de referencias cruzadas encontradas
        """
        references = []

        try:
            for source_dir in source_dirs:
                if not source_dir.exists():
                    continue

                for doc_path in source_dir.rglob("*"):
                    if not doc_path.is_file():
                        continue

                    try:
                        content = self._read_document(doc_path)
                        if not content:
                            continue

                        # Buscar término (case-insensitive)
                        term_lower = term.lower()
                        idx = 0

                        while True:
                            idx = content.lower().find(term_lower, idx)
                            if idx == -1:
                                break

                            # Extraer contexto
                            start = max(0, idx - context_window)
                            end = min(len(content), idx + len(term) + context_window)
                            context = content[start:end].strip()

                            # Calcular relevancia
                            relevance = self._calculate_relevance(context, term)

                            ref = CrossReference(
                                term=term,
                                source_doc=str(doc_path.relative_to(self.project_root)),
                                target_doc=str(source_dir.name),
                                context=context,
                                relevance_score=relevance,
                            )
                            references.append(ref)

                            idx += len(term)

                    except Exception as e:
                        self.logger.debug(f"Error processing {doc_path}: {e}")
                        continue

            # Ordenar por relevancia
            references.sort(key=lambda r: r.relevance_score, reverse=True)

            self.logger.info(f"✓ Found {len(references)} cross-references for '{term}'")
            return references

        except Exception as e:
            self.logger.error(f"Error finding cross-references: {e}")
            return []

    def extract_inconsistencies(self, doc_paths: List[Path]) -> List[Inconsistency]:
        """
        Analiza documentos y extrae inconsistencias de terminología, estructura, etc.
        """
        inconsistencies = []

        try:
            # Mapear términos a documentos
            term_map = defaultdict(list)
            for doc_path in doc_paths:
                content = self._read_document(doc_path)
                if not content:
                    continue

                concepts = self._extract_concepts(content)
                for concept in concepts:
                    term_map[concept].append(str(doc_path.relative_to(self.project_root)))

            # Buscar inconsistencias de terminología
            for term, locations in term_map.items():
                if len(locations) > 1:
                    # Mismo concepto, múltiples documentos
                    # Verificar variaciones (ejemplo: "API REST" vs "REST API")
                    variations = self._find_term_variations(term, doc_paths)
                    if variations:
                        inconsistencies.append(
                            Inconsistency(
                                issue_type="terminology",
                                severity="warning",
                                term=term,
                                locations=locations,
                                description=f"Possible variations: {', '.join(variations)}",
                                suggestion=f"Standardize to: {variations[0]}",
                            )
                        )

            # Otros tipos de inconsistencias
            structural_issues = self._check_structural_consistency(doc_paths)
            inconsistencies.extend(structural_issues)

            self.logger.info(f"✓ Found {len(inconsistencies)} inconsistencies")
            return inconsistencies

        except Exception as e:
            self.logger.error(f"Error extracting inconsistencies: {e}")
            return []

    def find_gaps_theory_vs_practice(self, theory_doc: Path, config_file: Path) -> Dict[str, Any]:
        """
        Encuentra gaps entre documentación teórica y configuración real.

        Args:
            theory_doc: Documentación/manual teórico
            config_file: Archivo de configuración actual (JSON)

        Returns:
            Análisis de gaps encontrados
        """
        try:
            theory_content = self._read_document(theory_doc)

            # Leer configuración
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f) if config_file.suffix == ".json" else {}

            # Extraer parámetros de configuración
            config_keys = self._extract_config_keys(config)

            # Extraer parámetros esperados de la teoría
            theory_keys = self._extract_expected_params(theory_content)

            # Análisis de gaps
            gaps = {
                "implemented_vs_documented": [],
                "documented_but_not_implemented": [],
                "configured_but_not_documented": [],
                "values_differ": [],
                "timestamp": self._get_timestamp(),
            }

            # Items en config pero no documentados
            for key in config_keys:
                if key not in theory_keys:
                    gaps["configured_but_not_documented"].append(
                        {"key": key, "value": config.get(key), "severity": "info"}
                    )

            # Items documentados pero no configurados
            for key in theory_keys:
                if key not in config_keys:
                    gaps["documented_but_not_implemented"].append({"key": key, "severity": "warning"})

            # Guardar análisis
            output_file = self.analysis_dir / f"gaps_{Path(theory_doc).stem}_vs_{Path(config_file).stem}.json"
            self._save_json(output_file, gaps)

            self.logger.info("✓ Gap analysis complete")
            return gaps

        except Exception as e:
            self.logger.error(f"Error in gap analysis: {e}")
            return {}

    # ============ Métodos privados ============

    def _read_document(self, doc_path: Path) -> str:
        """Lee un documento de texto."""
        try:
            if not doc_path.exists():
                return ""

            # Intentar leer como UTF-8
            return doc_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            self.logger.debug(f"Error reading {doc_path}: {e}")
            return ""

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """Divide texto en chunks."""
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i : i + chunk_size])
        return chunks

    def _extract_concepts(self, text: str) -> List[str]:
        """Extrae conceptos clave del texto."""
        # Implementación simple: palabras en mayúsculas o entre backticks
        concepts = set()

        # Palabras capitalizadas (probable concepto)
        words = text.split()
        for word in words:
            if word and word[0].isupper() and len(word) > 3:
                concepts.add(word.strip(".,!?;:"))

        # Términos entre backticks
        import re

        backtick_terms = re.findall(r"`([^`]+)`", text)
        concepts.update(backtick_terms)

        return list(concepts)

    def _find_similarities(self, chunks1: List[str], chunks2: List[str]) -> List[str]:
        """Encuentra similitudes entre chunks."""
        similarities = []

        for c1 in chunks1[:5]:  # Limitar para performance
            for c2 in chunks2[:5]:
                ratio = SequenceMatcher(None, c1, c2).ratio()
                if ratio > 0.7:
                    similarities.append(f"Similarity: {ratio:.1%}")

        return similarities

    def _find_differences(self, concepts1: List[str], concepts2: List[str]) -> List[Difference]:
        """Encuentra diferencias entre conceptos."""
        differences = []
        all_concepts = set(concepts1) | set(concepts2)

        for concept in all_concepts:
            in1 = concept in concepts1
            in2 = concept in concepts2

            if in1 != in2:
                differences.append(Difference(term=concept, in_doc1=in1, in_doc2=in2, similarity_score=0.0))

        return differences

    def _calculate_similarity_score(self, chunks1: List[str], chunks2: List[str]) -> float:
        """Calcula score de similitud general."""
        if not chunks1 or not chunks2:
            return 0.0

        similarities = 0
        comparisons = 0

        for c1 in chunks1[:3]:
            for c2 in chunks2[:3]:
                ratio = SequenceMatcher(None, c1, c2).ratio()
                similarities += ratio
                comparisons += 1

        return similarities / comparisons if comparisons > 0 else 0.0

    def _calculate_relevance(self, context: str, term: str) -> float:
        """Calcula relevancia de un contexto para un término."""
        # Simple: qué tan cerca está el término del centro del contexto
        center = len(context) // 2
        term_pos = context.lower().find(term.lower())

        if term_pos == -1:
            return 0.0

        distance = abs(term_pos - center)
        max_distance = len(context)

        return 1.0 - (distance / max_distance)

    def _find_term_variations(self, term: str, doc_paths: List[Path]) -> List[str]:
        """Busca variaciones de un término."""
        variations = set()

        for doc_path in doc_paths:
            content = self._read_document(doc_path)
            if not content:
                continue

            # Buscar permutaciones simples
            parts = term.split()
            if len(parts) > 1:
                # Invertir orden
                reversed_term = " ".join(reversed(parts))
                if reversed_term.lower() in content.lower():
                    variations.add(reversed_term)

        return list(variations)

    def _check_structural_consistency(self, doc_paths: List[Path]) -> List[Inconsistency]:
        """Verifica consistencia estructural (headers, formato, etc.)."""
        inconsistencies = []
        # Implementación básica
        return inconsistencies

    def _extract_config_keys(self, config: Dict) -> Set[str]:
        """Extrae claves de un diccionario de configuración recursivamente."""
        keys = set()

        def extract(obj, prefix=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    full_key = f"{prefix}.{k}" if prefix else k
                    keys.add(full_key)
                    extract(v, full_key)

        extract(config)
        return keys

    def _extract_expected_params(self, text: str) -> Set[str]:
        """Extrae parámetros esperados de documentación."""
        import re

        params = set()

        # Buscar patrones como "parameter: " o "config key: "
        patterns = [
            r"(?:parameter|key|setting|config):\s*([a-zA-Z_][a-zA-Z0-9_]*)",
            r"\[([A-Z_]+)\]",
            r"`([a-z_][a-z0-9_]*)`",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            params.update(matches)

        return params

    def _save_json(self, path: Path, data: Dict):
        """Guarda datos como JSON."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Saved analysis to {path.name}")
        except Exception as e:
            self.logger.error(f"Error saving JSON: {e}")

    @staticmethod
    def _get_timestamp() -> str:
        """Retorna timestamp actual."""
        from datetime import datetime

        return datetime.now().isoformat()
