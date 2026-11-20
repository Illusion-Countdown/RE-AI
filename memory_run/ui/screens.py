# -*- coding: utf-8 -*-
"""标题、奖励、模块、Boss 规则、暂停、帮助与结局界面。"""
import math

import pygame

from memory_run.const import *
from memory_run.content import GIRLS, BODIES
from memory_run.core.cards import CARD_DEFS
from memory_run.ui.render import draw_girl, draw_wrap, wrap
from memory_run.ui.deckui import draw_option_cards


def button(screen, rect, label, color=CYAN, sub="", on=True, size=20):
    r = pygame.Rect(*rect)
    fill = (13, 18, 26) if on else (10, 12, 16)
    pygame.draw.rect(screen, fill, r, border_radius=6)
    pygame.draw.rect(screen, color if on else (40, 48, 58), r, 2, border_radius=6)
    if on:
        glow(screen, r.centerx, r.centery, r.w * 0.55, color, 0.10)
    blit_text(screen, label, (r.centerx, r.centery - (8 if sub else 0)),
              size, WHITE if on else DIM, bold=True, anchor="center")
    if sub:
        blit_text(screen, sub, (r.centerx, r.centery + 16), 10, DIM,
                  anchor="center")
    return r


def _body_glyph(screen, kind, cx, cy, size, color):
    """复用 DANGLING 的身体符印。"""
    if kind == "list":
        for i in range(4):
            x = cx - size * 0.75 + i * size * 0.5
            pygame.draw.circle(screen, color, (int(x), int(cy)),
                               int(size * 0.16), 2)
            if i < 3:
                pygame.draw.line(screen, color, (x + size * 0.16, cy),
                                 (x + size * 0.34, cy), 2)
    elif kind == "array":
        w = size * 0.9
        for i in range(5):
            r = pygame.Rect(cx - w / 2 + i * w / 5, cy - size * 0.3,
                            w / 5 - 4, size * 0.6)
            pygame.draw.rect(screen, color, r, 2, border_radius=2)
        pygame.draw.line(screen, color, (cx - w / 2 - 10, cy + size * 0.45),
                         (cx + w / 2 + 10, cy + size * 0.45), 1)
    else:
        pts = [(cx, cy - size * 0.42), (cx - size * 0.42, cy + size * 0.1),
               (cx + size * 0.42, cy + size * 0.1),
               (cx - size * 0.22, cy + size * 0.42),
               (cx + size * 0.22, cy + size * 0.42)]
        for a, b in ((0, 1), (0, 2), (1, 3), (2, 4)):
            pygame.draw.line(screen, dim(color, 0.7), pts[a], pts[b], 1)
        for p in pts:
            pygame.draw.circle(screen, color, (int(p[0]), int(p[1])), 4)


def draw_title_bg(screen, t):
    screen.fill((6, 8, 12))
    # 透视网格
    for i in range(-8, 24):
        x = 80 + i * 80
        pygame.draw.line(screen, (14, 22, 30), (x, 0), (x + 200, H), 1)
    for y in range(0, H + 1, 50):
        pygame.draw.line(screen, (12, 18, 25), (0, y), (W, y), 1)
    # 复用的引用图背景：节点缓慢漂移，边只连接近邻
    _draw_ref_graph_bg(screen, t)
    # 漂浮内存块
    for i in range(24):
        x = (i * 137 + t * (12 + i % 5)) % (W + 80) - 40
        y = 100 + (i * 83) % 700
        s = 4 + (i % 4) * 3
        c = CYAN if i % 3 else PURPLE
        pygame.draw.rect(screen, dim(c, 0.20), (x, y, s * 3, s), 1)
    # 大光晕
    glow(screen, 1260, 360, 460, CYAN, 0.10)
    glow(screen, 300, 420, 380, MAGENTA, 0.06)


