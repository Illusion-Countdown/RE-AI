# -*- coding: utf-8 -*-
"""内容表：四种身体（数据结构）、模块奖励、九个固定房间。"""
from .const import *

# ---------------------------------------------------------------- 身体
BODIES = [
    {
        "id": "list", "name": "链表", "en": "LINKED LIST", "color": CYAN,
        "hp": 80, "speed": 332, "slices": 6, "regen": 0.60, "heap": 2,
        "gc_period": 19.0,
        "passive": "插入 O(1)：Shift 瞬移到指针位置，冷却 2.2 秒。",
        "disaster": "断链：每 15 秒，你建立的一条引用被随机剪断，并受到 8 伤害。",
        "stats": {"机动": 5, "韧性": 1, "资源": 2, "操作": 5},
        "flavor": "极脆、极快。剪错一条线，断的就是你自己。",
    },
    {
        "id": "array", "name": "数组", "en": "ARRAY", "color": GREEN,
        "hp": 150, "speed": 196, "slices": 8, "regen": 0.86, "heap": 2,
        "gc_period": 18.0,
        "passive": "索引 O(1)：CUT 工具点中一个节点，直接剪掉它所有入边（+1 时间片）。",
        "disaster": "扩容：每 18 秒全场震动 1.2 秒，期间你无法移动。",
        "stats": {"机动": 2, "韧性": 5, "资源": 4, "操作": 3},
        "flavor": "站桩、高血。扩容的那一刻，你会希望自己不在场上。",
    },
    {
        "id": "hash", "name": "哈希表", "en": "HASH TABLE", "color": BLUE,
        "hp": 108, "speed": 274, "slices": 7, "regen": 0.78, "heap": 3,
        "gc_period": 17.0,
        "passive": "冲突：CUT 时有 28% 概率连锁剪断一条同源边。",
        "disaster": "rehash：负载因子随节点数上涨，达 0.75 时全场洗牌。",
        "stats": {"机动": 3, "韧性": 3, "资源": 4, "操作": 4},
        "flavor": "负载因子是你的血压。0.75 之前，你还是这局的主人。",
    },
    {
        "id": "tree", "name": "树／图", "en": "TREE / GRAPH", "color": PURPLE,
        "hp": 96, "speed": 250, "slices": 7, "regen": 0.72, "heap": 2,
        "gc_period": 18.0,
        "passive": "范围失效：CUT 点中节点会同时剪断它的全部出边（+1 时间片）。",
        "disaster": "退化：每用一次范围失效，速度 -12%；第 4 次后退化为链表。",
        "stats": {"机动": 3, "韧性": 2, "资源": 3, "操作": 5},
        "flavor": "一次切断整棵子树。代价是你自己慢慢变成一条链。",
    },
]

