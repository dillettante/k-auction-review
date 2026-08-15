#!/usr/bin/env python3
"""Fail a public-release check when likely secrets or real-case folders are included.

Run this before committing or publishing. It checks text files only and does
not print matching values.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


EXCLUDED_DIRECTORIES = {".git", "private", "tmp", "samples", "__pycache__"}
TEXT_EXTENSIONS = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".ini", ".txt", ".html", ".js", ".sh"}
PATTERNS = {
    "embedded public-data key assignment": re.compile(r"AUCTION_RTMS_API_KEY\s*[=:]\s*['\"]?[^\s'\"]{20,}", re.I),
    "generic private key assignment": re.compile(r"(?:api[_-]?key|service[_-]?key|secret)\s*[=:]\s*['\"][A-Za-z0-9%+/=_-]{20,}", re.I),
}


def files(root: Path) -> list[Path]:
    return [
        path for path in root.rglob("*")
        if path.is_file() and not any(part in EXCLUDED_DIRECTORIES for part in path.relative_to(root).parts)
        and path.suffix.lower() in TEXT_EXTENSIONS
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()
    failures: list[str] = []
    for path in files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{path.relative_to(root)}: {label}")
    for sensitive in ("private", "samples"):
        if (root / sensitive).exists() and sensitive not in (root / ".gitignore").read_text(encoding="utf-8"):
            failures.append(f".gitignore: missing {sensitive}/ exclusion")
    if failures:
        print("public-release: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"public-release: PASS files={len(files(root))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