def _draw_ref_graph_bg(screen, t, seed=7):
    """DANGLING 式引用图背景：16 个节点、近邻连线、呼吸光。"""
    import random as _random
    rnd = _random.Random(seed)
    nodes = []
    for i in range(16):
        bx = rnd.uniform(70, W - 70)
        by = rnd.uniform(70, H - 70)
        ph = rnd.uniform(0, math.tau)
        c = (CYAN, CYAN, PURPLE, DIM2)[i % 4]
        x = bx + math.sin(t * 0.17 + ph) * 26
        y = by + math.cos(t * 0.13 + ph * 1.3) * 20
        nodes.append((x, y, c, ph))
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            ax, ay, ac, _ = nodes[i]
            bx, by, bc, _ = nodes[j]
            d = math.hypot(ax - bx, ay - by)
            if d < 300:
                k = 1 - d / 300
                pygame.draw.line(screen, mix(BG, mix(ac, bc, 0.5), 0.22 + 0.25 * k),
                                 (ax, ay), (bx, by), 1)
    for x, y, c, ph in nodes:
        p = 0.5 + 0.5 * math.sin(t * 1.5 + ph)
        glow(screen, x, y, 12 + p * 6, c, 0.16)
        pygame.draw.circle(screen, dim(c, 0.8), (int(x), int(y)),
                           2 + int(p * 2))
        pygame.draw.circle(screen, with_alpha(c, 60), (int(x), int(y)),
                           8 + int(p * 5), 1)


def draw_endgraph(screen, t, color, alive=True, seed=3):
    """复用 DANGLING 的结局引用图。"""
    import random as _random
    rnd = _random.Random(seed)
    pts = [(rnd.randint(150, W - 150), rnd.randint(120, H - 120))
           for _ in range(16)]
    for i in range(13):
        a, b = pts[i], pts[(i * 5 + 3) % len(pts)]
        pygame.draw.line(screen, dim(color, 0.17), a, b, 1)
    for i, p in enumerate(pts):
        if i < 4 and not alive:
            continue
        c = color if i % 3 else dim(color, 0.6)
        glow(screen, p[0], p[1], 30, c, 0.13)
        pygame.draw.circle(screen, dim(c, 0.7), (int(p[0]), int(p[1])),
                           3 + i % 3, 1)
        if not alive and i % 4 == 0:
            pygame.draw.line(screen, dim(RED, 0.5),
                             (p[0] - 6, p[1] - 6), (p[0] + 6, p[1] + 6), 1)
            pygame.draw.line(screen, dim(RED, 0.5),
                             (p[0] + 6, p[1] - 6), (p[0] - 6, p[1] + 6), 1)


def draw_title(screen, t, body_id="tree"):
    draw_title_bg(screen, t)
    blit_text(screen, "DANGLING // RUN", (90, 86), 13, CYAN, mono=True)
    blit_text(screen, "内存远征", (86, 112), 86, WHITE, bold=True, shadow=3)
    blit_text(screen, "把卡组塞进 5×5 的内存，留白就是你的工作内存。",
              (92, 218), 19, DIM)
    blit_text(screen, "剪断引用，让整片对象归零；画质是你的血，也是你的伤害。",
              (92, 248), 15, DIM2)
    # AI 娘
    draw_girl(screen, 1240, 360, 3.0, CYAN, (58, 178, 220), 0, t, portrait=True)
    blit_text(screen, "小忆", (1240, 560), 28, CYAN, bold=True, anchor="center")
    blit_text(screen, "DEEPSEEK / 你的向导", (1240, 590), 12, DIM,
              mono=True, anchor="center")
    # 四娘
    for i, g in enumerate(GIRLS):
        x = 900 + i * 130
        draw_girl(screen, x, 700, 0.55, g["color"], g["hair"], 0, t + i)
        blit_text(screen, g["name"], (x, 748), 12, g["color"], anchor="center")

    buttons = {}
    buttons["start"] = button(screen, (90, 330, 310, 62), "开始远征",
                              CYAN, "5 区 18 战（含 5 Boss）", size=24)
    buttons["tutorial"] = button(screen, (90, 406, 310, 52), "新手教程",
                                 GREEN, "4 个短房间，逐条教机制", size=20)
    buttons["help"] = button(screen, (90, 470, 310, 42), "操作与规则",
                             DIM, size=16)
    buttons["quit"] = button(screen, (90, 524, 310, 42), "退出",
                             DIM, size=16)
    # 身体选择
    blit_text(screen, "选择运行时（身体）", (90, 610), 12, DIM, mono=True)
    for i, b in enumerate(BODIES):
        r = pygame.Rect(90 + i * 250, 636, 230, 142)
        on = b["id"] == body_id
        pygame.draw.rect(screen, (13, 17, 25), r, border_radius=6)
        pygame.draw.rect(screen, b["color"] if on else (38, 48, 60), r,
                         2 if on else 1, border_radius=6)
        if on:
            glow(screen, r.centerx, r.centery, 150, b["color"], 0.18)
        blit_text(screen, b["name"], (r.x + 12, r.y + 8), 19,
                  b["color"] if on else WHITE, bold=True)
        blit_text(screen, b["en"], (r.right - 10, r.y + 12), 8, DIM,
                  mono=True, anchor="topright")
        blit_text(screen, f"HP {b['hp']}  SPEED {b['speed']}",
                  (r.x + 12, r.y + 36), 10, DIM, mono=True)
        _body_glyph(screen, b["id"], r.right - 42, r.y + 54, 28,
                    b["color"] if on else DIM)
        draw_wrap(screen, b["desc"], (r.x + 12, r.y + 58), 11, WHITE,
                  r.w - 24, 15)
        buttons[f"body_{b['id']}"] = r
        if on:
            blit_text(screen, "SELECTED", (r.right - 10, r.bottom - 14), 8,
                      b["color"], mono=True, anchor="topright")
    blit_text(screen, "pygame-ce  ·  1600×900  ·  F11 全屏  ·  M 静音  ·  F2 测试  ·  F3 切设备",
              (90, 812), 10, DIM2, mono=True)
    blit_text(screen, "设计依据：08_单人肉鸽_内存远征.md",
              (90, 832), 10, DIM2, mono=True)
    return buttons


