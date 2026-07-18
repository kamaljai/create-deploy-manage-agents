#!/usr/bin/env python3
"""Inventory a skill and flag portability risks without executing source files."""

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
    "credential_reference": (
        r"\b[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)\b",
        r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\b",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_directory", type=Path)
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
    return parser.parse_args()


def iter_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part in SKIP_PARTS for part in path.parts)
    )


def scan_text(path: Path) -> dict[str, list[int]]:
    if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > MAX_SCAN_BYTES:
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

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
    root = args.skill_directory.expanduser().resolve()
    skill_md = root / "SKILL.md"
    if not root.is_dir() or not skill_md.is_file():
        raise SystemExit(f"Not a skill directory (missing SKILL.md): {root}")

    files = iter_files(root)
    suffixes = Counter(path.suffix.lower() or "[no extension]" for path in files)
    findings: list[dict[str, object]] = []
    for path in files:
        categories = scan_text(path)
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
        "skill_directory": str(root),
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
        ],
    }
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