# ---------------------------------------------------------------- 模块
MODULES = [
    {"id": "alias_e", "name": "别名增幅", "en": "ALIAS+", "color": MAGENTA,
     "tag": "别名",
     "desc": "ALIAS 消耗改为 1 时间片。别名组受到的伤害 +25%，同步给全体。",
     "why": "适合炸弹、连锁敌人，以及把自己和 Boss 绑在一起的人。"},
    {"id": "weak_f", "name": "零费弱引", "en": "WEAK.FREE", "color": PURPLE,
     "tag": "弱引用",
     "desc": "WEAK 边不再消耗时间片。悬垂指针与破环都免费。",
     "why": "适合 Cycler 破环，以及提前埋悬垂指针的长期投资。"},
    {"id": "gc_bat", "name": "GC 电池", "en": "GC.CELL", "color": GREEN,
     "tag": "GC",
     "desc": "每次 GC 擦除返还 1 时间片，可超出上限 2 格。",
     "why": "适合能一次剪断整片子树的构筑。"},
    {"id": "heap_x", "name": "堆扩容", "en": "HEAP.X2", "color": TEAL,
     "tag": "资源",
     "desc": "堆上限 +2，立刻获得 1 点。别让它再被 ALIAS 吃空。",
     "why": "适合 ALIAS 重度使用者。堆永远不够。"},
    {"id": "ptr_prec", "name": "指针精度", "en": "PTR.PREC", "color": AMBER,
     "tag": "越界",
     "desc": "越界不再流失生命；元数据操作费用 -1。OFF-BY-ONE 成为常规武器。",
     "why": "适合打算长期住在边界外的人。"},
    {"id": "leak_cover", "name": "泄漏掩体", "en": "LEAK.COVER", "color": DIM,
     "tag": "泄漏",
     "desc": "泄漏物挡弹范围扩大，OOM 压力减半。垃圾是最好的墙。",
     "why": "适合拿泄漏物搭墙、打阵地战的构筑。"},
    {"id": "overclock", "name": "时间超频", "en": "OVERCLOCK", "color": CYAN,
     "tag": "时间片",
     "desc": "时间片上限 +2，回复速度 +25%。",
     "why": "适合手速快，想在一回合里做更多拓扑改造。"},
    {"id": "null_shield", "name": "空指针护盾", "en": "NULL.SHIELD", "color": WHITE,
     "tag": "防御",
     "desc": "受到伤害时 35% 概率让攻击者 segfault 1.5 秒。",
     "why": "适合近身 WRITE、不躲子弹的构筑。"},
    {"id": "bomb_cache", "name": "炸弹缓存", "en": "BOMB.CACHE", "color": GOLD,
     "tag": "炸弹",
     "desc": "每个房间开始时，在你身边生成一枚可别名的炸弹节点。",
     "why": "适合别名流。每关一颗免费核弹。"},
    {"id": "dead_code", "name": "死代码消除", "en": "DEAD.CODE", "color": DIM,
     "tag": "控场",
     "desc": "每房间一次（R 键）：全场敌人停火 3 秒，并清空其重建计时。",
     "why": "适合被弹幕压得抬不起头的时候。"},
    {"id": "vamp", "name": "吸血指针", "en": "VAMP.PTR", "color": RED,
     "tag": "回复",
     "desc": "WRITE 命中回复 4 生命；若你处于别名组，回复计入共享血池。",
     "why": "适合把自己和 Boss 别名之后的吸血循环。"},
    {"id": "cascade", "name": "级联红利", "en": "CASCADE", "color": GREEN,
     "tag": "级联",
     "desc": "一次擦除 ≥2 个对象时：返还 2 时间片、回复 8 生命、额外 +80 分。",
     "why": "适合切枢纽、追求一次擦除一片的构筑。"},
]

# ---------------------------------------------------------------- 元数据
META = {
    "spawn": {"name": "REFRESH TABLE", "cn": "刷新表", "color": AMBER,
              "desc": "冻结全场敌人的行动计时 8 秒", "cost": 2},
    "refcount": {"name": "REFCOUNT TABLE", "cn": "引用计数表", "color": CYAN,
                 "desc": "所有敌人各失去 1 条入边", "cost": 2},
    "heap": {"name": "ARENA META", "cn": "竞技场元数据", "color": GREEN,
             "desc": "回复 3 时间片、2 点堆", "cost": 2},
    "boss": {"name": "BOSS METADATA", "cn": "Boss 元数据", "color": MAGENTA,
             "desc": "剪断 Boss 的全部出边", "cost": 3},
}


def N(id, kind, p, name=None, hp=None, **kw):
    d = {"id": id, "kind": kind, "p": p, "name": name, "hp": hp}
    d.update(kw)
    return d


def E(a, b, kind="STRONG"):
    return (a, b, kind)