def draw_help(screen):
    screen.fill((6, 8, 12))
    draw_title_bg(screen, 1.0)
    panel(screen, pygame.Rect(120, 90, 1360, 720), (9, 12, 18),
          (36, 48, 62), 8, alpha=245)
    blit_text(screen, "操作与规则 // README", (160, 120), 30, WHITE, bold=True)
    left = [
        ("移动 / 冲刺", "WASD / 方向键；E 向鼠标方向冲刺"),
        ("卡片", "1/2/3 选牌；SHIFT 上一张；SPACE 下一张"),
        ("目标", "按住卡拖过引用线/对象；红色攻击边用 CUT 剪断 = 振刀"),
        ("释放", "ECC / 压缩等自身卡：左键点战场任意处"),
        ("WRITE", "右键，朝鼠标方向打一发，不耗卡"),
        ("手牌", "固定 3 张；用 1 抽 1；牌堆空后停抽"),
        ("减速 / 冲刺", "按住中键减速；E 冲刺"),
        ("整备", "奖励后进入；装卡、免费 ++、进商店"),
    ]
    right = [
        ("refcount", "只数入边中的 STRONG 数量"),
        ("GC", "refcount 归零立刻级联；清子节点会缩小冲击波"),
        ("WEAK", "不计 refcount；目标受伤 +35%，对玩家伤害 -35%"),
        ("LINK", "从自己拖到敌人 = 争夺：它停火，替你分摊 15%/条，上限 45%"),
        ("CUT", "消耗 1 工作内存；鼠标划过的那条边被剪断"),
        ("CAST", "剥掉析构器和类型免疫，再 CUT 才安全"),
        ("ALIAS", "共享血池；炸弹和硬壳别名 = 一次引爆"),
        ("画质", "100−50×负载/总−50×工作/空闲，修格/删卡会回升"),
    ]
    y = 180
    for k, v in left:
        blit_text(screen, k, (170, y), 14, CYAN, bold=True)
        blit_text(screen, v, (330, y), 14, WHITE)
        y += 34
    y = 180
    for k, v in right:
        blit_text(screen, k, (810, y), 14, AMBER, bold=True)
        draw_wrap(screen, v, (960, y), 14, WHITE, 470, 20)
        y += 68
    blit_text(screen, "ESC 暂停 / 返回    M 静音    F11 全屏",
              (160, 758), 13, DIM, mono=True)
    return {"back": button(screen, (1320, 740, 120, 44), "返回", DIM, size=15)}


