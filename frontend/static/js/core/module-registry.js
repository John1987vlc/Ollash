/**
 * Ollash Module Registry
 * Centralizes module registration and initialization to replace scattered typeof checks.
 *
 * Usage:
 *   // In each module file (at the end):
 *   OllashModules.register('MyModule', MyModule);
 *
 *   // In main.js (instead of typeof checks):
 *   OllashModules.initAll({ MyModule: { option: value }, ... });
 */
window.OllashModules = (function () {
    const _registry = {};

    return {
        /**
         * Register a module by name.
         * @param {string} name - Module identifier.
         * @param {object} module - Module object (must have an init() method if auto-initializable).
         */
        register(name, module) {
            _registry[name] = module;
        },

        /**
         * Initialize a single registered module with optional options.
         * @param {string} name - Module identifier.
         * @param {object} [options] - Options passed to module.init().
         */
        init(name, options) {
            const mod = _registry[name];
            if (mod && typeof mod.init === 'function') {
                mod.init(options);
            }
        },

        /**
         * Retrieve a registered module.
         * @param {string} name - Module identifier.
         * @returns {object|undefined}
         */
        get(name) {
            return _registry[name];
        },

        /**
         * Initialize all registered modules from a config map.
         * @param {Object.<string, object|null>} configs - Map of moduleName → init options (or null).
         */
        initAll(configs) {
            Object.entries(configs).forEach(([name, opts]) => {
                this.init(name, opts || undefined);
            });
        }
    };
}());
