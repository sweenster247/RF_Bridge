#!/usr/bin/env python3
"""Verify RF Bridge release version metadata stays in sync."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


def read_text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def require_match(label, pattern, text):
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise SystemExit(f"Could not find {label}.")
    return match.group(1)


def main():
    expected = require_match(
        "pyproject.toml version",
        r'^version\s*=\s*"([^"]+)"',
        read_text("pyproject.toml"),
    )

    checks = {
        "rf_bridge/version.py": require_match(
            "rf_bridge/version.py version",
            r'__version__\s*=\s*"([^"]+)"',
            read_text("rf_bridge/version.py"),
        ),
        "rf_bridge/__init__.py": require_match(
            "rf_bridge/__init__.py version",
            r'__version__\s*=\s*"([^"]+)"',
            read_text("rf_bridge/__init__.py"),
        ),
        "rf-bridge.spec CFBundleShortVersionString": require_match(
            "CFBundleShortVersionString",
            r"'CFBundleShortVersionString': '([^']+)'",
            read_text("rf-bridge.spec"),
        ),
        "rf-bridge.spec CFBundleVersion": require_match(
            "CFBundleVersion",
            r"'CFBundleVersion': '([^']+)'",
            read_text("rf-bridge.spec"),
        ),
        "README latest heading": require_match(
            "README latest heading",
            r"## What.s New in v([0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?)",
            read_text("README.md"),
        ),
        "CHANGELOG latest heading": require_match(
            "CHANGELOG latest heading",
            r"## v([0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?)",
            read_text("CHANGELOG.md"),
        ),
    }

    mismatches = [
        f"{label}: {version} != {expected}"
        for label, version in checks.items()
        if version != expected
    ]
    if mismatches:
        print("Version metadata mismatch:")
        for mismatch in mismatches:
            print(f"  - {mismatch}")
        return 1

    print(f"Version metadata OK: {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
