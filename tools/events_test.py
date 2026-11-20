# -*- coding: utf-8 -*-
"""事件名注册表检查：格式、重复、值一致性、裸字符串。"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "memory_run"
REGISTRY = PKG / "events.py"

# DOMAIN_ACTION[_STATE...]，2–5 段，总长 <= 48
NAME_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){1,4}$")
MAX_LEN = 48


def assignments(path):
    """产出 (常量名, 字符串值, 行号)。只收集简单 Name = "字符串"。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                yield target.id, value.value, node.lineno


def check_registry():
    errors = []
    entries = []
    seen_names = {}
    seen_values = {}
    for name, value, line in assignments(REGISTRY):
        if name == "__all__":
            continue
        entries.append((name, value, line))
        if not NAME_RE.match(name):
            errors.append(f"{REGISTRY.name}:{line}: 格式错误 {name!r}，应为 DOMAIN_ACTION[_STATE]")
        if len(name) > MAX_LEN:
            errors.append(f"{REGISTRY.name}:{line}: {name!r} 超过 {MAX_LEN} 字符")
        if value != name:
            errors.append(
                f"{REGISTRY.name}:{line}: 常量名 {name!r} 与值 {value!r} 不一致"
            )
        if name.startswith("EVENT_") or name.endswith("_EVENT"):
            errors.append(f"{REGISTRY.name}:{line}: 不要使用多余的 EVENT 前后缀：{name!r}")
        if any(part.isdigit() for part in name.split("_")):
            errors.append(f"{REGISTRY.name}:{line}: 不要用纯数字做版本段：{name!r}")
        if name in seen_names:
            errors.append(
                f"{REGISTRY.name}:{line}: 重复事件 {name!r}（首次在第 {seen_names[name]} 行）"
            )
        else:
            seen_names[name] = line
        if value in seen_values:
            errors.append(
                f"{REGISTRY.name}:{line}: 重复值 {value!r}（首次在第 {seen_values[value]} 行）"
            )
        else:
            seen_values[value] = line
    return entries, seen_values, errors


def check_outside(registry_values):
    errors = []
    for path in sorted(PKG.rglob("*.py")):
        if path == REGISTRY or "__pycache__" in path.parts:
            continue
        for name, value, line in assignments(path):
            if name == "__all__":
                continue
            # 1) 业务模块里直接写已注册的事件字符串
            if value in registry_values:
                errors.append(
                    f"{path.relative_to(ROOT)}:{line}: 裸事件字符串 {value!r}，"
                    "请改用 memory_run.events 常量"
                )
            # 2) 在注册表之外定义“像事件”的常量
            if value == name and NAME_RE.match(name):
                errors.append(
                    f"{path.relative_to(ROOT)}:{line}: 事件常量 {name!r} 只能定义在 "
                    "memory_run/events.py"
                )
    return errors


def self_check():
    """确保正则本身没写坏；这些只是规则样例，不注册。"""
    good = [
        "ENEMY_SPLIT_ON_DEATH",
        "BATTLE_TURN_START",
        "UI_BUTTON_CLICKED",
        "CARD_CAST",
        "GC_NODE_RECYCLED",
    ]
    bad = [
        "enemy_split",
        "ENEMYSPLIT",
        "SPLIT",
        "EVENT_ENEMY_SPLIT",
        "ENEMY_SPLIT_EVENT",
        "ENEMY_SPLIT_2",
        "ENEMY__SPLIT",
        "ENEMY_SPLIT_",
        "_ENEMY_SPLIT",
    ]
    for name in good:
        if not NAME_RE.match(name):
            raise AssertionError(f"good event rejected: {name}")
    for name in bad:
        if NAME_RE.match(name) and not (
            name.startswith("EVENT_") or name.endswith("_EVENT")
            or any(part.isdigit() for part in name.split("_"))
        ):
            raise AssertionError(f"bad event accepted: {name}")


def main():
    self_check()
    if not REGISTRY.exists():
        print(f"EVENTS FAIL: missing {REGISTRY}")
        return 1
    entries, values, errors = check_registry()
    errors.extend(check_outside(values))
    if errors:
        print("EVENTS FAIL")
        for error in errors:
            print("  " + error)
        return 1
    print(f"EVENTS OK ({len(entries)} registered)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
