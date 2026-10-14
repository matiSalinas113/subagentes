"""Run both suites, optionally against the staged tree or pushed commits."""
from __future__ import annotations

import argparse
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def check(root: Path) -> int:
    for project in ("login-app", "proyecto-demo"):
        tests = root / project / "tests"
        if not tests.is_dir() or not list(tests.glob("test_*.py")):
            print(f"ERROR: no hay pruebas en {tests}", file=sys.stderr)
            return 1
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=root / project,
        )
        if result.returncode:
            return result.returncode
    return 0


def check_ref(ref: str) -> int:
    archive = subprocess.run(
        ["git", "archive", "--format=zip", ref], cwd=ROOT,
        check=True, capture_output=True,
    )
    with tempfile.TemporaryDirectory(prefix="subagentes-check-") as directory:
        with zipfile.ZipFile(io.BytesIO(archive.stdout)) as snapshot:
            snapshot.extractall(directory)
        return check(Path(directory))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--pre-push", action="store_true")
    args = parser.parse_args()
    if args.staged:
        tree = subprocess.run(
            ["git", "write-tree"], cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout.strip()
        return check_ref(tree)
    if args.pre_push:
        refs = set()
        for line in sys.stdin:
            _, oid, _, _ = line.split()
            if set(oid) != {"0"}:
                refs.add(oid)
        for oid in sorted(refs):
            result = check_ref(oid)
            if result:
                return result
        return 0
    return check(ROOT)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        print(f"Validacion bloqueada: {error}", file=sys.stderr)
        sys.exit(1)
