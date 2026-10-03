#!/usr/bin/env python3
"""Create a Dockerized agent package from a skill or an ADK/CrewAI/Claude Agent SDK agent."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path


PROVIDERS = {"gemini", "ollama", "openai", "anthropic"}
TRANSPORTS = {"http", "cli", "both"}
RUNTIMES = {"docker", "microvm"}
# Source kind -> framework runner asset (None: skill packaged as a system prompt).
SOURCE_KINDS = {
    "skill": None,
    "adk": "adk.py",
    "crewai": "crewai.py",
    "claude-agent-sdk": "claude_agent_sdk.py",
}
TEXT_SUFFIXES = {
    ".dockerignore",
    ".example",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SKIP_NAMES = {
    ".env",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
SECRET_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Human-readable agent name")
    parser.add_argument(
        "--source-dir", "--skill-dir", dest="source_dir", required=True, type=Path,
        help="Skill directory or agent project root",
    )
    parser.add_argument("--source-kind", required=True, choices=sorted(SOURCE_KINDS))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    parser.add_argument("--model", required=True)
    parser.add_argument("--transport", default="both", choices=sorted(TRANSPORTS))
    parser.add_argument(
        "--runtime",
        required=True,
        choices=sorted(RUNTIMES),
        help="docker: plain Docker container; microvm: Docker Sandboxes microVM",
    )
    parser.add_argument("--input-description", required=True)
    parser.add_argument("--output-description", required=True)
    parser.add_argument("--source-url", help="Git repository URL, when applicable")
    parser.add_argument("--source-ref", help="Requested Git ref, when applicable")
    parser.add_argument("--source-commit", help="Resolved Git commit, when applicable")
    parser.add_argument("--source-subdir", help="Source path inside the repository")
    return parser.parse_args()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("Agent name must contain at least one letter or number")
    return slug[:63].rstrip("-")


def package_name(slug: str) -> str:
    name = slug.replace("-", "_")
    if name[0].isdigit():
        name = f"agent_{name}"
    return name


def _ignored_names(
    directory: str, names: list[str], *, allow_env_example: bool
) -> set[str]:
    base = Path(directory)
    return {
        name
        for name in names
        if name in SKIP_NAMES
        or name == ".env"
        or (name.startswith(".env.") and not (allow_env_example and name == ".env.example"))
        or (base / name).suffix.lower() in SECRET_SUFFIXES
    }


def ignored_source_names(directory: str, names: list[str]) -> set[str]:
    return _ignored_names(directory, names, allow_env_example=False)


def ignored_template_names(directory: str, names: list[str]) -> set[str]:
    return _ignored_names(directory, names, allow_env_example=True)


def copy_source(source: Path, destination: Path) -> None:
    symlinks = [path for path in source.rglob("*") if path.is_symlink()]
    if symlinks:
        relative = ", ".join(str(path.relative_to(source)) for path in symlinks[:5])
        raise SystemExit(f"Refusing to package source symlinks: {relative}")

    shutil.copytree(source, destination, ignore=ignored_source_names)


def substitute_tree(root: Path, replacements: dict[str, str]) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in TEXT_SUFFIXES and path.name not in {"Dockerfile", ".dockerignore"}:
            continue
        text = path.read_text(encoding="utf-8")
        for marker, value in replacements.items():
            text = text.replace(marker, value)
        path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    source_dir = args.source_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    template_dir = assets_dir / "agent-template"
    runner_asset = SOURCE_KINDS[args.source_kind]

    if args.source_kind == "skill" and not (source_dir / "SKILL.md").is_file():
        raise SystemExit(f"Source is not a skill directory: {source_dir}")
    if not source_dir.is_dir():
        raise SystemExit(f"Source directory not found: {source_dir}")
    if not template_dir.is_dir():
        raise SystemExit(f"Bundled template not found: {template_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty directory: {output_dir}")

    slug = slugify(args.name)
    pkg = package_name(slug)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template_dir, output_dir, dirs_exist_ok=True, ignore=ignored_template_names)

    replacements = {
        "__AGENT_NAME__": args.name,
        "__AGENT_SLUG__": slug,
        "__PACKAGE_NAME__": pkg,
        "__DEFAULT_PROVIDER__": args.provider,
        "__DEFAULT_MODEL__": args.model,
        "__TRANSPORT__": args.transport,
        "__INPUT_DESCRIPTION__": args.input_description,
        "__OUTPUT_DESCRIPTION__": args.output_description,
    }
    substitute_tree(output_dir, replacements)
    if args.runtime == "docker":
        shutil.rmtree(output_dir / "deploy")
    else:
        (output_dir / "deploy" / "microvm.sh").chmod(0o755)
    if runner_asset is None:
        copy_source(source_dir, output_dir / "skill_source")
    else:
        copy_source(source_dir, output_dir / "agent_source")
        runner = (assets_dir / "framework-runners" / runner_asset).read_text(encoding="utf-8")
        for marker, value in replacements.items():
            runner = runner.replace(marker, value)
        (output_dir / "src" / "skill_agent" / "runner.py").write_text(runner, encoding="utf-8")
        dockerfile = output_dir / "Dockerfile"
        text = dockerfile.read_text(encoding="utf-8")
        text = text.replace(
            "COPY --chown=10001:10001 skill_source ./skill_source",
            "COPY --chown=10001:10001 agent_source ./agent_source",
        ).replace("SKILL_ROOT=/app/skill_source", "PYTHONPATH=/app/agent_source")
        dockerfile.write_text(text, encoding="utf-8")

    provenance = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_kind": args.source_kind,
        "source_local_path": str(source_dir),
        "source_url": args.source_url,
        "source_ref": args.source_ref,
        "source_commit": args.source_commit,
        "source_subdir": args.source_subdir,
        "provider": args.provider,
        "model": args.model,
        "transport": args.transport,
        "runtime": args.runtime,
        "input_contract": args.input_description,
        "output_contract": args.output_description,
    }
    (output_dir / "skill-provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Created {args.runtime} agent package at {output_dir}")
    if runner_asset is None:
        print("Next: replace generic schemas with the agreed contract, add adapters, run tests.")
    else:
        print(
            "Next: wire src/skill_agent/runner.py into service/api/cli in place of the "
            "prompt + model gateway, add the agent's dependencies, and run tests."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
