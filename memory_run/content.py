# -*- coding: utf-8 -*-
"""内容表：AI 娘、模块、Boss 规则、教程与 5 区 18 战。"""
from .const import (
    CYAN, MAGENTA, PURPLE, AMBER, GREEN, RED, GOLD, TEAL, BLUE, WHITE, DIM,
)

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

# ---------------------------------------------------------------- AI 娘
GIRLS = [
    {
        "id": "deepseek", "name": "小忆", "en": "DEEPSEEK", "color": CYAN,
        "hair": (58, 178, 220), "eye": CYAN,
        "line": "别急着打血条。先看谁指着谁。",
    },
    {
        "id": "claude", "name": "克劳", "en": "CLAUDE", "color": AMBER,
        "hair": (212, 132, 84), "eye": AMBER,
        "line": "结构比数值更诚实。",
    },
    {
        "id": "gpt", "name": "吉皮", "en": "GPT", "color": GREEN,
        "hair": (92, 196, 150), "eye": GREEN,
        "line": "先建立引用，再谈所有权。",
    },
    {
        "id": "glm", "name": "知澜", "en": "GLM", "color": PURPLE,
        "hair": (160, 122, 230), "eye": PURPLE,
        "line": "内存不会说谎，只会泄漏。",
    },
]

# ---------------------------------------------------------------- 模块
MODULES = [
    {"id": "exception", "name": "异常捕获", "en": "TRY/CATCH", "color": GREEN,
     "desc": "每房间第一次析构伤害为 0。", "tag": "防御"},
    {"id": "inline", "name": "内联", "en": "INLINE", "color": AMBER,
     "desc": "WRITE 伤害 +50%，且不再制造泄漏。", "tag": "输出"},
    {"id": "weak_net", "name": "弱引用网", "en": "WEAK.NET", "color": PURPLE,
     "desc": "WEAK 不占工作内存；弱引用目标永久可见。", "tag": "弱引用"},
    {"id": "steal", "name": "引用窃取", "en": "STEAL", "color": TEAL,
     "desc": "CUT 剪断敌方边时，30% 概率把边收归自己。", "tag": "拓扑"},
    {"id": "cascade_bonus", "name": "级联红利", "en": "CASCADE+", "color": GOLD,
     "desc": "级联每层伤害加成从 1% 提升到 2%。", "tag": "级联"},
    {"id": "compressor", "name": "压缩器", "en": "COMPRESSOR", "color": RED,
     "desc": "压缩持续时间 +4 秒。", "tag": "画质"},
    {"id": "lossless", "name": "无损审计", "en": "LOSSLESS", "color": CYAN,
     "desc": "画质 ≥75% 时，WRITE +20% 伤害。", "tag": "画质"},
    {"id": "redundancy", "name": "冗余校验", "en": "ECC.REDUNDANT", "color": GREEN,
     "desc": "每房间第一次跌破 25% 画质时，回到 50%（一次）。", "tag": "画质"},
    {"id": "wreck", "name": "残骸协议", "en": "WRECK", "color": DIM,
     "desc": "每有 1 个坏死格，WRITE +3% 伤害（上限 +30%）。", "tag": "坏死"},
    {"id": "necro_bomb", "name": "坏死引爆", "en": "NECRO.BOMB", "color": MAGENTA,
     "desc": "每房间一次（R）：消耗 1 个坏死格，造成 60 范围伤害并回 2 工作内存。", "tag": "坏死"},
    {"id": "overload", "name": "过载", "en": "OVERLOAD", "color": RED,
     "desc": "画质 <50% 时，所有伤害 +15%。", "tag": "画质"},
    {"id": "dead_code", "name": "死代码消除", "en": "DEAD.CODE", "color": CYAN,
     "desc": "每房间一次（T）：全场敌人停火 3 秒。", "tag": "控场"},
    {"id": "cow", "name": "写时复制", "en": "COW", "color": BLUE,
     "desc": "ALIAS 组第一次受伤不共享。", "tag": "别名"},
    {"id": "tail_rec", "name": "尾递归", "en": "TAIL.REC", "color": TEAL,
     "desc": "GC 级联超过 3 个对象后停止继续级联。", "tag": "GC"},
]

