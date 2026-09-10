"""Select explicit compiler paths or the pinned sibling development toolchain."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def toolchain():
    pins = json.loads((ROOT / "toolchain.json").read_text())
    if pins["schema"] != 1:
        raise RuntimeError("unsupported toolchain manifest schema")
    selected = {}
    for name, variable in (("luce", "LUCE_COMPILER"), ("luce-base", "LUCE_BASE_COMPILER")):
        path = Path(os.environ.get(variable, ROOT.parent / name / "build" / name)).resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f"{path}: build {pins[name]} or set {variable} to an executable")
        version = subprocess.check_output([str(path), "--version"], text=True).strip()
        expected = name + " " + pins[name][len(name) + 1:]
        if variable not in os.environ and version != expected:
            raise RuntimeError(f"{path}: expected {expected}, found {version}; use {variable} for an explicit override")
        print(f"{name}: {path} ({version})", flush=True)
        selected[name] = path
    environment = os.environ.copy()
    environment["LUCE_BASE"] = str(selected["luce-base"])
    return selected["luce"], environment
