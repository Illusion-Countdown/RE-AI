# -*- coding: utf-8 -*-
from memory_run.const import CYAN, GREEN, PURPLE

# ---------------------------------------------------------------- 数据结构（世界内容）
# 这些是运行时层中的数据结构，不再作为玩家自机；自机是 AI 娘。
# hp / speed / regen 保留为旧数据，当前玩法不读取。
BODIES = [
    {"id": "list", "name": "链表", "en": "LINKED LIST", "hp": 90,
     "speed": 312, "regen": 1.6, "color": CYAN,
     "desc": "最快。冲刺距离更远，但血最少。"},
    {"id": "array", "name": "数组", "en": "ARRAY", "hp": 140,
     "speed": 216, "regen": 2.0, "color": GREEN,
     "desc": "最厚。移动慢，工作内存回复也慢。"},
    {"id": "tree", "name": "树／图", "en": "TREE", "hp": 106,
     "speed": 268, "regen": 1.7, "color": PURPLE,
     "desc": "均衡。适合第一次远征。"},
]
BODY_BY_ID = {b["id"]: b for b in BODIES}
