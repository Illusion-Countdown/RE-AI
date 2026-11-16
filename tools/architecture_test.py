# -*- coding: utf-8 -*-
"""分层依赖检查：core/content/run/battle 不得反向依赖 UI。

只检查 memory_run 包内的 import；根目录兼容 shim 不参与。
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "memory_run"

# 每层允许依赖的 memory_run 前缀；自己这一层总是允许
ALLOWED = {
    "core": ("memory_run.const", "memory_run.core", "memory_run.content.card_defs"),
    "content": ("memory_run.const", "memory_run.content"),
    "run": ("memory_run.const", "memory_run.core", "memory_run.content", "memory_run.run"),
    "battle": ("memory_run.const", "memory_run.core", "memory_run.content",
               "memory_run.run", "memory_run.platform", "memory_run.battle"),
    "platform": ("memory_run.const", "memory_run.platform"),
    "ui": ("memory_run",),
}


def module_paths():
    for layer in ALLOWED:
        for p in (ROOT / layer).rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            yield layer, p


def imported_names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith("memory_run"):
                yield mod
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("memory_run"):
                    yield alias.name


def main():
    bad = []
    for layer, path in module_paths():
        allowed = ALLOWED[layer]
        for mod in imported_names(path):
            if any(mod == a or mod.startswith(a + ".") for a in allowed):
                continue
            bad.append((path.relative_to(ROOT), mod))
    if bad:
        print("ARCHITECTURE VIOLATIONS")
        for path, mod in bad:
            print(f"  {path}: {mod}")
        return 1
    print("ARCHITECTURE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
