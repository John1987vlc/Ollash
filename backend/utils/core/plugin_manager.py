"""
Plugin Manager for Ollash

Discovers, loads, validates, and manages third-party plugins that extend
the Ollash tool system with new domains.
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.plugin_interface import OllashPlugin


class PluginManager:
    """Discovers and manages Ollash plugins.

    Plugins are discovered from a configurable directory (default: 'plugins/').
    Each plugin must contain a module with a class that extends OllashPlugin.
    """

    def __init__(
        self,
        plugins_dir: Path,
        logger: AgentLogger,
        enabled_plugins: Optional[List[str]] = None,
    ):
        self.plugins_dir = Path(plugins_dir)
        self.logger = logger
        self.enabled_plugins = enabled_plugins or []
        self._loaded_plugins: Dict[str, OllashPlugin] = {}

    def discover(self) -> List[OllashPlugin]:
        """Discover and load all plugins from the plugins directory.

        Returns:
            List of loaded plugin instances.
        """
        if not self.plugins_dir.exists():
            self.logger.info(f"Plugins directory not found: {self.plugins_dir}")
            return []

        discovered = []
        plugins_package = str(self.plugins_dir).replace("/", ".").replace("\\", ".")

        try:
            spec = importlib.util.find_spec(plugins_package)
            if not spec or not spec.submodule_search_locations:
                self.logger.info(f"No plugins package found at: {plugins_package}")
                return []
        except (ModuleNotFoundError, ValueError):
            self.logger.info(f"Cannot import plugins package: {plugins_package}")
            return []

        for _, name, is_pkg in pkgutil.iter_modules(spec.submodule_search_locations, prefix=f"{spec.name}."):
            if not is_pkg:
                continue

            plugin_id = name.split(".")[-1]

            # Skip disabled plugins if filter is set
            if self.enabled_plugins and plugin_id not in self.enabled_plugins:
                self.logger.debug(f"Skipping disabled plugin: {plugin_id}")
                continue

            plugin = self._load_plugin_from_package(name, plugin_id)
            if plugin:
                discovered.append(plugin)

        self.logger.info(f"Discovered {len(discovered)} plugin(s)")
        return discovered

    def _load_plugin_from_package(self, package_name: str, plugin_id: str) -> Optional[OllashPlugin]:
        """Load a plugin from its package."""
        try:
            # Try to import plugin.py from the package
            module = importlib.import_module(f"{package_name}.plugin")

            # Find the OllashPlugin subclass
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, OllashPlugin) and attr is not OllashPlugin:
                    plugin = attr()
                    plugin.on_load()
                    self._loaded_plugins[plugin.get_id()] = plugin
                    self.logger.info(
                        f"Loaded plugin: {plugin.get_name()} v{plugin.get_version()} (id: {plugin.get_id()})"
                    )
                    return plugin

            self.logger.warning(f"No OllashPlugin subclass found in {package_name}.plugin")
        except ImportError as e:
            self.logger.warning(f"Failed to import plugin {plugin_id}: {e}")
        except Exception as e:
            self.logger.error(f"Error loading plugin {plugin_id}: {e}")

        return None

    def load_plugin(self, plugin_id: str) -> Optional[OllashPlugin]:
        """Load a specific plugin by ID."""
        if plugin_id in self._loaded_plugins:
            return self._loaded_plugins[plugin_id]

        package_name = f"{str(self.plugins_dir).replace('/', '.').replace(chr(92), '.')}.{plugin_id}"
        return self._load_plugin_from_package(package_name, plugin_id)

    def unload_plugin(self, plugin_id: str) -> None:
        """Unload a plugin by ID."""
        if plugin_id in self._loaded_plugins:
            plugin = self._loaded_plugins[plugin_id]
            plugin.on_unload()
            del self._loaded_plugins[plugin_id]
            self.logger.info(f"Unloaded plugin: {plugin_id}")

    def get_loaded_plugins(self) -> Dict[str, OllashPlugin]:
        """Return all currently loaded plugins."""
        return dict(self._loaded_plugins)

    def get_all_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get combined tool definitions from all loaded plugins."""
        definitions = []
        for plugin in self._loaded_plugins.values():
            definitions.extend(plugin.get_tool_definitions())
        return definitions

    def get_all_toolset_configs(self) -> List[Dict[str, Any]]:
        """Get combined toolset configs from all loaded plugins."""
        configs = []
        for plugin in self._loaded_plugins.values():
            for cfg in plugin.get_toolset_configs():
                cfg["plugin_id"] = plugin.get_id()
                configs.append(cfg)
        return configs

    def get_plugin_metadata(self) -> List[Dict[str, Any]]:
        """Get metadata for all loaded plugins."""
        return [p.get_metadata() for p in self._loaded_plugins.values()]
