/**
 * Type declarations for CDN-loaded libraries that don't have @types packages.
 *
 * Libraries loaded via <script> tags in base.html and not installed via npm.
 * Add `declare module` stubs here to silence TypeScript errors when importing
 * from these packages in .ts files.
 */

// Cytoscape (loaded via CDN — no @types/cytoscape for ESM)
declare module "cytoscape" {
  const cytoscape: unknown;
  export default cytoscape;
}

// vis-network (loaded via CDN)
declare module "vis-network" {
  export class Network {
    constructor(container: HTMLElement, data: unknown, options?: unknown);
    destroy(): void;
  }
  export class DataSet<T = unknown> {
    constructor(data?: T[]);
    add(data: T | T[]): unknown;
    update(data: T | T[]): void;
  }
}

// Mermaid (loaded via CDN)
declare module "mermaid" {
  const mermaid: {
    initialize(config: Record<string, unknown>): void;
    render(id: string, graph: string): Promise<{ svg: string }>;
  };
  export default mermaid;
}

// Monaco Editor (loaded via CDN — may have @types/monaco-editor but not installed)
declare const monaco: {
  editor: {
    create(element: HTMLElement, options?: Record<string, unknown>): {
      getValue(): string;
      setValue(value: string): void;
      dispose(): void;
    };
  };
  languages: { register(language: unknown): void };
};

// Chart.js (loaded via CDN — @types/chart.js available but may not be installed)
declare const Chart: {
  new (
    ctx: CanvasRenderingContext2D | HTMLCanvasElement,
    config: Record<string, unknown>
  ): {
    destroy(): void;
    update(): void;
    data: Record<string, unknown>;
  };
};

// Xterm.js (loaded via CDN)
declare const Terminal: {
  new (options?: Record<string, unknown>): {
    open(container: HTMLElement): void;
    write(data: string): void;
    writeln(data: string): void;
    onData(callback: (data: string) => void): void;
    dispose(): void;
  };
};

// Marked.js (loaded via CDN)
declare const marked: {
  parse(markdown: string, options?: Record<string, unknown>): string;
};

// Highlight.js (loaded via CDN)
declare const hljs: {
  highlightElement(element: HTMLElement): void;
  highlightAll(): void;
};
