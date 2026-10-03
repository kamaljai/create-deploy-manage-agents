#!/usr/bin/env python3
"""Inventory a skill or agent project and flag portability risks without executing source files."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".sh",
    ".ps1",
}
SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__"}
MAX_SCAN_BYTES = 1_000_000

PATTERNS: dict[str, tuple[str, ...]] = {
    "ui_or_host_dependency": (
        r"\bcomputer[-_ ]?use\b",
        r"\bcontrol[-_ ]?(?:chrome|browser)\b",
        r"\bosascript\b",
        r"\bxdg-open\b",
        r"\bopen\s+-a\b",
    ),
    "codex_or_connector_dependency": (
        r"\bmcp__",
        r"\b(?:gmail|outlook|calendar|slack|notion|figma)\b",
        r"\brequest_user_input\b",
        r"\bcreate_thread\b",
    ),
    "shell_or_process_execution": (
        r"\bsubprocess\b",
        r"\bos\.system\b",
        r"\bchild_process\b",
        r"\beval\s*\(",
        r"\bexec\s*\(",
    ),
    "privileged_or_docker_access": (
        r"/var/run/docker\.sock",
        r"\bprivileged\s*:\s*true\b",
        r"\bsudo\b",
        r"\bchmod\s+777\b",
    ),
    "external_side_effect": (
        r"\b(send|publish|post|delete|purchase|transfer|deploy)\b",
        r"\bcreate_(?:event|issue|pull_request)\b",
    ),
    "filesystem_assumption": (
        r"(?:~|\$HOME|/Users/|/home/)",
        r"[A-Za-z]:\\\\",
    ),
    "data_store_reference": (
        r"\b(?:postgres(?:ql)?|psycopg|asyncpg|mysql|sqlite3?|sqlalchemy|mongo(?:db)?|redis)\b",
        r"\b(?:chroma(?:db)?|pinecone|qdrant|weaviate|pgvector|faiss|lancedb|milvus)\b",
        r"\b(?:bigquery|firestore|spanner|alloydb|dynamodb|cosmos(?:db)?|snowflake)\b",
        r"\b(?:s3://|gs://|boto3|google\.cloud\.storage|azure\.storage)\b",
        r"\b(?:DATABASE_URL|REDIS_URL|MONGO(?:DB)?_URI)\b",
    ),
    "credential_reference": (
        r"\b[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)\b",
        r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\b",
    ),
}


FRAMEWORK_PATTERNS: dict[str, tuple[str, ...]] = {
    "adk": (
        r"\bfrom google\.adk\b",
        r"\bimport google\.adk\b",
        r"\bgoogle-adk\b",
        r"\broot_agent\s*=",
    ),
    "crewai": (r"\bfrom crewai\b", r"\bimport crewai\b", r"@CrewBase\b", r"^\s*crewai\b"),
    "claude-agent-sdk": (
        r"\bclaude_agent_sdk\b",
        r"@anthropic-ai/claude-agent-sdk",
        r"\bclaude-agent-sdk\b",
        r"\bClaudeAgentOptions\b",
    ),
}
ENV_VAR_PATTERNS = (
    r"os\.(?:getenv|environ\.get)\(\s*[\"']([A-Z][A-Z0-9_]+)[\"']",
    r"os\.environ\[\s*[\"']([A-Z][A-Z0-9_]+)[\"']\s*\]",
    r"process\.env\.([A-Z][A-Z0-9_]+)",
    r"process\.env\[\s*[\"']([A-Z][A-Z0-9_]+)[\"']\s*\]",
)
ENV_FILE_NAMES = {".env.example", ".env.sample", ".env.template", "env.example"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_directory", type=Path, help="Skill or agent project directory")
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
    return parser.parse_args()


def iter_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part in SKIP_PARTS for part in path.parts)
    )


def read_text(path: Path) -> str | None:
    is_env_file = path.name in ENV_FILE_NAMES
    if (path.suffix.lower() not in TEXT_SUFFIXES and not is_env_file) or (
        path.stat().st_size > MAX_SCAN_BYTES
    ):
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def detect_kinds(root: Path, texts: dict[Path, str]) -> list[str]:
    kinds = ["skill"] if (root / "SKILL.md").is_file() else []
    for kind, expressions in FRAMEWORK_PATTERNS.items():
        regexes = [re.compile(expression, re.MULTILINE) for expression in expressions]
        if any(regex.search(text) for text in texts.values() for regex in regexes):
            kinds.append(kind)
    return kinds


def env_var_names(texts: dict[Path, str]) -> list[str]:
    """Names only; values are never read from env files."""
    names: set[str] = set()
    for path, text in texts.items():
        if path.name in ENV_FILE_NAMES:
            names.update(re.findall(r"^\s*([A-Z][A-Z0-9_]+)\s*=", text, re.MULTILINE))
            continue
        for expression in ENV_VAR_PATTERNS:
            names.update(re.findall(expression, text))
    return sorted(names)


def scan_text(text: str) -> dict[str, list[int]]:
    matches: dict[str, list[int]] = {}
    for category, expressions in PATTERNS.items():
        lines: set[int] = set()
        for expression in expressions:
            regex = re.compile(expression, re.IGNORECASE)
            for match in regex.finditer(text):
                lines.add(text.count("\n", 0, match.start()) + 1)
        if lines:
            matches[category] = sorted(lines)[:20]
    return matches


def main() -> int:
    args = parse_args()
    root = args.source_directory.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    files = iter_files(root)
    texts = {path: text for path in files if (text := read_text(path)) is not None}
    kinds = detect_kinds(root, texts)
    suffixes = Counter(path.suffix.lower() or "[no extension]" for path in files)
    findings: list[dict[str, object]] = []
    for path, text in texts.items():
        if path.name in ENV_FILE_NAMES:
            continue
        categories = scan_text(text)
        if categories:
            findings.append(
                {
                    "path": str(path.relative_to(root)),
                    "categories": categories,
                }
            )

    executables = [
        str(path.relative_to(root))
        for path in files
        if path.suffix.lower() in {".py", ".js", ".ts", ".sh", ".ps1"}
    ]
    large_or_binary = [
        str(path.relative_to(root))
        for path in files
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > MAX_SCAN_BYTES
    ]
    report = {
        "source_directory": str(root),
        "detected_kinds": kinds,
        "env_var_names": env_var_names(texts),
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "file_types": dict(sorted(suffixes.items())),
        "executable_source_files": executables,
        "large_or_binary_files": large_or_binary,
        "findings": findings,
        "notes": [
            "Keyword findings require human review and are not proof of incompatibility.",
            "The scanner does not execute source files or reveal credential values.",
            "Review licensing, external services, side effects, and runtime requirements manually.",
            "detected_kinds lists every framework seen; confirm the entrypoint with the user.",
        ],
    }
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