def draw_pause(screen, t):
    ov = pygame.Surface((W, H), pygame.SRCALPHA)
    ov.fill((4, 6, 9, 210))
    screen.blit(ov, (0, 0))
    panel(screen, pygame.Rect(540, 250, 520, 380), (10, 14, 20),
          (44, 60, 76), 8)
    blit_text(screen, "PAUSED", (800, 292), 38, WHITE, bold=True, anchor="center")
    blit_text(screen, "世界已冻结。检查你的手牌和网格。", (800, 340), 14,
              DIM, anchor="center")
    out = {}
    out["resume"] = button(screen, (650, 390, 300, 50), "继续", CYAN, size=18)
    out["help"] = button(screen, (650, 454, 300, 44), "操作与规则", DIM, size=15)
    out["abandon"] = button(screen, (650, 512, 300, 44), "放弃本局", RED, size=15)
    blit_text(screen, "ESC 继续  ·  M 静音", (800, 590), 11, DIM2,
              mono=True, anchor="center")
    return out


def draw_result_header(screen, run, result, mode="card"):
    panel(screen, pygame.Rect(0, 0, W, 190), (8, 11, 17), (36, 48, 62))
    perfect = bool(result and result.get("perfect"))
    title = "PERFECT CLEAR" if perfect else "ROOM CLEARED"
    col = GOLD if perfect else GREEN
    blit_text(screen, title, (90, 32), 46, col, bold=True, shadow=2)
    blit_text(screen, f"{run.room['code']}  {run.room['title']}  /  {run.zone_name}",
              (94, 92), 14, DIM, mono=True)
    if result:
        blit_text(screen, f"SCORE +{result.get('score', 0)}", (92, 126), 20,
                  WHITE, mono=True)
        blit_text(screen, f"画质 {int(result.get('quality', 0))}%   "
                          f"受伤 {'是' if result.get('damage', 0) else '否'}   "
                          f"新增坏死 {result.get('new_dead', 0)}",
                  (300, 132), 13, DIM)
        blit_text(screen, f"碎片 +{result.get('shards', 0)}", (700, 132), 13,
                  GOLD, mono=True)
        if perfect:
            blit_text(screen, "无伤 · 画质≥75 · 无新坏死：额外稀有卡 + 2 碎片",
                      (900, 132), 12, GOLD)
    hint = {"card": "三选一：选一张带进网格；放不下会进仓库。",
            "module": "三选一模块：规则改变，不是数值。",
            "rule": "Boss 规则：三选一，永久生效。"}[mode]
    blit_text(screen, hint, (92, 162), 12, DIM2)


