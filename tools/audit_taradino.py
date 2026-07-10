#!/usr/bin/env python3
"""Inventory Taradino desktop/platform dependencies before N64 compilation."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SOURCE_SUFFIXES = {".c", ".h"}
PATTERNS = {
    "SDL video/input/timing": re.compile(r"\bSDL_[A-Za-z0-9_]+\b|#\s*include\s*[<\"]SDL(?:2)?/?.*?[>\"]"),
    "SDL mixer/audio": re.compile(r"\bMix_[A-Za-z0-9_]+\b|SDL_mixer"),
    "networking": re.compile(r"\b(socket|connect|bind|listen|accept|sendto|recvfrom|gethostbyname|select)\s*\("),
    "POSIX filesystem/process": re.compile(r"\b(chdir|mkdir|opendir|readdir|closedir|getenv|system|fork|exec[a-z]*)\s*\("),
    "unaligned/native endian risk": re.compile(r"\*\s*\(\s*(?:u?int(?:16|32|64)_t|short|long)\s*\*\s*\)"),
}
SYMBOL_PATTERN = re.compile(r"\b(?:SDL|Mix)_[A-Za-z0-9_]+\b")
INCLUDE_PATTERN = re.compile(r"^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]", re.MULTILINE)


@dataclass(frozen=True)
class FileAudit:
    path: str
    lines: int
    categories: list[str]
    symbols: list[str]
    includes: list[str]


def iter_sources(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
            yield path


def audit(root: Path) -> dict:
    files: list[FileAudit] = []
    category_counts: Counter[str] = Counter()
    symbol_counts: Counter[str] = Counter()

    for path in iter_sources(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        categories = [name for name, pattern in PATTERNS.items() if pattern.search(text)]
        symbols = sorted(set(SYMBOL_PATTERN.findall(text)))
        includes = sorted(set(INCLUDE_PATTERN.findall(text)))
        for category in categories:
            category_counts[category] += 1
        for symbol in symbols:
            symbol_counts[symbol] += 1
        files.append(
            FileAudit(
                path=path.relative_to(root).as_posix(),
                lines=text.count("\n") + (0 if text.endswith("\n") or not text else 1),
                categories=categories,
                symbols=symbols,
                includes=includes,
            )
        )

    direct = [item for item in files if item.categories]
    neutral = [item for item in files if not item.categories]
    return {
        "root": str(root),
        "source_file_count": len(files),
        "direct_dependency_file_count": len(direct),
        "candidate_platform_neutral_file_count": len(neutral),
        "category_counts": dict(sorted(category_counts.items())),
        "most_common_desktop_symbols": symbol_counts.most_common(40),
        "files": [asdict(item) for item in files],
    }


def markdown(report: dict) -> str:
    lines = [
        "# Taradino N64 dependency audit",
        "",
        f"- Source files scanned: **{report['source_file_count']}**",
        f"- Files with direct desktop/platform dependencies: **{report['direct_dependency_file_count']}**",
        f"- Candidate platform-neutral files: **{report['candidate_platform_neutral_file_count']}**",
        "",
        "## Dependency categories",
        "",
        "| Category | Files |",
        "|---|---:|",
    ]
    for name, count in report["category_counts"].items():
        lines.append(f"| {name} | {count} |")
    if not report["category_counts"]:
        lines.append("| No configured dependency signatures found | 0 |")

    lines.extend(["", "## Highest-priority replacement files", ""])
    dependent = [item for item in report["files"] if item["categories"]]
    dependent.sort(key=lambda item: (-len(item["categories"]), item["path"]))
    for item in dependent:
        categories = ", ".join(item["categories"])
        symbols = ", ".join(item["symbols"][:8]) or "no SDL/Mix symbols"
        lines.append(f"- `{item['path']}` — {categories}; {symbols}")

    lines.extend(["", "## Candidate platform-neutral compilation set", ""])
    for item in report["files"]:
        if not item["categories"] and item["path"].endswith(".c"):
            lines.append(f"- `{item['path']}`")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a static dependency inventory, not proof that a file already compiles on N64. "
            "The next compile pass can begin with the candidate-neutral C files, then replace the "
            "reported SDL, mixer, networking, filesystem, timing, and endian-sensitive boundaries.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Taradino source tree or its rott directory")
    parser.add_argument("--out", type=Path, default=Path("build/reports"))
    args = parser.parse_args()

    if not args.source.is_dir():
        parser.error(f"source directory does not exist: {args.source}")

    report = audit(args.source)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "taradino-port-audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "taradino-port-audit.md").write_text(markdown(report), encoding="utf-8")
    print(
        f"Audited {report['source_file_count']} source files; "
        f"{report['direct_dependency_file_count']} need direct platform work"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
