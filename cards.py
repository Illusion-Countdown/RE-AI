# -*- coding: utf-8 -*-
"""Card data for the memory-assembly demo."""

CATEGORIES = {
    "CUT": {"cn": "断链", "en": "CUT", "color": (80, 214, 255), "dim": (28, 82, 105)},
    "REF": {"cn": "引用", "en": "REF", "color": (185, 140, 255), "dim": (66, 46, 95)},
    "TYPE": {"cn": "类型", "en": "TYPE", "color": (255, 200, 87), "dim": (96, 72, 32)},
    "MEM": {"cn": "内存", "en": "MEM", "color": (114, 230, 160), "dim": (38, 86, 60)},
}

RARITY = ["基础", "进阶", "稀有"]
RARITY_COLORS = [(150, 185, 200), (95, 205, 255), (255, 200, 87)]

# cells are (row, col), canonical top-left orientation
CARDS = [
    {
        "key": "CUT", "cn": "断链剪", "en": "CUT", "cat": "CUT", "rarity": 0,
        "cells": [(0, 0), (1, 0), (1, 1)], "mb": 4, "work": 1, "target": "敌人",
        "effect": "选择一个敌人，剪断 1 条 STRONG 引用；引用归零触发 GC。",
        "up": "一次剪断 2 条引用。",
    },
    {
        "key": "CLIP", "cn": "尽剪", "en": "CLIP", "cat": "CUT", "rarity": 1,
        "cells": [(0, 0), (0, 1), (0, 2), (1, 1)], "mb": 5, "work": 0, "target": "敌人",
        "effect": "滑剪命中多个敌人时，只清空第一个命中敌人的全部引用（含 SUPPORT），不再同时清空所有被划过的敌人。",
        "up": "清空引用后额外造成 150 伤害。",
    },
    {
        "key": "SWEEP", "cn": "扫链", "en": "SWEEP", "cat": "CUT", "rarity": 1,
        "cells": [(0, 0), (0, 1), (0, 2)], "mb": 3, "work": 0, "target": "全体敌人",
        "effect": "对所有敌人各剪断 1 条 STRONG 引用。",
        "up": "全体各剪断 2 条引用。",
    },
    {
        "key": "DELAY", "cn": "延时断点", "en": "DELAY", "cat": "CUT", "rarity": 1,
        "cells": [(0, 1), (0, 2), (1, 0), (1, 1)], "mb": 4, "work": 0, "target": "敌人",
        "effect": "选择一名敌人，3 秒后剪断其 1 条 STRONG 引用。",
        "up": "延迟缩短为 2 秒，并剪断 2 条引用。",
    },
    {
        "key": "REFLECT", "cn": "折返断链", "en": "REFLECT", "cat": "CUT", "rarity": 2,
        "cells": [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)], "mb": 8, "work": 0, "target": "敌人",
        "effect": "标记一名敌人 6 秒；其攻击时反伤自身。",
        "up": "反伤持续时间延长至 9 秒。",
    },
    {
        "key": "LINK", "cn": "锚链", "en": "LINK", "cat": "REF", "rarity": 0,
        "cells": [(0, 0), (1, 0)], "mb": 2, "work": 0, "target": "敌人",
        "effect": "锚定一名敌人 4 秒，使其停止行动。",
        "up": "锚定时长延长至 6 秒。",
    },
    {
        "key": "WEAK", "cn": "窥弱印", "en": "WEAK", "cat": "REF", "rarity": 0,
        "cells": [(0, 0)], "mb": 1, "work": 0, "target": "敌人",
        "effect": "标记一名敌人 6 秒，其受到伤害 +35%。",
        "up": "弱化持续时间延长至 9 秒。",
    },
    {
        "key": "WEAKEN", "cn": "降级刻", "en": "WEAKEN", "cat": "REF", "rarity": 1,
        "cells": [(0, 1), (1, 0), (1, 1)], "mb": 3, "work": 0, "target": "敌人",
        "effect": "剪断目标 1 条 STRONG 引用，并施加 6 秒弱化。",
        "up": "剪断 2 条引用，弱化延长至 9 秒。",
    },
    {
        "key": "ALIAS", "cn": "别名绑定", "en": "ALIAS", "cat": "REF", "rarity": 1,
        "cells": [(0, 0), (0, 1), (1, 0), (1, 1)], "mb": 6, "work": 2, "target": "敌人",
        "effect": "标记一名敌人 6 秒；其受伤时向另一名敌人扩散 35% 伤害。",
        "up": "扩散比例提升至 50%。",
    },
    {
        "key": "STEAL", "cn": "引用窃取", "en": "STEAL", "cat": "REF", "rarity": 2,
        "cells": [(0, 0), (0, 1), (1, 1), (1, 2)], "mb": 5, "work": 1, "target": "敌人",
        "effect": "剪断目标 1 条 STRONG 引用，并恢复 10 保真度。",
        "up": "同时恢复 20 保真度。",
    },
    {
        "key": "VOID", "cn": "空型抹除", "en": "VOID", "cat": "TYPE", "rarity": 1,
        "cells": [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)], "mb": 7, "work": 2, "target": "敌人",
        "effect": "眩晕目标 2 秒，并剥掉其析构器。",
        "up": "眩晕延长至 3 秒。",
    },
    {
        "key": "TRUNC", "cn": "截断", "en": "TRUNC", "cat": "TYPE", "rarity": 1,
        "cells": [(0, 0), (0, 2), (1, 0), (1, 1), (1, 2)], "mb": 7, "work": 2, "target": "敌人",
        "effect": "对目标造成 80 伤害，并眩晕 1 秒。",
        "up": "伤害提升至 120，眩晕 2 秒。",
    },
    {
        "key": "COMPRESS", "cn": "压缩", "en": "COMPRESS", "cat": "MEM", "rarity": 2,
        "cells": [(0, 0), (0, 1), (0, 2), (1, 0), (2, 0), (2, 1), (2, 2)],
        "mb": 10, "work": 0, "target": "自身",
        "effect": "8 秒内我方伤害 +30%，保真度 -10。",
        "up": "持续 12 秒，伤害 +40%。",
    },
    {
        "key": "ECC", "cn": "纠错补块", "en": "ECC", "cat": "MEM", "rarity": 2,
        "cells": [(0, 0), (0, 2), (1, 0), (1, 1), (1, 2), (2, 0), (2, 2)],
        "mb": 8, "work": 0, "target": "自身",
        "effect": "恢复 30 点保真度。",
        "up": "恢复 50 点保真度。",
    },
    {
        "key": "LOSSY", "cn": "有损爆发", "en": "LOSSY", "cat": "MEM", "rarity": 2,
        "cells": [(r, c) for r in range(3) for c in range(3) if not (r == 1 and c == 1)],
        "mb": 14, "work": 3, "target": "全体敌人",
        "effect": "对所有敌人造成 70 伤害，保真度 -10。",
        "up": "伤害提升至 110。",
    },
    {
        "key": "DOWN", "cn": "降采样", "en": "DOWN", "cat": "MEM", "rarity": 1,
        "cells": [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)], "mb": 7, "work": 2, "target": "敌人",
        "effect": "使目标减速 5 秒。",
        "up": "减速延长至 8 秒。",
    },
    {
        "key": "PATCH", "cn": "热补丁", "en": "PATCH", "cat": "MEM", "rarity": 0,
        "cells": [(0, 0), (0, 1)], "mb": 3, "work": 0, "target": "自身",
        "effect": "回复生命比例最低角色 18% 最大生命。",
        "up": "回复量提升至 24%。",
    },
    {
        "key": "STITCH", "cn": "缝合", "en": "STITCH", "cat": "MEM", "rarity": 1,
        "cells": [(0, 0), (0, 1), (1, 0)], "mb": 4, "work": 0, "target": "自身",
        "effect": "回复生命最低角色 12% 最大生命，并给予 2 秒减伤。",
        "up": "回复量提升至 18%。",
    },
    {
        "key": "EDGE", "cn": "锐化", "en": "EDGE", "cat": "CUT", "rarity": 1,
        "kind": "passive", "cells": [(0, 0), (0, 1), (1, 0)], "mb": 3, "work": 0, "target": "被动",
        "effect": "滑剪命中判定宽度 +8，更容易一次划过多条引用。",
        "up": "判定宽度额外 +4。",
    },
    {
        "key": "RECLAIM", "cn": "回收协议", "en": "RECLAIM", "cat": "MEM", "rarity": 1,
        "kind": "passive", "cells": [(0, 0), (0, 1), (1, 0), (1, 1)], "mb": 4, "work": 0, "target": "被动",
        "effect": "每次触发 GC 时恢复 6 点保真度。",
        "up": "每次 GC 恢复 10 点保真度。",
    },
    {
        "key": "OVERCLOCK", "cn": "超频", "en": "OVERCLOCK", "cat": "TYPE", "rarity": 2,
        "kind": "passive", "cells": [(0, 0), (0, 1), (0, 2), (1, 1)], "mb": 5, "work": 0, "target": "被动",
        "effect": "我方造成的伤害 +12%。",
        "up": "我方造成的伤害 +18%。",
    },
]

BY_KEY = {c["key"]: c for c in CARDS}


def normalize(cells):
    if not cells:
        return []
    min_r = min(r for r, c in cells)
    min_c = min(c for r, c in cells)
    return sorted((r - min_r, c - min_c) for r, c in cells)


def rotate(cells, rot):
    cells = normalize(cells)
    for _ in range(rot % 4):
        cells = normalize([(c, -r) for r, c in cells])
    return cells


def bbox(cells):
    return (max(r for r, c in cells) + 1, max(c for r, c in cells) + 1)