# ---------------------------------------------------------------- 房间
ROOMS = [
    {
        "code": "R01", "title": "HELLO, WORLD", "cn": "你好，世界", "danger": 1,
        "calm": 1.7,
        "intro": "这不是一场战斗，是一次重构。",
        "hint": "按 [2] 切到 CUT，用鼠标划过引用线剪断它。引用计数归零，它就会被 GC 直接擦除——不必打血条。",
        "nodes": [
            N("scope", "ROOT", (0.50, 0.09), "SCOPE"),
            N("s", "SENTINEL", (0.50, 0.40), "SENTINEL.01", 66),
            N("m1", "MINION", (0.26, 0.72), "MINION.02", 24),
            N("m2", "MINION", (0.74, 0.72), "MINION.03", 24),
        ],
        "edges": [E("scope", "s"), E("s", "m1"), E("s", "m2")],
        "oob": [],
        "leaks": [],
        "free_slots": [],
    },
    {
        "code": "R02", "title": "THE CYCLE", "cn": "环", "danger": 2,
        "calm": 1.3,
        "intro": "两个对象互相引用，谁都不会归零。",
        "hint": "强引用环会自我重建。用 WEAK 边（紫色虚线）占住方向，再剪断强边。",
        "nodes": [
            N("scope", "ROOT", (0.50, 0.08), "SCOPE"),
            N("a", "CYCLER", (0.31, 0.44), "CYCLER.A", 62, partner="b"),
            N("b", "CYCLER", (0.69, 0.44), "CYCLER.B", 62, partner="a"),
        ],
        "edges": [E("scope", "a"), E("scope", "b"),
                  E("a", "b"), E("b", "a")],
        "oob": [], "leaks": [], "free_slots": [],
    },
    {
        "code": "R03", "title": "ALLOCATOR", "cn": "分配器", "danger": 2,
        "intro": "它不断申请新节点，把 n 抬高。",
        "hint": "剪断它唯一的入边，它生成的所有子节点会一起被级联回收。",
        "nodes": [
            N("scope", "ROOT", (0.50, 0.08), "SCOPE"),
            N("al", "ALLOCATOR", (0.50, 0.34), "ALLOCATOR.01", 74),
            N("m1", "MINION", (0.24, 0.66), "MINION.02", 24),
            N("m2", "MINION", (0.76, 0.66), "MINION.03", 24),
        ],
        "edges": [E("scope", "al"), E("al", "m1"), E("al", "m2")],
        "oob": [], "leaks": [], "free_slots": [],
    },
    {
        "code": "R04", "title": "USE AFTER FREE", "cn": "释放后使用", "danger": 3,
        "intro": "它已经被回收了，但还有指针指着它。",
        "hint": "用 WEAK 咬住僵尸的槽位，再剪断它的悬垂边。分配器会把新对象放进那个槽——那条弱引用就接管了它。",
        "nodes": [
            N("scope", "ROOT", (0.50, 0.07), "SCOPE"),
            N("dead", "ROOT", (0.14, 0.86), "0xDEAD"),
            N("al", "ALLOCATOR", (0.50, 0.28), "ALLOCATOR.01", 74),
            N("z", "ZOMBIE", (0.66, 0.62), "ZOMBIE.04", 0),
        ],
        "edges": [E("scope", "al"), E("dead", "z", "DANGLING")],
        "oob": [], "leaks": [],
        "free_slots": [(0.66, 0.62)],
        "alloc_slot": (0.66, 0.62),
        "realloc": True,
    },
    {
        "code": "R05", "title": "MEMORY LEAK", "cn": "内存泄漏", "danger": 3,
        "intro": "失去引用，却没被回收的东西。",
        "hint": "泄漏物不可选中、不可回收，但会挡子弹——对敌人不可见。别用 WRITE 制造更多泄漏。",
        "nodes": [
            N("scope", "ROOT", (0.50, 0.07), "SCOPE"),
            N("s", "SENTINEL", (0.50, 0.26), "SENTINEL.05", 70),
            N("m1", "MINION", (0.22, 0.62), "MINION.06", 24),
            N("m2", "MINION", (0.78, 0.62), "MINION.07", 24),
        ],
        "edges": [E("scope", "s"), E("s", "m1"), E("s", "m2")],
        "oob": [],
        "leaks": [(0.36, 0.50), (0.50, 0.54), (0.64, 0.50), (0.43, 0.38)],
        "free_slots": [],
    },
    {
        "code": "R06", "title": "OFF BY ONE", "cn": "差一格", "danger": 4,
        "intro": "边界之外那一格，是关卡自己的元数据。",
        "hint": "贴着竞技场边缘继续走，可以跨出界一格。越界会掉血、有 UB 风险，但能读写刷新表、引用计数表和元数据。",
        "nodes": [
            N("scope", "ROOT", (0.50, 0.07), "SCOPE"),
            N("s", "SENTINEL", (0.42, 0.28), "SENTINEL.08", 80),
            N("al", "ALLOCATOR", (0.72, 0.30), "ALLOCATOR.09", 74),
            N("m1", "MINION", (0.18, 0.62), "MINION.10", 24),
            N("m2", "MINION", (0.44, 0.70), "MINION.11", 24),
            N("m3", "MINION", (0.70, 0.68), "MINION.12", 24),
            N("m4", "MINION", (0.86, 0.52), "MINION.13", 24),
        ],
        "edges": [E("scope", "s"), E("scope", "al"),
                  E("s", "m1"), E("s", "m2"), E("al", "m3"), E("al", "m4")],
        "oob": ["spawn", "refcount", "heap"],
        "leaks": [(0.58, 0.50)],
        "free_slots": [],
    },
    {
        "code": "R07", "title": "ALIASING", "cn": "别名", "danger": 4,
        "intro": "两个指针指向同一块内存。伤害也是。",
        "hint": "ALIAS 让两个对象共享血条。把炸弹和硬壳别名，再剪掉炸弹的入边让它被回收——一次引爆等于击杀。",
        "nodes": [
            N("scope", "ROOT", (0.50, 0.07), "SCOPE"),
            N("scope2", "ROOT", (0.10, 0.20), "ROOT.02"),
            N("bomb", "BOMB", (0.26, 0.66), "BOMB.14", 20),
            N("brute", "MINION", (0.68, 0.36), "BRUTE.15", 220),
            N("m1", "MINION", (0.83, 0.62), "MINION.16", 26),
        ],
        "edges": [E("scope", "brute"), E("scope2", "brute"),
                  E("scope", "m1"), E("scope", "bomb"),
                  E("bomb", "brute", "WEAK")],
        "oob": ["spawn", "heap"],
        "leaks": [],
        "free_slots": [],
    },
    {
        "code": "R08", "title": "SENTINEL PRIME", "cn": "枢纽", "danger": 5,
        "intro": "整张图都挂在同一个节点上。",
        "hint": "先找枢纽：谁身上挂着最多的边？切掉它，整片一起归零。",
        "nodes": [
            N("scope", "ROOT", (0.50, 0.06), "SCOPE"),
            N("sp", "SENTINEL", (0.50, 0.30), "SENTINEL.PRIME", 120),
            N("m1", "MINION", (0.20, 0.55), "MINION.17", 24),
            N("m2", "MINION", (0.34, 0.74), "MINION.18", 24),
            N("m3", "MINION", (0.64, 0.74), "MINION.19", 24),
            N("m4", "MINION", (0.80, 0.55), "MINION.20", 24),
            N("al", "ALLOCATOR", (0.16, 0.30), "ALLOCATOR.21", 70),
            N("ca", "CYCLER", (0.84, 0.30), "CYCLER.A", 58, partner="cb"),
            N("cb", "CYCLER", (0.84, 0.52), "CYCLER.B", 58, partner="ca"),
        ],
        "edges": [E("scope", "sp"), E("scope", "al"), E("scope", "ca"),
                  E("sp", "m1"), E("sp", "m2"), E("sp", "m3"), E("sp", "m4"),
                  E("al", "m1"), E("ca", "cb"), E("cb", "ca")],
        "oob": ["spawn", "refcount", "heap"],
        "leaks": [],
        "free_slots": [],
    },
    {
        "code": "R09", "title": "GC BOSS", "cn": "垃圾回收者", "danger": 6,
        "intro": "它决定什么时候，全世界停下来。",
        "hint": "先剪断三根塔架到核心的引用。它不会死——它会重构自己。",
        "boss": True,
        "nodes": [
            N("scope", "ROOT", (0.50, 0.05), "SCOPE"),
            N("core", "CORE", (0.50, 0.32), "GC.CORE", 600),
            N("p1", "PYLON", (0.18, 0.72), "PYLON.01", 80),
            N("p2", "PYLON", (0.50, 0.80), "PYLON.02", 80),
            N("p3", "PYLON", (0.82, 0.72), "PYLON.03", 80),
        ],
        "edges": [E("scope", "p1"), E("scope", "p2"), E("scope", "p3"),
                  E("p1", "core"), E("p2", "core"), E("p3", "core")],
        "oob": ["refcount", "heap", "boss"],
        "leaks": [],
        "free_slots": [],
    },
]

BOSS_PHASE2_NODES = [
    N("core_a", "CORE", (0.34, 0.36), "GC.CORE.L", 320),
    N("core_b", "CORE", (0.66, 0.36), "GC.CORE.R", 320),
]
BOSS_PHASE2_EDGES = [E("core_a", "core_b"), E("core_b", "core_a")]
