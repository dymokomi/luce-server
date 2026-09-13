#!/usr/bin/env python3
"""Build a Base consumer against this source package without a package manager.

Each invocation gets a temporary source tree. The compiler sees the same
luce_server namespace that a future installer will place in a consumer package.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def build(entry: Path, output: Path, compiler: Path, opt: int = 0) -> None:
    entry, output, compiler = entry.resolve(), output.resolve(), compiler.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="luce-server-") as temporary:
        project = Path(temporary)
        source = project / "src"
        shutil.copytree(ROOT / "src/luce_server", source / "luce_server",
                        ignore=shutil.ignore_patterns(".DS_Store"))
        shutil.copy2(entry, source / "main.lucb")
        shutil.copy2(ROOT / "luce.toml", project / "luce.toml")
        subprocess.run([str(compiler), "build", str(source / "main.lucb"), "--native",
                        "--opt", str(opt), "-o", str(output)], check=True, cwd=ROOT)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entry", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--base", type=Path, default=Path(os.environ.get(
        "LUCE_BASE_COMPILER", ROOT.parent / ("luce-base/build/luce-base.exe" if os.name == "nt" else "luce-base/build/luce-base"))))
    parser.add_argument("--opt", type=int, choices=range(4), default=0)
    arguments = parser.parse_args()
    build(arguments.entry, arguments.output, arguments.base, arguments.opt)
