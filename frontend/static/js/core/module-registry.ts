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

export interface OllashModule {
    init?(options?: Record<string, unknown>): void;
    [key: string]: unknown;
}

export interface OllashModulesAPI {
    register(name: string, module: OllashModule): void;
    init(name: string, options?: Record<string, unknown>): void;
    get(name: string): OllashModule | undefined;
    initAll(configs: Record<string, Record<string, unknown> | null>): void;
}

declare global {
    interface Window {
        OllashModules: OllashModulesAPI;
    }
}

window.OllashModules = (function (): OllashModulesAPI {
    const _registry: Record<string, OllashModule> = {};

    return {
        /**
         * Register a module by name.
         * @param name - Module identifier.
         * @param module - Module object (must have an init() method if auto-initializable).
         */
        register(name: string, module: OllashModule): void {
            _registry[name] = module;
        },

        /**
         * Initialize a single registered module with optional options.
         * @param name - Module identifier.
         * @param options - Options passed to module.init().
         */
        init(name: string, options?: Record<string, unknown>): void {
            const mod = _registry[name];
            if (mod && typeof mod.init === 'function') {
                mod.init(options);
            }
        },

        /**
         * Retrieve a registered module.
         * @param name - Module identifier.
         */
        get(name: string): OllashModule | undefined {
            return _registry[name];
        },

        /**
         * Initialize all registered modules from a config map.
         * @param configs - Map of moduleName → init options (or null).
         */
        initAll(configs: Record<string, Record<string, unknown> | null>): void {
            Object.entries(configs).forEach(([name, opts]) => {
                this.init(name, opts ?? undefined);
            });
        },
    };
}());
