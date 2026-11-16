# -*- coding: utf-8 -*-
from memory_run.const import CYAN, GREEN, PURPLE

# ---------------------------------------------------------------- 身体
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
