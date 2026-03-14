"""Plugins router — manages local Python plugins from ~/.ollash/plugins/.

A plugin is any Python file or package placed in the plugins directory.
On load, Ollash imports it so any @ollash_tool decorators auto-register
new tools into the global tool registry.

Endpoints
---------
GET  /api/plugins            — list installed plugins
POST /api/plugins/install    — install plugin from local path (copy into dir)
DELETE /api/plugins/{name}   — remove plugin
POST /api/plugins/{name}/reload — reload plugin module at runtime
GET  /api/plugins/directory  — return plugins directory path
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_current_user_dep

router = APIRouter(prefix="/api/plugins", tags=["plugins"])

_PLUGINS_DIR = Path(os.environ.get("OLLASH_ROOT_DIR", ".ollash")) / "plugins"


# ---------------------------------------------------------------------------
# Plugin loader
# ---------------------------------------------------------------------------


def _ensure_plugins_dir() -> Path:
    _PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    return _PLUGINS_DIR


def _plugin_info(path: Path) -> dict:
    """Return metadata for a plugin file or package directory."""
    if path.is_dir():
        loaded = f"ollash_plugin_{path.name}" in sys.modules
        return {
            "name": path.name,
            "type": "package",
            "path": str(path),
            "loaded": loaded,
            "size_bytes": sum(f.stat().st_size for f in path.rglob("*.py")),
        }
    loaded = f"ollash_plugin_{path.stem}" in sys.modules
    return {
        "name": path.stem,
        "type": "module",
        "path": str(path),
        "loaded": loaded,
        "size_bytes": path.stat().st_size,
    }


def _list_plugins() -> list[dict]:
    plugins_dir = _ensure_plugins_dir()
    result: list[dict] = []
    for item in sorted(plugins_dir.iterdir()):
        if item.name.startswith("_"):
            continue
        if item.is_file() and item.suffix == ".py":
            result.append(_plugin_info(item))
        elif item.is_dir() and (item / "__init__.py").exists():
            result.append(_plugin_info(item))
    return result


def _load_plugin(name: str) -> str:
    """Import a plugin by name, registering its @ollash_tool decorators."""
    plugins_dir = _ensure_plugins_dir()

    plugins_str = str(plugins_dir)
    if plugins_str not in sys.path:
        sys.path.insert(0, plugins_str)

    py_file = plugins_dir / f"{name}.py"
    pkg_dir = plugins_dir / name

    if py_file.exists():
        module_name = f"ollash_plugin_{name}"
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            return f"Module '{name}' loaded ({py_file.name})"
    elif pkg_dir.exists() and (pkg_dir / "__init__.py").exists():
        module_name = f"ollash_plugin_{name}"
        spec = importlib.util.spec_from_file_location(
            module_name,
            pkg_dir / "__init__.py",
            submodule_search_locations=[str(pkg_dir)],
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            return f"Package '{name}' loaded"
    raise FileNotFoundError(f"Plugin '{name}' not found in {plugins_dir}")


def load_all_plugins() -> list[str]:
    """Load all plugins from the plugins directory.  Called at app startup."""
    results: list[str] = []
    for info in _list_plugins():
        try:
            msg = _load_plugin(info["name"])
            results.append(msg)
        except Exception as exc:
            results.append(f"FAILED {info['name']}: {exc}")
    return results


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PluginInstall(BaseModel):
    source_path: str  # absolute path to .py file or directory on the local filesystem


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
def list_plugins(user: dict = Depends(get_current_user_dep)) -> list[dict]:
    return _list_plugins()


@router.get("/directory")
def plugins_directory(user: dict = Depends(get_current_user_dep)) -> dict:
    d = _ensure_plugins_dir()
    return {"path": str(d)}


_ALLOWED_PLUGIN_SOURCES = [
    Path(".ollash").resolve(),
    Path("uploads").resolve(),
]


@router.post("/install", status_code=201)
def install_plugin(
    body: PluginInstall,
    user: dict = Depends(get_current_user_dep),
) -> dict:
    src = Path(body.source_path).resolve()
    if not any(src.is_relative_to(b) for b in _ALLOWED_PLUGIN_SOURCES):
        raise HTTPException(400, detail="source_path must be within .ollash/ or uploads/.")
    if not src.exists():
        raise HTTPException(400, detail="Source not found.")

    plugins_dir = _ensure_plugins_dir()

    if src.is_file() and src.suffix == ".py":
        dst = plugins_dir / src.name
        shutil.copy2(src, dst)
        name = src.stem
    elif src.is_dir() and (src / "__init__.py").exists():
        dst = plugins_dir / src.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        name = src.name
    else:
        raise HTTPException(
            400,
            detail="Source must be a .py file or a Python package directory with __init__.py",
        )

    try:
        msg = _load_plugin(name)
    except Exception as exc:
        return {"name": name, "status": "installed", "load_warning": str(exc)}

    return {"name": name, "status": "installed", "message": msg}


@router.delete("/{name}", status_code=204)
def remove_plugin(name: str, user: dict = Depends(get_current_user_dep)) -> None:
    plugins_dir = _ensure_plugins_dir()
    py_file = plugins_dir / f"{name}.py"
    pkg_dir = plugins_dir / name

    removed = False
    if py_file.exists():
        py_file.unlink()
        removed = True
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
        removed = True

    # Unload from sys.modules
    to_remove = [k for k in sys.modules if k == f"ollash_plugin_{name}" or k.startswith(f"ollash_plugin_{name}.")]
    for k in to_remove:
        del sys.modules[k]

    if not removed:
        raise HTTPException(404, detail=f"Plugin '{name}' not found")


@router.post("/{name}/reload")
def reload_plugin(name: str, user: dict = Depends(get_current_user_dep)) -> dict:
    """Remove from sys.modules and re-import the plugin."""
    to_remove = [k for k in sys.modules if k == f"ollash_plugin_{name}" or k.startswith(f"ollash_plugin_{name}.")]
    for k in to_remove:
        del sys.modules[k]
    try:
        msg = _load_plugin(name)
        return {"name": name, "status": "reloaded", "message": msg}
    except FileNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, detail=f"Reload failed: {exc}") from exc
