#!/usr/bin/env python3
"""Run the package's unit and independent network checks at every native level."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build import build


def checked(command, timeout=120):
    subprocess.run(list(map(str, command)), cwd=ROOT, check=True, timeout=timeout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path(os.environ.get(
        "LUCE_BASE_COMPILER", ROOT.parent / ("luce-base/build/luce-base.exe" if os.name == "nt" else "luce-base/build/luce-base"))))
    parser.add_argument("--opt", type=int, choices=range(4), action="append")
    arguments = parser.parse_args()
    if os.name != "nt":
        checked([sys.executable, ROOT / "tests/process_ownership.py"])
    for level in arguments.opt if arguments.opt is not None else range(4):
        unit = ROOT / "build" / f"unit-{level}"
        server = ROOT / "build" / f"server-{level}"
        lifecycle = ROOT / "build" / f"lifecycle-{level}"
        build(ROOT / "tests/unit.lucb", unit, arguments.base, level)
        checked([unit])
        build(ROOT / "tests/lifecycle.lucb", lifecycle, arguments.base, level)
        checked([lifecycle])
        build(ROOT / "tests/server.lucb", server, arguments.base, level)
        checked([sys.executable, ROOT / "tests/integration.py", server])
        print(f"PASS native opt {level}", flush=True)
