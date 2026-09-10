#!/usr/bin/env python3
"""Run protocol and application tests on the native execution path."""
import argparse
import subprocess

from compiler import ROOT, toolchain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opt", type=int, choices=range(4), action="append",
                        help="test selected native optimization levels; default: all four")
    arguments = parser.parse_args()
    compiler, environment = toolchain()
    build = ROOT / "build/tests"
    build.mkdir(parents=True, exist_ok=True)
    for level in arguments.opt if arguments.opt is not None else range(4):
        binary = build / f"unit-opt-{level}"
        subprocess.run([str(compiler), "build", str(ROOT / "src/tests/unit.luc"),
                        "--native", "--opt", str(level), "-o", str(binary)], env=environment, check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120)
        print(result.stdout, end="", flush=True)
        if result.returncode != 0 or result.stderr:
            raise RuntimeError(f"native opt {level}: exit {result.returncode}\n{result.stderr}")
        print(f"PASS native opt {level}", flush=True)


if __name__ == "__main__":
    main()
