# -*- coding: utf-8 -*-
"""核查 assets/pets/lab_manifest.json 及其动作素材（task-8 交付自检）。

用法（项目根 D:\\Pygame\\RE-AI-AutoChess）：
    D:\\Pygame\\.venv\\Scripts\\python.exe assets\\pets\\verify_manifest.py

检查项：
- manifest 可解析，8 个唯一角色（dsh 合并 dsh1，不含独立 dsh1），每角色 4 个动作；
- 每个动作目录/ json / webp 实际存在；
- pygame 能解码 webp，拼贴尺寸 = columns*frame_width × rows*frame_height；
- 可切帧数 = frame_count，且首/中/尾帧 subsurface 可用；
- 输出 "LAB MANIFEST READ TEST OK ..."。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "assets" / "pets" / "lab_manifest.json"
EXPECTED_IDS = ["dsh", "gpt", "claude", "gemini", "qwen", "glm", "grok", "kimi"]


def main() -> int:
    pygame.init()
    pygame.display.set_mode((64, 64))

    if not MANIFEST_PATH.is_file():
        print(f"FAIL manifest 不存在: {MANIFEST_PATH}")
        return 1
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        man = json.load(handle)

    pets = man.get("characters") or man.get("pets")
    if not isinstance(pets, list) or not pets:
        print("FAIL manifest 中没有 characters/pets 列表")
        return 1
    slots = man.get("actionSlots") or ["idle", "move", "skill", "ult"]

    errors: list[str] = []
    ids = [pet.get("id") for pet in pets]
    if sorted(ids) != sorted(EXPECTED_IDS):
        errors.append(f"角色 id 不符: {ids}")
    if "dsh1" in ids:
        errors.append("dsh1 不应作为独立角色出现")

    stats = {"chars": 0, "actions": 0, "files": 0, "sheets": 0, "frames": 0, "slices": 0}
    for pet in pets:
        pid = pet.get("id")
        stats["chars"] += 1
        if pet.get("skill") not in ("attack", "heal", "shield"):
            errors.append(f"{pid}: skill 类型非法 {pet.get('skill')!r}")
        actions = pet.get("actions") or {}
        for slot in slots:
            action = actions.get(slot)
            if not action:
                errors.append(f"{pid}/{slot}: manifest 缺少动作")
                continue
            stats["actions"] += 1
            for key in ("file", "json", "fps", "frame_count", "columns", "rows",
                        "frame_width", "frame_height"):
                if key not in action:
                    errors.append(f"{pid}/{slot}: 缺少字段 {key}")
            webp = PROJECT_ROOT / action["file"]
            jsonf = PROJECT_ROOT / action["json"]
            for path in (webp, jsonf):
                if not path.is_file():
                    errors.append(f"{pid}/{slot}: 文件不存在 {path}")
                else:
                    stats["files"] += 1
            if not webp.is_file():
                continue
            try:
                sheet = pygame.image.load(str(webp))
            except pygame.error as exc:
                errors.append(f"{pid}/{slot}: pygame 解码失败 {exc}")
                continue
            fw, fh = int(action["frame_width"]), int(action["frame_height"])
            cols, rows = int(action["columns"]), int(action["rows"])
            frames = int(action["frame_count"])
            if sheet.get_size() != (fw * cols, fh * rows):
                errors.append(f"{pid}/{slot}: 拼贴尺寸 {sheet.get_size()} != {(fw * cols, fh * rows)}")
            else:
                stats["sheets"] += 1
            cells = (sheet.get_width() // fw) * (sheet.get_height() // fh)
            if cells != frames:
                errors.append(f"{pid}/{slot}: 可切帧数 {cells} != frame_count {frames}")
            else:
                stats["frames"] += 1
            for index in (0, cells // 2, cells - 1):
                col, row = index % cols, index // cols
                sub = sheet.subsurface(pygame.Rect(col * fw, row * fh, fw, fh))
                if sub.get_size() == (fw, fh):
                    stats["slices"] += 1

    print("manifest:", MANIFEST_PATH)
    print("stats:", json.dumps(stats, ensure_ascii=False))
    if errors:
        print(f"FAIL {len(errors)} 项：")
        for item in errors:
            print(" -", item)
        return 1
    print(f"LAB MANIFEST READ TEST OK: {stats['chars']} characters x "
          f"{stats['actions'] // max(1, stats['chars'])} actions, all sheets/frames/slices decoded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
