"""Phase 6: InfraPhase — template-driven infrastructure file generation.

Creates: .gitignore, requirements.txt (or package.json), Dockerfile.
Uses hardcoded templates for most files. One LLM call only for dependency inference.
Skips files that already exist in ctx.generated_files.

Improvements:
  #12 — Smart entrypoint detection: finds the true entry file for Dockerfile CMD
  #16 — Plugin architecture: each infra concern is an InfraPlugin with can_handle/apply
"""

from __future__ import annotations

import re
import sys as _sys
from abc import ABC, abstractmethod
from typing import ClassVar, List, Set

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_GITIGNORE_PYTHON = """__pycache__/
*.pyc
*.pyo
*.pyd
.env
.venv/
venv/
env/
dist/
build/
*.egg-info/
.mypy_cache/
.ruff_cache/
.pytest_cache/
*.db
.DS_Store
"""

_GITIGNORE_NODE = """node_modules/
dist/
build/
.env
.env.local
*.log
.DS_Store
coverage/
"""

_GITIGNORE_GO = """/bin/
/vendor/
*.exe
*.exe~
*.dll
*.so
*.dylib
*.test
*.out
.env
.DS_Store
"""

_GITIGNORE_RUST = """/target/
Cargo.lock
**/*.rs.bk
.env
.DS_Store
"""

_GITIGNORE_JAVA = """target/
*.class
*.jar
*.war
*.ear
.idea/
*.iml
.eclipse/
.settings/
.project
.classpath
.DS_Store
.env
"""

_GITIGNORE_CSHARP = """bin/
obj/
*.user
*.suo
*.vs/
.vs/
packages/
*.nupkg
.env
.DS_Store
"""

_GITIGNORE_PHP = """vendor/
.env
.env.local
*.log
composer.lock
*.cache
.DS_Store
storage/logs/
storage/framework/cache/
"""

_GITIGNORE_RUBY = """.bundle/
vendor/bundle/
*.gem
.env
.DS_Store
log/
tmp/
coverage/
"""

_GITIGNORE_DART = """.dart_tool/
.packages
build/
.flutter-plugins
.flutter-plugins-dependencies
*.g.dart
*.freezed.dart
pubspec.lock
.env
.DS_Store
"""

_GITIGNORE_KOTLIN = """.gradle/
build/
*.class
*.jar
*.war
.idea/
*.iml
.kotlin/
.DS_Store
.env
"""

# Map project_type / tech_stack keywords → gitignore template
_GITIGNORE_MAP: dict[str, str] = {
    "go_service": _GITIGNORE_GO,
    "rust_project": _GITIGNORE_RUST,
    "java_app": _GITIGNORE_JAVA,
    "csharp_app": _GITIGNORE_CSHARP,
    "php_app": _GITIGNORE_PHP,
    "ruby_app": _GITIGNORE_RUBY,
    "flutter_app": _GITIGNORE_DART,
    "kotlin_app": _GITIGNORE_KOTLIN,
}

_DOCKERFILE_PYTHON = """FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "{entrypoint}"]
"""

_DOCKERFILE_NODE = """FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
CMD ["node", "{entrypoint}"]
"""

_DOCKERFILE_FRONTEND = """FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""

_DOCKERFILE_GO = """FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/server .

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/server .
EXPOSE 8080
CMD ["./server"]
"""

_DOCKERFILE_RUST = """FROM rust:1.77-alpine AS builder
RUN apk add --no-cache musl-dev
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo 'fn main(){{}}' > src/main.rs && cargo build --release
RUN rm -f target/release/deps/app*
COPY . .
RUN cargo build --release

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/target/release/{binary_name} .
EXPOSE 8080
CMD ["./{binary_name}"]
"""

_DOCKERFILE_JAVA = """FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn package -DskipTests

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
"""

_DOCKERFILE_CSHARP = """FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /app
COPY *.csproj ./
RUN dotnet restore
COPY . .
RUN dotnet publish -c Release -o out

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app/out .
EXPOSE 8080
ENTRYPOINT ["dotnet", "{assembly_name}.dll"]
"""

_DOCKERFILE_PHP = """FROM php:8.3-fpm-alpine
WORKDIR /var/www/html
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-interaction --optimize-autoloader
COPY . .
EXPOSE 9000
CMD ["php-fpm"]
"""

_DOCKERFILE_RUBY = """FROM ruby:3.3-alpine
RUN apk add --no-cache build-base
WORKDIR /app
COPY Gemfile Gemfile.lock ./
RUN bundle install --without development test
COPY . .
EXPOSE 3000
CMD ["ruby", "{entrypoint}"]
"""

_PACKAGE_JSON_FRONTEND = """{{
  "name": "{project_name}",
  "version": "1.0.0",
  "description": "{description}",
  "scripts": {{
    "start": "npx serve . -l 8080",
    "dev": "npx live-server --port=8080"
  }},
  "dependencies": {{}},
  "devDependencies": {{
    "serve": "^14.0.0"
  }}
}}
"""

_DEP_FILE_SYSTEM = (
    "You are a build system expert. Output ONLY the requested dependency file content. "
    "No explanations. No markdown fences. Use realistic version pins."
)

_GOMOD_USER = """Generate a go.mod file for this project.
Project name (module path): {module_name}
Go version: 1.22
Imports used in code:
{imports_found}