MODULE_BY_ID = {m["id"]: m for m in MODULES}

# ---------------------------------------------------------------- Boss 规则
BOSS_RULES = [
    {"id": "reg", "name": "抽牌加速", "desc": "自动抽牌间隔 -0.5s；不再依赖寄存器。"},
    {"id": "grid", "name": "网格扩容", "desc": "网格额外 +1 行（+1 列）。"},
    {"id": "free_gc", "name": "免费 GC", "desc": "每房间一次免费立即 GC（G）。"},
    {"id": "discount", "name": "升级折扣", "desc": "卡牌升级费用 -1 碎片（最低 1）。"},
    {"id": "window", "name": "级联窗口 +1s", "desc": "级联窗口从 2 秒变为 3 秒。"},
    {"id": "perfect", "name": "完美翻倍", "desc": "完美清房奖励翻倍。"},
]

# ---------------------------------------------------------------- 房间节点
def N(id, kind, p, name=None, hp=None, **kw):
    d = {"id": id, "kind": kind, "p": p, "name": name, "hp": hp}
    d.update(kw)
    return d


def E(a, b, kind="STRONG"):
    return (a, b, kind)


def _room(code, title, cn, zone, nodes, edges, danger=1, **kw):
    d = {"code": code, "title": title, "cn": cn, "zone": zone,
         "danger": danger, "nodes": nodes, "edges": edges}
    d.update(kw)
    return d


