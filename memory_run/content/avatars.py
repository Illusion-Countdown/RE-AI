# -*- coding: utf-8 -*-
from memory_run.const import CYAN, AMBER, GREEN, PURPLE

# ---------------------------------------------------------------- AI 娘
# 玩家操控的是 AI 娘本人；四名角色当前共享基础属性，
# 角色专属技能/特性后续再拆分。
GIRL_BASE_STATS = {"hp": 106, "speed": 268, "regen": 1.7}
DEFAULT_GIRL_ID = "deepseek"

GIRLS = [
    {
        "id": "deepseek", "name": "小忆", "en": "MNEMOSYNE", "color": CYAN,
        "hair": (58, 178, 220), "eye": CYAN,
        "line": "别急着打血条。先看谁指着谁。",
    },
    {
        "id": "claude", "name": "克劳", "en": "ARCHITECT", "color": AMBER,
        "hair": (212, 132, 84), "eye": AMBER,
        "line": "结构比数值更诚实。",
    },
    {
        "id": "gpt", "name": "吉皮", "en": "GENESIS", "color": GREEN,
        "hair": (92, 196, 150), "eye": GREEN,
        "line": "先建立引用，再谈所有权。",
    },
    {
        "id": "glm", "name": "知澜", "en": "LEAK", "color": PURPLE,
        "hair": (160, 122, 230), "eye": PURPLE,
        "line": "内存不会说谎，只会泄漏。",
    },
]

GIRL_BY_ID = {g["id"]: g for g in GIRLS}