Output go.mod content:"""

_CARGO_TOML_USER = """Generate a Cargo.toml for this Rust project.
Project name: {project_name}
Binary crate (has main.rs): {has_main}
Imports/crates used in code:
{imports_found}

Output Cargo.toml content:"""

_POM_XML_USER = """Generate a minimal pom.xml for this Java project.
Project name: {project_name}
Group ID: com.example
Artifact ID: {artifact_id}
Java version: 21
Build system: Maven
Dependencies used (import statements):
{imports_found}

Output pom.xml content:"""

_GEMFILE_USER = """Generate a Gemfile for this Ruby project.
Ruby version: 3.3
Gems required (from require statements):
{imports_found}

Output Gemfile content:"""

_COMPOSER_JSON_USER = """Generate a composer.json for this PHP project.
Project name: {project_name}
PHP version: ^8.3
Namespaces/packages used:
{imports_found}

Output composer.json content:"""

_PUBSPEC_YAML_USER = """Generate a pubspec.yaml for this Dart/Flutter project.
Project name: {project_name}
Flutter: {is_flutter}
Packages imported in code:
{imports_found}

Output pubspec.yaml content:"""

_REQUIREMENTS_SYSTEM = (
    "Output a requirements.txt file. List only third-party pip packages. "
    "No stdlib. No comments. One package per line with version pins. Output only the file content."
)

_REQUIREMENTS_USER = """Tech stack: {tech_stack}
Project type: {project_type}
Import statements found in project:
{imports_found}

