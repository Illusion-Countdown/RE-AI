# -*- coding: utf-8 -*-
from memory_run.const import GREEN, AMBER, PURPLE, TEAL, GOLD, RED, CYAN, DIM, MAGENTA, BLUE

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