ROOMS = [
    # ------------------------------------------------------------ 教程
    _room("T1", "FIRST CUT", "第一次剪断", 0, [
        N("scope", "ROOT", (0.50, 0.10), "SCOPE"),
        N("s", "SENTINEL", (0.50, 0.42), "SENTINEL.01", 54),
        N("m1", "MINION", (0.30, 0.70), "MINION.02", 20),
        N("m2", "MINION", (0.70, 0.70), "MINION.03", 20),
    ], [E("scope", "s"), E("s", "m1"), E("s", "m2")],
        tutorial=True, tut="cut",
        intro="我是小忆。你看到的不是血条，是一张引用图。",
        hint="按 1 选「单剪」，从 SCOPE 划向 SENTINEL 的线。引用归零，它会连同子节点一起被 GC 擦除。",
        tips=["CUT 划边", "GC 级联"]),

    _room("T2", "BREAK THE CYCLE", "破环", 0, [
        N("scope", "ROOT", (0.50, 0.10), "SCOPE"),
        N("a", "CYCLER", (0.34, 0.48), "CYCLER.A", 48, partner="b"),
        N("b", "CYCLER", (0.66, 0.48), "CYCLER.B", 48, partner="a"),
    ], [E("scope", "a"), E("scope", "b"), E("a", "b"), E("b", "a")],
        tutorial=True, tut="weak",
        intro="强引用环里，两个对象的 refcount 永远不会归零。",
        hint="按 1 选「弱观测」，从 A 拖到 B。然后先剪 B 的根引用（B 会归零并带走 B→A），再剪 A 的根引用。",
        tips=["WEAK 破环", "refcount"]),

    _room("T3", "OWNERSHIP", "所有权", 0, [
        N("scope", "ROOT", (0.50, 0.10), "SCOPE"),
        N("brute", "MINION", (0.50, 0.40), "BRUTE.04", 150),
        N("m1", "MINION", (0.30, 0.72), "MINION.05", 24),
        N("m2", "MINION", (0.70, 0.72), "MINION.06", 24),
    ], [E("scope", "brute"), E("brute", "m1"), E("brute", "m2")],
        tutorial=True, tut="link",
        intro="你可以把敌人链接到自己身上：它停火，但你受伤时它分摊 40%。",
        hint="按 1 选「硬链」，从自己拖到 BRUTE；再剪 SCOPE→BRUTE 的根引用；最后剪断你自己→BRUTE 的边，让它的 refcount 归零。",
        tips=["LINK 争夺", "承伤"]),

    _room("T4", "DESTRUCTOR", "析构器", 0, [
        N("scope", "ROOT", (0.50, 0.10), "SCOPE"),
        N("elite", "SENTINEL", (0.50, 0.40), "DESTRUCTOR.07", 120,
          destructor=True),
        N("m1", "MINION", (0.30, 0.72), "MINION.08", 26),
        N("m2", "MINION", (0.70, 0.72), "MINION.09", 26),
    ], [E("scope", "elite"), E("elite", "m1"), E("elite", "m2")],
        tutorial=True, tut="cast",
        intro="红色虚线环代表析构器：死亡时会爆炸。",
        hint="按 1 选「截断」，点掉析构器，再剪。没有 CAST 牌时，用 WRITE 远程磨血。",
        tips=["CAST 剥析构", "先剥再剪"]),

    # ------------------------------------------------------------ 第一区
    _room("R01", "HELLO, WORLD", "你好，世界", 1, [
        N("scope", "ROOT", (0.50, 0.08), "SCOPE"),
        N("hub", "SENTINEL", (0.50, 0.33), "SENTINEL.10", 70, owned=1),
        N("m1", "MINION", (0.28, 0.58), "MINION.11", 24),
        N("m2", "MINION", (0.50, 0.68), "MINION.12", 24),
        N("m3", "MINION", (0.72, 0.58), "MINION.13", 24),
    ], [E("scope", "hub"), E("hub", "m1"), E("hub", "m2"),
        E("hub", "m3")],
        danger=1, hint="找枢纽：三个子节点都挂在它身上。"),
    _room("R02", "THE CYCLE", "环", 2, [
        N("scope", "ROOT", (0.50, 0.08), "SCOPE"),
        N("a", "CYCLER", (0.34, 0.40), "CYCLER.A", 64, partner="b"),
        N("b", "CYCLER", (0.66, 0.40), "CYCLER.B", 64, partner="a"),
        N("m1", "MINION", (0.24, 0.74), "MINION.14", 24),
        N("m2", "MINION", (0.76, 0.74), "MINION.15", 24),
    ], [E("scope", "a"), E("scope", "b"), E("a", "b"), E("b", "a"),
        E("a", "m1"), E("b", "m2")],
        danger=2, hint="先破环，否则剪掉一条，另一条会重建。"),
    _room("R03", "ALLOCATOR", "分配器", 3, [
        N("scope", "ROOT", (0.50, 0.08), "SCOPE"),
        N("al", "ALLOCATOR", (0.50, 0.32), "ALLOCATOR.16", 90, owned=1),
        N("m1", "MINION", (0.26, 0.62), "MINION.17", 24),
        N("m2", "MINION", (0.74, 0.62), "MINION.18", 24),
        N("ward", "WARD", (0.50, 0.52), "WARD.19", 50),
    ], [E("scope", "al"), E("al", "m1"), E("al", "m2"),
        E("al", "ward")],
        danger=2, hint="它每 4 秒申请一个新子对象。先剪入边。"),
    _room("B1", "GC CORE", "垃圾回收者", 4, [
        N("scope", "ROOT", (0.50, 0.05), "SCOPE"),
        N("core", "GC_CORE", (0.50, 0.30), "GC.CORE", 600,
          boss="gc", pylon=True),
        N("p1", "PYLON", (0.20, 0.74), "PYLON.01", 100),
        N("p2", "PYLON", (0.50, 0.82), "PYLON.02", 100),
        N("p3", "PYLON", (0.80, 0.74), "PYLON.03", 100),
    ], [E("scope", "p1"), E("scope", "p2"), E("scope", "p3"),
        E("p1", "core"), E("p2", "core"), E("p3", "core")],
        danger=3, boss=True,
        intro="三条根引用托着核心。先拆塔架，再谈核心。",
        hint="核心在塔架全死前免疫。剪断 PYLON 的根引用，或直接打掉它们。"),

    # ------------------------------------------------------------ 第二区
    _room("R04", "DEADLOCK", "死锁", 5, [
        N("scope", "ROOT", (0.50, 0.07), "SCOPE"),
        N("a", "WARD", (0.32, 0.36), "LOCK.A", 120, owned=2, barrier=True),
        N("b", "WARD", (0.68, 0.36), "LOCK.B", 120, owned=2, barrier=True),
        N("m1", "MINION", (0.28, 0.70), "MINION.20", 36),
        N("m2", "MINION", (0.72, 0.70), "MINION.21", 36),
    ], [E("scope", "a"), E("scope", "a"), E("scope", "b"),
        E("scope", "b"), E("a", "b"), E("b", "a"),
        E("a", "m1"), E("b", "m2")],
        danger=3, hint="两把锁互相引用。屏障会免疫第一次剪断。"),
    _room("R05", "LIVELOCK", "活锁", 6, [
        N("scope", "ROOT", (0.50, 0.07), "SCOPE"),
        N("g1", "GLITCH", (0.34, 0.38), "GHOST.22", 90, cut_immune=True),
        N("g2", "GLITCH", (0.66, 0.38), "GHOST.23", 90, cut_immune=True),
        N("scope2", "ROOT", (0.10, 0.18), "ROOT.02"),
        N("m1", "MINION", (0.50, 0.72), "MINION.24", 40),
    ], [E("scope", "g1"), E("scope", "g2"), E("scope2", "m1"),
        E("g1", "m1", "WEAK")],
        danger=3, hint="它不在你的拓扑里：先 CAST 赋予类型，CUT 才生效。"),
    _room("R06", "RACE CONDITION", "竞态", 7, [
        N("scope", "ROOT", (0.50, 0.07), "SCOPE"),
        N("q", "QUANTIZER", (0.50, 0.30), "QUANTIZER.25", 100),
        N("g", "GLITCH", (0.22, 0.62), "GLITCH.26", 70),
        N("t", "TEAR", (0.78, 0.62), "TEAR.27", 70),
        N("m1", "MINION", (0.36, 0.78), "MINION.28", 36),
        N("m2", "MINION", (0.64, 0.78), "MINION.29", 36),
    ], [E("scope", "q"), E("scope", "g"), E("scope", "t"),
        E("q", "m1"), E("q", "m2")],
        danger=4, hint="量化者会持续压画质。先杀它，或接受模糊的代价。"),
    _room("B2", "AUDITOR", "审计员", 8, [
        N("scope", "ROOT", (0.50, 0.05), "SCOPE"),
        N("core", "AUDITOR", (0.50, 0.30), "AUDITOR", 800,
          boss="auditor"),
        N("m1", "MINION", (0.24, 0.68), "MINION.30", 50),
        N("m2", "MINION", (0.76, 0.68), "MINION.31", 50),
        N("p1", "PYLON", (0.18, 0.46), "AUDIT.01", 120),
        N("p2", "PYLON", (0.82, 0.46), "AUDIT.02", 120),
    ], [E("scope", "core"), E("scope", "p1"), E("scope", "p2"),
        E("p1", "core"), E("p2", "core"), E("core", "m1"),
        E("core", "m2")],
        danger=4, boss=True,
        intro="它的护盾由你损失画质构成。把画质修回来，才能破盾。",
        hint="护盾 = 损失画质 ×2；画质 ≥75% 时护盾失效。用 ECC 修坏死格。"),

    # ------------------------------------------------------------ 第三区
    _room("R07", "UNION", "联合体", 9, [
        N("scope", "ROOT", (0.50, 0.07), "SCOPE"),
        N("brute", "MINION", (0.50, 0.34), "UNION.BRUTE", 300,
          destructor=True, owned=1),
        N("bomb", "BOMB", (0.28, 0.64), "BOMB.32", 40),
        N("m1", "MINION", (0.72, 0.64), "MINION.33", 50),
        N("ward", "WARD", (0.50, 0.72), "WARD.34", 90),
    ], [E("scope", "brute"), E("scope", "bomb"), E("scope", "m1"),
        E("scope", "ward"), E("bomb", "brute", "WEAK")],
        danger=5, hint="炸弹和硬壳共享血条时，一次引爆等于击杀。"),
    _room("R08", "TYPE ERASER", "类型擦除者", 10, [
        N("scope", "ROOT", (0.50, 0.07), "SCOPE"),
        N("er", "ERASER", (0.50, 0.32), "ERASER.35", 260, cut_immune=True),
        N("m1", "MINION", (0.30, 0.66), "MINION.36", 55),
        N("m2", "MINION", (0.70, 0.66), "MINION.37", 55),
        N("p", "PYLON", (0.50, 0.78), "ERASE.PYLON", 100),
    ], [E("scope", "er"), E("scope", "m1"), E("scope", "m2"),
        E("scope", "p"), E("er", "m1"), E("er", "m2"), E("p", "er")],
        danger=5, hint="它拒绝被 CUT。先用 CAST 剥掉类型免疫，再剪或打。"),
    _room("R09", "OFF BY ONE", "差一格", 11, [
        N("scope", "ROOT", (0.50, 0.07), "SCOPE"),
        N("c1", "CRAWLER", (0.20, 0.30), "CRAWLER.38", 120, necro=True),
        N("c2", "CRAWLER", (0.80, 0.30), "CRAWLER.39", 120, necro=True),
        N("q", "QUANTIZER", (0.50, 0.50), "QUANTIZER.40", 120),
        N("m1", "MINION", (0.34, 0.76), "MINION.41", 50),
        N("m2", "MINION", (0.66, 0.76), "MINION.42", 50),
    ], [E("scope", "c1"), E("scope", "c2"), E("scope", "q"),
        E("q", "m1"), E("q", "m2"), E("c1", "c2", "WEAK")],
        danger=6, hint="越界爬虫命中会烧坏一格。用 ECC 修回来。"),
    _room("B3", "KERNEL", "内核", 12, [
        N("scope", "ROOT", (0.50, 0.05), "SCOPE"),
        N("ka", "KERNEL", (0.34, 0.34), "KERNEL.L", 500, boss="kernel"),
        N("kb", "KERNEL", (0.66, 0.34), "KERNEL.R", 500, boss="kernel"),
        N("m1", "MINION", (0.24, 0.72), "MINION.43", 60),
        N("m2", "MINION", (0.76, 0.72), "MINION.44", 60),
    ], [E("scope", "ka"), E("scope", "kb"), E("ka", "kb"),
        E("kb", "ka"), E("ka", "m1"), E("kb", "m2")],
        danger=6, boss=True,
        intro="两个内核互为强引用。只要环还在，它们就不会归零。",
        hint="用 WEAK 破环。两个内核都归零，或都被打掉，才算通关。"),

    # ------------------------------------------------------------ 第四区
    _room("R10", "FRAGMENT TIDE", "碎片潮", 4, [
        N("scope", "ROOT", (0.50, 0.06), "SCOPE"),
        N("ward", "WARD", (0.30, 0.34), "WARD.50", 120, barrier=True),
        N("eye", "SENTINEL", (0.56, 0.32), "SENTINEL.51", 150, owned=1),
        N("m1", "MINION", (0.24, 0.66), "MINION.52", 55),
        N("m2", "MINION", (0.44, 0.70), "MINION.53", 55),
        N("m3", "CRAWLER", (0.74, 0.64), "CRAWLER.54", 90, necro=True),
    ], [E("scope", "ward"), E("scope", "eye"),
        E("ward", "m1"), E("eye", "m2"), E("eye", "m3")],
        danger=8,
        intro="这不是散兵。WARD 护着炮塔，炮塔带着三只小怪。",
        hint="先 CUT 掉 WARD→小怪的支援边，再处理炮塔；别先杀小怪。"),

    _room("R11", "CACHE LINE", "缓存行", 4, [
        N("scope", "ROOT", (0.50, 0.06), "SCOPE"),
        N("a", "CYCLER", (0.34, 0.34), "CACHE.A", 90, partner="b"),
        N("b", "CYCLER", (0.66, 0.34), "CACHE.B", 90, partner="a"),
        N("guard", "WARD", (0.50, 0.58), "GUARD.55", 140, barrier=True),
        N("p", "PYLON", (0.18, 0.70), "PYLON.56", 110),
    ], [E("scope", "a"), E("scope", "b"), E("scope", "p"),
        E("a", "b", "WEAK"), E("a", "guard"), E("b", "guard")],
        danger=9,
        intro="两个循环体互相搭链，中间的 WARD 在替它们吃伤害。",
        hint="WEAK 破环后，CUT WARD 的支援边；不要被双环拖住。"),

    _room("B4", "FRAGMENT CORE", "碎片核心", 4, [
        N("scope", "ROOT", (0.50, 0.05), "SCOPE"),
        N("core", "GC_CORE", (0.50, 0.28), "FRAGMENT.CORE", 900,
          boss="gc", pylon=True),
        N("p1", "PYLON", (0.18, 0.70), "SHARD.01", 180),
        N("p2", "PYLON", (0.50, 0.80), "SHARD.02", 180),
        N("p3", "PYLON", (0.82, 0.70), "SHARD.03", 180),
        N("ward", "WARD", (0.74, 0.48), "SHARD.GUARD", 160, barrier=True),
    ], [E("scope", "p1"), E("scope", "p2"), E("scope", "p3"),
        E("p1", "core"), E("p2", "core"), E("p3", "core"),
        E("ward", "core")],
        danger=9, boss=True,
        intro="核心把碎片焊成了新的塔架。WARD 会替它挡下第一刀。",
        hint="先 CUT WARD 的支援，再拆三根塔架；核心在三塔全死前免疫。"),

    # ------------------------------------------------------------ 第五区
    _room("R12", "DEAD STORE", "死存储", 5, [
        N("scope", "ROOT", (0.50, 0.06), "SCOPE"),
        N("er", "ERASER", (0.34, 0.34), "ERASER.60", 320, cut_immune=True),
        N("q", "QUANTIZER", (0.68, 0.34), "QUANTIZER.61", 150),
        N("ward", "WARD", (0.50, 0.60), "WARD.62", 160, barrier=True),
        N("m1", "MINION", (0.20, 0.74), "MINION.63", 70),
        N("m2", "MINION", (0.82, 0.74), "MINION.64", 70),
    ], [E("scope", "er"), E("scope", "q"), E("scope", "ward"),
        E("er", "m1"), E("q", "m2"), E("ward", "er")],
        danger=10,
        intro="擦除者让 CUT 失效；量化者持续吃你的画质；WARD 替它们挡刀。",
        hint="先 CAST 擦除者，再 CUT；不要同时把 WEAK 和 CUT 都交给同一个目标。"),

    _room("R13", "OOM EDGE", "OOM 边缘", 5, [
        N("scope", "ROOT", (0.50, 0.06), "SCOPE"),
        N("ka", "KERNEL", (0.32, 0.30), "KERNEL.SHARD.L", 180),
        N("kb", "KERNEL", (0.68, 0.30), "KERNEL.SHARD.R", 180),
        N("c", "CYCLER", (0.50, 0.56), "OOM.CYCLE", 120, partner="d"),
        N("d", "CYCLER", (0.50, 0.76), "OOM.CYCLE.B", 120, partner="c"),
    ], [E("scope", "ka"), E("scope", "kb"), E("ka", "kb"),
        E("ka", "c"), E("kb", "d"), E("c", "d", "WEAK")],
        danger=11,
        intro="两个内核碎片共享一条环，越晚破环，弹幕越密。",
        hint="WEAK 破环后集中 CUT 根边；先杀带输出的 KERNEL.SHARD。"),

    _room("B5", "OOM", "内存耗尽", 5, [
        N("scope", "ROOT", (0.50, 0.05), "SCOPE"),
        N("ka", "KERNEL", (0.32, 0.28), "OOM.L", 700, boss="kernel"),
        N("kb", "KERNEL", (0.68, 0.28), "OOM.R", 700, boss="kernel"),
        N("m1", "MINION", (0.20, 0.70), "MINION.70", 80),
        N("m2", "MINION", (0.80, 0.70), "MINION.71", 80),
        N("ward", "WARD", (0.50, 0.62), "WARD.72", 180, barrier=True),
    ], [E("scope", "ka"), E("scope", "kb"), E("ka", "kb"),
        E("kb", "ka"), E("ka", "m1"), E("kb", "m2"), E("ward", "ka"),
        E("ward", "kb")],
        danger=12, boss=True,
        intro="最后一块内存被两个内核互相引用。WARD 正在替它们续命。",
        hint="先拆 WARD 的支援，再用 WEAK 破双内核环；全部归零才算通关。"),
]