Output requirements.txt (third-party packages only, one per line):"""

_PACKAGE_JSON_TEMPLATE = """{{
  "name": "{project_name}",
  "version": "1.0.0",
  "description": "{description}",
  "main": "{entrypoint}",
  "scripts": {{
    "start": "node {entrypoint}",
    "dev": "node {entrypoint}"
  }},
  "dependencies": {{}},
  "devDependencies": {{}}
}}
"""

# Standard Python stdlib modules — fallback for Python < 3.10
_STDLIB_FALLBACK: frozenset = frozenset({
    "os", "sys", "re", "json", "pathlib", "typing", "abc", "time", "datetime",
    "collections", "itertools", "functools", "copy", "math", "random", "hashlib",
    "hmac", "base64", "uuid", "io", "struct", "logging", "threading", "asyncio",
    "concurrent", "subprocess", "shutil", "tempfile", "glob", "fnmatch", "csv",
    "configparser", "argparse", "ast", "inspect", "importlib", "pkgutil",
    "contextlib", "dataclasses", "enum", "traceback", "warnings", "weakref",
    "gc", "platform", "socket", "ssl", "http", "urllib", "email", "html", "xml",
    "unittest", "doctest", "pdb", "profile", "timeit", "dis", "__future__",
    "builtins",
    # Commonly missed modules added for completeness:
    "secrets", "getpass", "textwrap", "string", "operator", "statistics",
    "decimal", "fractions", "array", "bisect", "heapq", "queue", "shelve",
    "pickle", "pprint", "types", "numbers", "sqlite3", "zlib", "gzip", "bz2",
    "zipfile", "tarfile", "atexit", "signal", "codecs", "unicodedata", "locale",
    "cmd", "shlex", "getopt", "difflib", "mimetypes", "cgi", "http",
    "multiprocessing", "selectors", "select", "fcntl", "termios", "tty",
    "pty", "pipes", "resource", "syslog", "optparse", "gettext",
})

# Use the authoritative stdlib list when available (Python 3.10+)
_STDLIB: frozenset = getattr(_sys, "stdlib_module_names", _STDLIB_FALLBACK)


# ---------------------------------------------------------------------------
# #16 — Plugin base class
# ---------------------------------------------------------------------------


class InfraPlugin(ABC):
    """Base class for infrastructure generation plugins.

    Each plugin handles one concern (gitignore, requirements, Dockerfile, etc.).
    Plugins are applied in order; each is responsible for checking if it should
    run and for writing its output to ctx.
    """

    @abstractmethod
    def can_handle(self, ctx: PhaseContext) -> bool:
        """Return True if this plugin should run for the given project context."""
        ...

    @abstractmethod
    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        """Apply this plugin. Writes files to ctx via phase._write_file()."""
        ...


class GitignorePlugin(InfraPlugin):
    def can_handle(self, ctx: PhaseContext) -> bool:
        return ".gitignore" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        # I1 — pick template based on project type, then tech_stack, then fallback
        gitignore = _GITIGNORE_MAP.get(ctx.project_type)
        if gitignore is None:
            has_node = any(t in ctx.tech_stack for t in ("javascript", "typescript", "react", "vue"))
            is_frontend = ctx.project_type in ("frontend_web", "web_app", "game")
            if is_frontend or has_node:
                gitignore = _GITIGNORE_NODE
            elif any(t in ctx.tech_stack for t in ("go", "golang")):
                gitignore = _GITIGNORE_GO
            elif any(t in ctx.tech_stack for t in ("rust", "cargo")):
                gitignore = _GITIGNORE_RUST
            elif any(t in ctx.tech_stack for t in ("java", "kotlin", "gradle", "maven")):
                gitignore = _GITIGNORE_JAVA
            elif any(t in ctx.tech_stack for t in ("csharp", "dotnet", "c#")):
                gitignore = _GITIGNORE_CSHARP
            elif any(t in ctx.tech_stack for t in ("php", "laravel", "symfony")):
                gitignore = _GITIGNORE_PHP
            elif any(t in ctx.tech_stack for t in ("ruby", "rails", "sinatra")):
                gitignore = _GITIGNORE_RUBY
            elif any(t in ctx.tech_stack for t in ("dart", "flutter")):
                gitignore = _GITIGNORE_DART
            else:
                gitignore = _GITIGNORE_PYTHON
        phase._write_file(ctx, ".gitignore", gitignore)
        ctx.logger.info("[Infra/GitignorePlugin] .gitignore written")


class RequirementsPlugin(InfraPlugin):
    def can_handle(self, ctx: PhaseContext) -> bool:
        return "python" in ctx.tech_stack and "requirements.txt" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        imports_found = phase._scan_python_imports(ctx)
        user = _REQUIREMENTS_USER.format(
            tech_stack=", ".join(ctx.tech_stack),
            project_type=ctx.project_type,
            imports_found="\n".join(imports_found[:40]),
        )
        content = phase._llm_call(ctx, _REQUIREMENTS_SYSTEM, user, role="coder", no_think=True, max_tokens=512)
        if content:
            content = re.sub(r"```[a-z]*\n?", "", content).strip()
            phase._write_file(ctx, "requirements.txt", content + "\n")
            ctx.logger.info("[Infra/RequirementsPlugin] requirements.txt written")


class PackageJsonPlugin(InfraPlugin):
    def can_handle(self, ctx: PhaseContext) -> bool:
        has_node = any(t in ctx.tech_stack for t in ("javascript", "typescript", "react", "vue"))
        is_frontend = ctx.project_type in ("frontend_web", "web_app")
        return (has_node or is_frontend) and "package.json" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        is_frontend = ctx.project_type in ("frontend_web", "web_app")
        project_name = ctx.project_name.lower().replace(" ", "-")
        description = ctx.project_description[:100]

        if is_frontend:
            content = _PACKAGE_JSON_FRONTEND.format(
                project_name=project_name,
                description=description,
            )
        else:
            # #12 — detect JS entrypoint
            entrypoint = phase._find_js_entrypoint(ctx)
            content = _PACKAGE_JSON_TEMPLATE.format(
                project_name=project_name,
                description=description,
                entrypoint=entrypoint,
            )
        phase._write_file(ctx, "package.json", content)
        ctx.logger.info("[Infra/PackageJsonPlugin] package.json written")


class DockerfilePlugin(InfraPlugin):
    def can_handle(self, ctx: PhaseContext) -> bool:
        return "Dockerfile" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        has_node = any(t in ctx.tech_stack for t in ("javascript", "typescript", "react", "vue"))
        is_frontend = ctx.project_type in ("frontend_web", "web_app", "game")
        has_go = ctx.project_type == "go_service" or any(t in ctx.tech_stack for t in ("go", "golang"))
        has_rust = ctx.project_type == "rust_project" or "rust" in ctx.tech_stack
        has_java = ctx.project_type == "java_app" or any(t in ctx.tech_stack for t in ("java", "spring"))
        has_csharp = ctx.project_type == "csharp_app" or any(t in ctx.tech_stack for t in ("csharp", "dotnet", "c#"))
        has_php = ctx.project_type == "php_app" or "php" in ctx.tech_stack
        has_ruby = ctx.project_type == "ruby_app" or "ruby" in ctx.tech_stack

        # I3 — multi-language Dockerfiles
        if is_frontend:
            content = _DOCKERFILE_FRONTEND
        elif has_go:
            content = _DOCKERFILE_GO
        elif has_rust:
            binary = ctx.project_name.lower().replace(" ", "_").replace("-", "_")
            content = _DOCKERFILE_RUST.format(binary_name=binary)
        elif has_java:
            content = _DOCKERFILE_JAVA
        elif has_csharp:
            assembly = phase._get_csharp_assembly_name(ctx)
            content = _DOCKERFILE_CSHARP.format(assembly_name=assembly)
        elif has_php:
            content = _DOCKERFILE_PHP
        elif has_ruby:
            entrypoint = phase._find_ruby_entrypoint(ctx)
            content = _DOCKERFILE_RUBY.format(entrypoint=entrypoint)
        elif has_node:
            entrypoint = phase._find_js_entrypoint(ctx)
            content = _DOCKERFILE_NODE.format(entrypoint=entrypoint)
        else:
            entrypoint = phase._find_python_entrypoint(ctx)  # #12
            content = _DOCKERFILE_PYTHON.format(entrypoint=entrypoint)

        phase._write_file(ctx, "Dockerfile", content)
        ctx.logger.info("[Infra/DockerfilePlugin] Dockerfile written (entrypoint inferred)")


class GoModPlugin(InfraPlugin):
    """I2 — Generate go.mod for Go projects."""

    def can_handle(self, ctx: PhaseContext) -> bool:
        has_go = any(p.endswith(".go") for p in ctx.generated_files)
        return has_go and "go.mod" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        imports_found = phase._scan_go_imports(ctx)
        module_name = f"github.com/example/{ctx.project_name.lower().replace(' ', '-')}"
        user = _GOMOD_USER.format(module_name=module_name, imports_found="\n".join(imports_found[:20]))
        content = phase._llm_call(ctx, _DEP_FILE_SYSTEM, user, role="coder", no_think=True, max_tokens=512)
        if content:
            content = re.sub(r"```[a-z]*\n?", "", content).strip()
            phase._write_file(ctx, "go.mod", content + "\n")
            ctx.logger.info("[Infra/GoModPlugin] go.mod written")


class CargoTomlPlugin(InfraPlugin):
    """I2 — Generate Cargo.toml for Rust projects."""

    def can_handle(self, ctx: PhaseContext) -> bool:
        has_rust = any(p.endswith(".rs") for p in ctx.generated_files)
        return has_rust and "Cargo.toml" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        imports_found = phase._scan_rust_imports(ctx)
        has_main = any(p == "src/main.rs" or p == "main.rs" for p in ctx.generated_files)
        project_name = ctx.project_name.lower().replace(" ", "-")
        user = _CARGO_TOML_USER.format(
            project_name=project_name,
            has_main=str(has_main),
            imports_found="\n".join(imports_found[:20]),
        )
        content = phase._llm_call(ctx, _DEP_FILE_SYSTEM, user, role="coder", no_think=True, max_tokens=512)
        if content:
            content = re.sub(r"```[a-z]*\n?", "", content).strip()
            phase._write_file(ctx, "Cargo.toml", content + "\n")
            ctx.logger.info("[Infra/CargoTomlPlugin] Cargo.toml written")


class PomXmlPlugin(InfraPlugin):
    """I2 — Generate pom.xml for Java projects."""

    def can_handle(self, ctx: PhaseContext) -> bool:
        has_java = any(p.endswith(".java") for p in ctx.generated_files)
        return has_java and "pom.xml" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        imports_found = phase._scan_java_imports(ctx)
        artifact = ctx.project_name.lower().replace(" ", "-")
        user = _POM_XML_USER.format(
            project_name=ctx.project_name,
            artifact_id=artifact,
            imports_found="\n".join(imports_found[:30]),
        )
        content = phase._llm_call(ctx, _DEP_FILE_SYSTEM, user, role="coder", no_think=True, max_tokens=512)
        if content:
            content = re.sub(r"```[a-z]*\n?", "", content).strip()
            phase._write_file(ctx, "pom.xml", content + "\n")
            ctx.logger.info("[Infra/PomXmlPlugin] pom.xml written")


class GemfilePlugin(InfraPlugin):
    """I2 — Generate Gemfile for Ruby projects."""

    def can_handle(self, ctx: PhaseContext) -> bool:
        has_ruby = any(p.endswith(".rb") for p in ctx.generated_files)
        return has_ruby and "Gemfile" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        imports_found = phase._scan_ruby_imports(ctx)
        user = _GEMFILE_USER.format(imports_found="\n".join(imports_found[:20]))
        content = phase._llm_call(ctx, _DEP_FILE_SYSTEM, user, role="coder", no_think=True, max_tokens=512)
        if content:
            content = re.sub(r"```[a-z]*\n?", "", content).strip()
            phase._write_file(ctx, "Gemfile", content + "\n")
            ctx.logger.info("[Infra/GemfilePlugin] Gemfile written")


class ComposerJsonPlugin(InfraPlugin):
    """I2 — Generate composer.json for PHP projects."""

    def can_handle(self, ctx: PhaseContext) -> bool:
        has_php = any(p.endswith(".php") for p in ctx.generated_files)
        return has_php and "composer.json" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        imports_found = phase._scan_php_imports(ctx)
        project_name = f"example/{ctx.project_name.lower().replace(' ', '-')}"
        user = _COMPOSER_JSON_USER.format(
            project_name=project_name,
            imports_found="\n".join(imports_found[:20]),
        )
        content = phase._llm_call(ctx, _DEP_FILE_SYSTEM, user, role="coder", no_think=True, max_tokens=512)
        if content:
            content = re.sub(r"```[a-z]*\n?", "", content).strip()
            phase._write_file(ctx, "composer.json", content + "\n")
            ctx.logger.info("[Infra/ComposerJsonPlugin] composer.json written")


class PubspecYamlPlugin(InfraPlugin):
    """I2 — Generate pubspec.yaml for Dart/Flutter projects."""

    def can_handle(self, ctx: PhaseContext) -> bool:
        has_dart = any(p.endswith(".dart") for p in ctx.generated_files)
        return has_dart and "pubspec.yaml" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        imports_found = phase._scan_dart_imports(ctx)
        is_flutter = ctx.project_type == "flutter_app" or "flutter" in ctx.tech_stack
        user = _PUBSPEC_YAML_USER.format(
            project_name=ctx.project_name.lower().replace(" ", "_"),
            is_flutter=str(is_flutter),
            imports_found="\n".join(imports_found[:20]),
        )
        content = phase._llm_call(ctx, _DEP_FILE_SYSTEM, user, role="coder", no_think=True, max_tokens=512)
        if content:
            content = re.sub(r"```[a-z]*\n?", "", content).strip()
            phase._write_file(ctx, "pubspec.yaml", content + "\n")
            ctx.logger.info("[Infra/PubspecYamlPlugin] pubspec.yaml written")


# ---------------------------------------------------------------------------
# InfraPhase
# ---------------------------------------------------------------------------


class InfraPhase(BasePhase):
    phase_id = "6"
    phase_label = "Infra"

    # #16 — Ordered list of plugins (ClassVar: shared, do not mutate at runtime)
    PLUGINS: ClassVar[List[InfraPlugin]] = [
        GitignorePlugin(),
        RequirementsPlugin(),
        PackageJsonPlugin(),
        GoModPlugin(),
        CargoTomlPlugin(),
        PomXmlPlugin(),
        GemfilePlugin(),
        ComposerJsonPlugin(),
        PubspecYamlPlugin(),
        DockerfilePlugin(),
    ]

    def run(self, ctx: PhaseContext) -> None:
        for plugin in self.PLUGINS:
            if plugin.can_handle(ctx):
                try:
                    plugin.apply(self, ctx)
                except Exception as e:
                    ctx.logger.warning(f"[Infra] Plugin {plugin.__class__.__name__} failed: {e}")
        ctx.logger.info("[Infra] Infrastructure files complete")

    # ----------------------------------------------------------------
    # #12 — Smart entrypoint detection
    # ----------------------------------------------------------------

    @staticmethod
    def _find_python_entrypoint(ctx: PhaseContext) -> str:
        """Find the Python entry file: lowest-priority file with no importers.

        Preference order:
        1. File named main.py, app.py, cli.py, run.py, server.py
        2. Leaf node in the import graph (no other file imports it)
        3. Fallback to 'main.py'
        """
        preferred = ("main.py", "app.py", "cli.py", "run.py", "server.py")
        for name in preferred:
            if name in ctx.generated_files:
                return name

        # Find blueprint leaf nodes (files that no one imports) among Python files
        all_imports: Set[str] = set()
        for fp in ctx.blueprint:
            all_imports.update(fp.imports)

        py_files = [fp.path for fp in ctx.blueprint if fp.path.endswith(".py") and fp.path not in all_imports]
        if py_files:
            # Pick the one with highest priority number (generated last = typically entry)
            py_files.sort(key=lambda p: next((fp.priority for fp in ctx.blueprint if fp.path == p), 0), reverse=True)
            return py_files[0]

        return "main.py"

    @staticmethod
    def _find_js_entrypoint(ctx: PhaseContext) -> str:
        """Find the JS/TS entry file using the same leaf-node heuristic."""
        preferred = ("index.js", "main.js", "app.js", "server.js", "index.ts", "main.ts")
        for name in preferred:
            if name in ctx.generated_files:
                return name

        all_imports: Set[str] = set()
        for fp in ctx.blueprint:
            all_imports.update(fp.imports)

        js_files = [fp.path for fp in ctx.blueprint if fp.path.endswith((".js", ".ts")) and fp.path not in all_imports]
        if js_files:
            js_files.sort(key=lambda p: next((fp.priority for fp in ctx.blueprint if fp.path == p), 0), reverse=True)
            return js_files[0]

        return "index.js"

    @staticmethod
    def _find_ruby_entrypoint(ctx: PhaseContext) -> str:
        preferred = ("app.rb", "main.rb", "server.rb", "config.ru", "Rakefile")
        for name in preferred:
            if name in ctx.generated_files:
                return name
        ruby_files = [p for p in ctx.generated_files if p.endswith(".rb")]
        return ruby_files[0] if ruby_files else "app.rb"

    @staticmethod
    def _get_csharp_assembly_name(ctx: PhaseContext) -> str:
        """Determine the .NET assembly name for the Dockerfile ENTRYPOINT.

        Resolution order:
        1. Filename stem of any *.csproj in generated_files
           (e.g. 'CrmBasico.csproj' → 'CrmBasico')
        2. <AssemblyName> element inside .csproj content
        3. ctx.project_name with spaces stripped (legacy fallback)
        """
        import re as _re

        # Priority 1: stem of the first .csproj file found
        for path in ctx.generated_files:
            if path.endswith(".csproj"):
                stem = path.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
                if stem:
                    return stem

        # Priority 2: explicit <AssemblyName> tag inside any .csproj content
        for path, content in ctx.generated_files.items():
            if not path.endswith(".csproj"):
                continue
            m = _re.search(r"<AssemblyName>\s*([^\s<]+)\s*</AssemblyName>", content)
            if m:
                return m.group(1).strip()

        # Priority 3: fallback to project name
        return ctx.project_name.replace(" ", "")

    # ----------------------------------------------------------------
    # Utilities (used by plugins)
    # ----------------------------------------------------------------

    @staticmethod
    def _scan_python_imports(ctx: PhaseContext) -> List[str]:
        """Extract third-party import names from all .py files."""
        # Build set of local package/module names from the generated project structure
        local_packages: Set[str] = set()
        for p in ctx.generated_files:
            parts = p.replace("\\", "/").split("/")
            # top-level directory (e.g. "vault" from "vault/storage.py")
            # or top-level Python file stem (e.g. "main" from "main.py")
            local_packages.add(parts[0].split(".")[0])

        third_party: Set[str] = set()
        for path, content in ctx.generated_files.items():
            if not path.endswith(".py"):
                continue
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("import "):
                    mod = line.split()[1].split(".")[0]
                    if mod not in _STDLIB and mod not in local_packages:
                        third_party.add(f"import {mod}")
                elif line.startswith("from "):
                    parts = line.split()
                    if len(parts) >= 2:
                        mod = parts[1].split(".")[0]
                        if mod not in _STDLIB and mod not in local_packages and not mod.startswith("."):
                            third_party.add(f"from {mod}")
        return sorted(third_party)

    @staticmethod
    def _scan_go_imports(ctx: PhaseContext) -> List[str]:
        """Extract external module imports from .go files."""
        import re as _re

        external: Set[str] = set()
        stdlib_prefixes = (
            "fmt",
            "os",
            "io",
            "net",
            "http",
            "math",
            "sync",
            "time",
            "strings",
            "strconv",
            "errors",
            "context",
            "log",
            "sort",
            "path",
            "bufio",
            "bytes",
            "encoding",
            "flag",
            "runtime",
        )
        for path, content in ctx.generated_files.items():
            if not path.endswith(".go"):
                continue
            for pkg in _re.findall(r'"([^"]+)"', content):
                if not any(pkg.startswith(p) for p in stdlib_prefixes):
                    external.add(pkg)
        return sorted(external)

    @staticmethod
    def _scan_rust_imports(ctx: PhaseContext) -> List[str]:
        """Extract external crate names from Rust files."""
        import re as _re

        crates: Set[str] = set()
        for path, content in ctx.generated_files.items():
            if not path.endswith(".rs"):
                continue
            for crate in _re.findall(r"^(?:extern crate|use)\s+([\w]+)", content, _re.MULTILINE):
                if crate not in ("std", "core", "alloc", "self", "super", "crate"):
                    crates.add(crate)
        return sorted(crates)

    @staticmethod
    def _scan_java_imports(ctx: PhaseContext) -> List[str]:
        """Extract non-stdlib import statements from Java files."""
        import re as _re

        imports: Set[str] = set()
        stdlib_prefixes = ("java.", "javax.", "sun.", "com.sun.")
        for path, content in ctx.generated_files.items():
            if not path.endswith(".java"):
                continue
            for imp in _re.findall(r"^import\s+([\w.]+);", content, _re.MULTILINE):
                if not any(imp.startswith(p) for p in stdlib_prefixes):
                    imports.add(imp)
        return sorted(imports)

    @staticmethod
    def _scan_ruby_imports(ctx: PhaseContext) -> List[str]:
        """Extract gem names from require statements in Ruby files."""
        import re as _re

        gems: Set[str] = set()
        stdlib_gems = {
            "json",
            "yaml",
            "csv",
            "net/http",
            "uri",
            "date",
            "time",
            "fileutils",
            "pathname",
            "logger",
            "open3",
            "tempfile",
        }
        for path, content in ctx.generated_files.items():
            if not path.endswith(".rb"):
                continue
            for gem in _re.findall(r"^require\s+['\"]([^'\"]+)['\"]", content, _re.MULTILINE):
                if gem not in stdlib_gems:
                    gems.add(gem)
        return sorted(gems)

    @staticmethod
    def _scan_php_imports(ctx: PhaseContext) -> List[str]:
        """Extract use/require statements from PHP files."""
        import re as _re

        namespaces: Set[str] = set()
        for path, content in ctx.generated_files.items():
            if not path.endswith(".php"):
                continue
            for ns in _re.findall(r"^use\s+([\w\\]+)", content, _re.MULTILINE):
                top = ns.split("\\")[0]
                if top not in ("App", "Exception", "Closure", "stdClass"):
                    namespaces.add(ns)
        return sorted(namespaces)

    @staticmethod
    def _scan_dart_imports(ctx: PhaseContext) -> List[str]:
        """Extract package imports from Dart files."""
        import re as _re

        packages: Set[str] = set()
        for path, content in ctx.generated_files.items():
            if not path.endswith(".dart"):
                continue
            for pkg in _re.findall(r"^import\s+'package:([^/']+)", content, _re.MULTILINE):
                if pkg not in ("flutter", "dart"):
                    packages.add(pkg)
        return sorted(packages)
