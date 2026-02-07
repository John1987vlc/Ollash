import os
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Any


class FileManager:
    """Gestiona operaciones de archivos del proyecto."""

    def __init__(self, root_path: str = None):
        self.root = Path(root_path) if root_path else Path.cwd()

    def read_file(self, path: str) -> str:
        """Lee el contenido de un archivo."""
        file_path = self.root / path
        if file_path.exists():
            return file_path.read_text(encoding='utf-8')
        raise FileNotFoundError(f"No existe: {path}")

    def write_file(self, path: str, content: str) -> str:
        """Escribe contenido a un archivo."""
        file_path = self.root / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return f"✅ Escrito: {path}"

    def create_directory(self, path: str) -> str:
        """Crea un directorio."""
        dir_path = self.root / path
        dir_path.mkdir(parents=True, exist_ok=True)
        return f"✅ Directorio creado: {path}"

    def list_directory(self, path: str = ".") -> List[str]:
        """Lista contenido de un directorio."""
        dir_path = self.root / path
        return [f.name for f in dir_path.iterdir()]

    def find_files(self, pattern: str) -> List[str]:
        """Busca archivos por patrón glob."""
        return [str(p) for p in self.root.glob(pattern)]

    def delete_file(self, path: str) -> str:
        """Elimina un archivo o directorio."""
        target = self.root / path
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        return f"✅ Eliminado: {path}"

    def get_file_info(self, path: str) -> Dict[str, Any]:
        """Obtiene información de un archivo."""
        file_path = self.root / path
        if file_path.exists():
            stat = file_path.stat()
            return {
                "nombre": file_path.name,
                "ruta": str(file_path),
                "tamaño": stat.st_size,
                "modificado": stat.st_mtime,
                "es_archivo": file_path.is_file(),
                "es_dir": file_path.is_dir()
            }
        return {"error": "Archivo no encontrado"}