TUTORIAL_COUNT = 4
ROOM_BY_CODE = {r["code"]: r for r in ROOMS}
TUTORIALS = [r for r in ROOMS if r.get("tutorial")]
RUN_ROOMS = [r for r in ROOMS if not r.get("tutorial")]

# ---------------------------------------------------------------- 奖励池
CARD_POOL_ZONE = {
    1: ["CUT", "LINK", "WEAK", "CLIP", "SWEEP", "WEAKEN", "ALIAS", "ECC"],
    2: ["CUT", "LINK", "WEAK", "CLIP", "SWEEP", "WEAKEN", "ALIAS", "VOID",
        "TRUNC", "DELAY", "REFLECT", "COMPRESS", "ECC", "DOWN"],
    3: ["CUT", "LINK", "WEAK", "CLIP", "SWEEP", "WEAKEN", "ALIAS", "VOID",
        "TRUNC", "DELAY", "REFLECT", "STEAL", "COMPRESS", "ECC", "LOSSY",
        "DOWN"],
    4: ["CUT", "LINK", "WEAK", "CLIP", "SWEEP", "WEAKEN", "ALIAS", "VOID",
        "TRUNC", "DELAY", "REFLECT", "STEAL", "COMPRESS", "ECC", "LOSSY",
        "DOWN"],
    5: ["CUT", "LINK", "WEAK", "CLIP", "SWEEP", "WEAKEN", "ALIAS", "VOID",
        "TRUNC", "DELAY", "REFLECT", "STEAL", "COMPRESS", "ECC", "LOSSY",
        "DOWN"],
}

MODULE_POOL = [m["id"] for m in MODULES]

# ---------------------------------------------------------------- 关卡顺序
def room_for_step(step):
    """0..21：教程 4 + 正式 18（5 区 15 战 + 5 Boss）。"""
    if step < TUTORIAL_COUNT:
        return TUTORIALS[step]
    idx = step - TUTORIAL_COUNT
    if idx < len(RUN_ROOMS):
        return RUN_ROOMS[idx]
    return None


def zone_of(step):
    if step < TUTORIAL_COUNT:
        return 0
    r = room_for_step(step)
    return r["zone"] if r else 0


ZONE_NAMES = {
    0: ("教学沙盒", "TUTORIAL SANDBOX"),
    1: ("引用荒原", "REFERENCE WASTES"),
    2: ("并发回廊", "CONCURRENCY CORRIDOR"),
    3: ("类型深渊", "TYPE ABYSS"),
    4: ("碎片浅滩", "FRAGMENT SHALLOWS"),
    5: ("内核深渊", "KERNEL ABYSS"),
}