def draw_reward(screen, run, result, options, mode="card"):
    screen.fill((7, 9, 13))
    draw_title_bg(screen, 0.5)
    draw_result_header(screen, run, result, mode)
    out = {}
    if mode == "card":
        rects = draw_option_cards(screen, options, y=230, w=360, h=380,
                                  gap=38)
        out["options"] = rects
        for i, (r, key) in enumerate(zip(rects, options)):
            pygame.draw.rect(screen, CARD_DEFS[key]["color"], r, 2, border_radius=8)
            blit_text(screen, f"推荐 {i + 1}", (r.centerx, r.bottom + 8), 10,
                      DIM, mono=True, anchor="midtop")
        out["skip"] = button(screen, (650, 792, 300, 46),
                             "跳过（无碎片）", DIM, size=14)
    elif mode == "module":
        out["options"] = _choice_panels(screen, options, "MODULE", AMBER,
                                        _module_text, run)
    else:
        out["options"] = _choice_panels(screen, options, "BOSS RULE", GOLD,
                                        _rule_text, run)
    out["deck"] = button(screen, (110, 792, 300, 46),
                         "整备 / 商店（先调整）", CYAN, size=14)
    blit_text(screen, "点击选择  ·  选择后自动继续", (W // 2, 866), 11,
              DIM2, anchor="center", mono=True)
    return out


def draw_shop(screen, run, items):
    screen.fill((7, 9, 13))
    draw_title_bg(screen, 0.7)
    panel(screen, pygame.Rect(70, 70, 1460, 760), (8, 11, 17),
          (38, 52, 66), 8, alpha=245)
    blit_text(screen, "黑市 // SHOP", (110, 100), 34, GOLD, bold=True)
    blit_text(screen, f"碎片 {run.shards}    只卖卡牌与规则增幅；修复请回整备。",
              (112, 144), 13, DIM)
    out = []
    for i, item in enumerate(items):
        r = pygame.Rect(110 + (i % 3) * 450, 200 + (i // 3) * 250, 420, 220)
        if item["kind"] == "card":
            from memory_run.core.cards import CARD_DEFS
            d = CARD_DEFS[item["key"]]
            col, name, sub = d["color"], d["cn"], d["en"] + " / CARD"
            desc = d["desc"]
        else:
            from memory_run.content import MODULE_BY_ID
            d = MODULE_BY_ID[item["id"]]
            col, name, sub = d["color"], d["name"], d["en"] + " / BOOST"
            desc = d["desc"]
        pygame.draw.rect(screen, dim(col, 0.10), r, border_radius=8)
        pygame.draw.rect(screen, col, r, 2, border_radius=8)
        blit_text(screen, sub, (r.x + 18, r.y + 14), 10, dim(col, 0.85),
                  mono=True)
        blit_text(screen, name, (r.x + 18, r.y + 36), 24, WHITE, bold=True)
        draw_wrap(screen, desc, (r.x + 18, r.y + 78), 13, WHITE,
                  r.w - 36, 19)
        can = run.shards >= item["price"]
        br = pygame.Rect(r.x + 18, r.bottom - 56, r.w - 36, 38)
        pygame.draw.rect(screen, dim(col, 0.22 if can else 0.06), br,
                         border_radius=5)
        pygame.draw.rect(screen, col if can else (48, 54, 62), br, 1,
                         border_radius=5)
        blit_text(screen, f"购买  {item['price']} 碎片", (br.centerx, br.centery),
                  14, WHITE if can else DIM, anchor="center")
        out.append(br)
    back = button(screen, (1370, 100, 120, 38), "返回", DIM, size=13)
    return {"items": out, "back": back}


def _module_text(screen, run, mid):
    from memory_run.content import MODULE_BY_ID
    m = MODULE_BY_ID[mid]
    return m["name"], m["en"], m["desc"], m["color"]


def _draw_module_sigil(screen, mid, cx, cy, color):
    """复用/改写 DANGLING 的模块符印：规则不同，图形语言一致。"""
    if mid == "exception":
        pts = [(cx, cy - 34), (cx + 28, cy - 18), (cx + 22, cy + 22),
               (cx, cy + 34), (cx - 22, cy + 22), (cx - 28, cy - 18)]
        pygame.draw.polygon(screen, color, pts, 2)
        blit_text(screen, "TRY", (cx, cy), 12, color, anchor="center",
                  mono=True, bold=True)
    elif mid == "inline":
        for i in range(3):
            pygame.draw.line(screen, dim(color, 0.4 + i * 0.25),
                             (cx - 34 + i * 10, cy + 22),
                             (cx + 22 - i * 10, cy - 22), 2)
    elif mid == "weak_net":
        for i in range(4):
            pygame.draw.line(screen, dim(color, 0.25 + i * 0.2),
                             (cx - 36, cy - 20 + i * 13),
                             (cx + 36, cy + 8 - i * 7), 1)
    elif mid == "steal":
        pygame.draw.circle(screen, color, (cx - 18, cy), 18, 2)
        pygame.draw.circle(screen, color, (cx + 18, cy), 18, 2)
        pygame.draw.line(screen, color, (cx - 4, cy), (cx + 4, cy), 2)
    elif mid == "cascade_bonus":
        for i in range(3):
            pygame.draw.circle(screen, dim(color, 0.35 + i * 0.3),
                               (cx - 26 + i * 26, cy), 12, 2)
    elif mid == "compressor":
        for i in range(3):
            pygame.draw.rect(screen, color if i < 2 else dim(color, 0.35),
                             (cx - 30 + i * 22, cy - 18, 16, 36), 2,
                             border_radius=2)
    elif mid == "lossless":
        pygame.draw.arc(screen, color, (cx - 34, cy - 20, 68, 40),
                        0.2, 2.9, 3)
        pygame.draw.circle(screen, color, (cx, cy), 7)
    elif mid == "redundancy":
        pygame.draw.rect(screen, color, (cx - 30, cy - 24, 60, 48), 2)
        blit_text(screen, "ECC", (cx, cy), 13, color, anchor="center",
                  mono=True, bold=True)
    elif mid == "wreck":
        for i in range(6):
            a = i * math.tau / 6 + 0.4
            pygame.draw.line(screen, dim(color, 0.4 + i * 0.08),
                             (cx + math.cos(a) * 12, cy + math.sin(a) * 12),
                             (cx + math.cos(a) * 34, cy + math.sin(a) * 34), 2)
    elif mid == "necro_bomb":
        pygame.draw.circle(screen, color, (cx, cy), 24, 2)
        pygame.draw.line(screen, color, (cx, cy - 24), (cx + 8, cy - 36), 2)
        blit_text(screen, "×", (cx, cy), 18, color, anchor="center", bold=True)
    elif mid == "overload":
        pygame.draw.polygon(screen, color,
                            [(cx + 8, cy - 36), (cx - 16, cy + 2),
                             (cx, cy + 2), (cx - 6, cy + 36),
                             (cx + 22, cy - 8), (cx + 4, cy - 8)], 2)
    elif mid == "dead_code":
        for i in range(4):
            pygame.draw.line(screen, dim(color, 0.35),
                             (cx - 36, cy - 22 + i * 14),
                             (cx + 36, cy - 22 + i * 14), 2)
        pygame.draw.line(screen, color, (cx - 36, cy - 34),
                         (cx + 36, cy + 30), 3)
    elif mid == "cow":
        pygame.draw.rect(screen, color, (cx - 30, cy - 22, 36, 44), 2)
        pygame.draw.rect(screen, dim(color, 0.6), (cx - 12, cy - 30, 36, 44), 2)
    elif mid == "tail_rec":
        pygame.draw.arc(screen, color, (cx - 30, cy - 24, 60, 48),
                        0.3, 5.6, 2)
        pygame.draw.polygon(screen, color,
                            [(cx + 20, cy - 24), (cx + 34, cy - 18),
                             (cx + 20, cy - 10)])
    else:
        pygame.draw.circle(screen, color, (cx, cy), 28, 2)
        blit_text(screen, "?", (cx, cy), 22, color, anchor="center",
                  bold=True)


def _rule_text(screen, run, rid):
    from memory_run.content import BOSS_RULES
    r = next(x for x in BOSS_RULES if x["id"] == rid)
    return r["name"], "BOSS RULE", r["desc"], GOLD


def _choice_panels(screen, options, tag, color, textfn, run=None):
    w, h, gap = 360, 430, 38
    start = (W - (len(options) * w + (len(options) - 1) * gap)) // 2
    rects = []
    for i, oid in enumerate(options):
        r = pygame.Rect(start + i * (w + gap), 226, w, h)
        pygame.draw.rect(screen, (13, 17, 25), r, border_radius=8)
        pygame.draw.rect(screen, color, r, 2, border_radius=8)
        name, en, desc, col = textfn(screen, run, oid)
        blit_text(screen, f"{tag} {i + 1}", (r.centerx, r.y + 20), 10,
                  DIM, mono=True, anchor="midtop")
        # 图标
        cx, cy = r.centerx, r.y + 100
        pygame.draw.circle(screen, dim(col, 0.2), (cx, cy), 42)
        if tag == "MODULE":
            _draw_module_sigil(screen, oid, cx, cy, col)
        else:
            pygame.draw.circle(screen, col, (cx, cy), 42, 2)
            pygame.draw.circle(screen, col, (cx, cy), 8)
            for k in range(4):
                a = k * math.tau / 4 + 0.4
                pygame.draw.line(screen, dim(col, 0.6),
                                 (cx + math.cos(a) * 48, cy + math.sin(a) * 48),
                                 (cx + math.cos(a) * 60, cy + math.sin(a) * 60), 2)
        blit_text(screen, name, (r.centerx, r.y + 164), 24, WHITE,
                  bold=True, anchor="midtop")
        blit_text(screen, en, (r.centerx, r.y + 198), 10, dim(col, 0.9),
                  mono=True, anchor="midtop")
        draw_wrap(screen, desc, (r.x + 26, r.y + 238), 15, WHITE,
                  r.w - 52, 22)
        blit_text(screen, "点击选择", (r.centerx, r.bottom - 26), 11,
                  col, mono=True, anchor="center")
        rects.append(r)
    return rects


def draw_end(screen, run, victory, t=0.0):
    screen.fill((6, 8, 12))
    draw_endgraph(screen, t, GREEN if victory else RED, alive=victory, seed=9)
    # 给结算数据一层暗底，避免引用图穿过数字
    panel(screen, pygame.Rect(56, 238, 920, 430), (6, 8, 12), None, 8,
          alpha=215)
    col = GREEN if victory else RED
    title = "远征完成" if victory else "进程终止"
    blit_text(screen, "MEMORY RUN // END", (80, 80), 13, col, mono=True)
    blit_text(screen, title, (76, 110), 72, col, bold=True, shadow=3)
    if victory:
        blit_text(screen, "你带着一套完整的构筑从内存里活着回来了。",
                  (82, 200), 18, WHITE)
    else:
        blit_text(screen, "REF 耗尽，或者画质把你从渲染管线里踢了出去。",
                  (82, 200), 18, WHITE)
    s = run.summary()
    lines = [
        ("最终得分", str(s["score"])),
        ("清房", f"{s['rooms']} 间"),
        ("完美", f"{s['perfects']} 次"),
        ("模块", f"{s['modules']} 个"),
        ("GC 擦除", str(s["gc"])),
        ("剪断", str(s["cuts"])),
        ("战斗时间", f"{int(s['time'] // 60)}:{int(s['time'] % 60):02d}"),
        ("剩余碎片", str(run.shards)),
    ]
    y = 280
    for i, (k, v) in enumerate(lines):
        x = 90 + (i // 4) * 420
        yy = y + (i % 4) * 56
        blit_text(screen, k, (x, yy), 12, DIM, mono=True)
        blit_text(screen, v, (x, yy + 18), 28, WHITE, bold=True, mono=True)
    # 牌组
    blit_text(screen, "最终网格", (90, 540), 11, DIM, mono=True)
    g = run.deck.grid
    cell = 30
    for r in range(g.h):
        for c in range(g.w):
            rr = pygame.Rect(90 + c * cell, 562 + r * cell, cell - 2, cell - 2)
            if (r, c) in g.dead:
                pygame.draw.rect(screen, RED, rr, 1)
            elif (r, c) in g.owner:
                pygame.draw.rect(screen, g.owner[(r, c)].color, rr)
            else:
                pygame.draw.rect(screen, (30, 40, 52), rr, 1)
    blit_text(screen, f"{g.w}×{g.h}  ·  空闲 {g.free_count()}  ·  坏死 {len(g.dead)}",
              (90, 562 + g.h * cell + 10), 11, DIM, mono=True)
    out = {}
    out["again"] = button(screen, (1000, 620, 240, 54), "再来一局", col, size=18)
    out["title"] = button(screen, (1260, 620, 240, 54), "返回标题", DIM, size=16)
    return out


def draw_tutorial_clear(screen, run):
    screen.fill((7, 9, 13))
    draw_title_bg(screen, 0.6)
    panel(screen, pygame.Rect(360, 220, 880, 440), (9, 12, 18),
          (40, 56, 72), 8)
    blit_text(screen, f"TUTORIAL {run.step + 1}/{4}", (W // 2, 260), 14,
              CYAN, mono=True, anchor="center")
    blit_text(screen, "这一课过了。", (W // 2, 296), 34, WHITE, bold=True,
              anchor="center")
    draw_wrap(screen, run.room.get("hint", ""), (W // 2, 360), 16, WHITE,
              700, 24, anchor="midtop")
    out = {}
    out["next"] = button(screen, (610, 540, 380, 54), "下一课", CYAN, size=18)
    return out


def draw_tutorial_end(screen):
    screen.fill((6, 8, 12))
    draw_title_bg(screen, 0.8)
    panel(screen, pygame.Rect(300, 190, 1000, 480), (9, 12, 18),
          (40, 56, 72), 8)
    blit_text(screen, "TUTORIAL COMPLETE", (W // 2, 230), 16, CYAN,
              mono=True, anchor="center")
    blit_text(screen, "你已经会改所有权了。", (W // 2, 270), 36, WHITE,
              bold=True, anchor="center")
    draw_wrap(screen,
              "接下来是真正的远征：5 个区、18 个固定房间、5 个 Boss。"
              "每次清房三选一卡牌，每两房三选一模块，Boss 后进入安全屋整备。"
              "卡组会越来越重，画质会越来越低——你要决定带什么、留多少空。",
              (W // 2, 330), 17, WHITE, 760, 26, anchor="midtop")
    blit_text(screen, "教程奖励：纠错码 ×1  ·  碎片 +1", (W // 2, 470), 14,
              GOLD, anchor="center")
    out = {}
    out["run"] = button(screen, (540, 530, 250, 54), "进入正式远征", CYAN, size=18)
    out["title"] = button(screen, (810, 530, 250, 54), "返回标题", DIM, size=16)
    return out
