#!/usr/bin/env python3
"""Build a server application with Luce's native backend."""
import argparse
from pathlib import Path
import subprocess

from compiler import ROOT, toolchain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build/luce-server")
    parser.add_argument("--opt", type=int, choices=range(4), default=2)
    arguments = parser.parse_args()
    compiler, environment = toolchain()
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(compiler), "build", str(arguments.source.resolve()), "--native",
                    "--opt", str(arguments.opt), "-o", str(output)], env=environment, check=True)
    print(output)


if __name__ == "__main__":
    main()
