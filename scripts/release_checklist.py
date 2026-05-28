#!/usr/bin/env python3
"""Run lightweight RF Bridge release-prep checks."""

from pathlib import Path
import os
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run(label, command):
    print(f"\n== {label} ==")
    env = os.environ.copy()
    env.setdefault("PYTHONPYCACHEPREFIX", "/private/tmp/rf_bridge_pycache")
    result = subprocess.run(command, cwd=ROOT, env=env)
    if result.returncode:
        raise SystemExit(result.returncode)


def current_version():
    text = (ROOT / "rf_bridge" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("Could not read rf_bridge/version.py")
    return match.group(1)


def latest_changelog_section():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"(## v[^\n]+\n.*?)(?=\n## v|\Z)", text, re.S)
    return match.group(1).strip() if match else "No changelog section found."


def main():
    version = current_version()
    run(
        "Compile Python files",
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "rf_bridge",
            "rf-bridge.py",
            "scripts/tinysa_diag.py",
            "tinysa_diag.py",
            "scripts/check_version_consistency.py",
        ],
    )
    run("Check version metadata", [sys.executable, "scripts/check_version_consistency.py"])

    artifact_base = f"RF-Bridge-v{version}-macOS-arm64"
    print("\n== Expected release artifacts ==")
    for suffix in ("dmg", "zip"):
        path = ROOT / "dist" / "releases" / f"{artifact_base}.{suffix}"
        status = "found" if path.exists() else "not built yet"
        print(f"{path.relative_to(ROOT)}: {status}")

    print("\n== Latest changelog section ==")
    print(latest_changelog_section())
    print("\nRelease checklist complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
