# -*- coding: utf-8 -*-
from .render_deps import *


class HudMixin:
    def draw_ui(self, screen, b, mouse):
        self.draw_top(screen, b)
        self.draw_memory(screen, b)
        self.draw_hand(screen, b, mouse)
        self.draw_hint(screen, b, mouse)
        self.draw_banner(screen, b)

    # ------------------------------------------------------------ 顶部

    def draw_top(self, screen, b):
        r = b.room
        zone = b.run.zone_name
        blit_text(screen, f"{zone}  /  {r['code']}", (30, 20), 22, WHITE,
                  bold=True, shadow=2)
        blit_text(screen, f"{r['title']}  ·  {r.get('cn', '')}", (30, 49), 12,
                  DIM, shadow=1)

        # 时间：只保留一个轻量浮标
        blit_text(screen, "TIME", (W // 2, 14), 9, DIM, mono=True,
                  anchor="midtop")
        blit_text(screen, f"{int(b.time // 60):02d}:{int(b.time % 60):02d}",
                  (W // 2, 26), 24, WHITE, mono=True, anchor="midtop", shadow=2)
        blit_text(screen, f"ROOM {b.run.step + 1:02d}", (W // 2, 56), 10,
                  DIM, mono=True, anchor="midtop")

        # 右上：HP / 画质 / REF，紧凑悬浮，不做整条顶栏
        q = b.quality()
        qcol = GREEN if q >= 75 else (AMBER if q >= 50 else RED)
        hpcol = RED if b.hp < b.max_hp * 0.35 else GREEN
        x0, x1 = W - 430, W - 285
        blit_text(screen, "HP", (x0, 15), 9, DIM, mono=True)
        blit_text(screen, f"{int(b.hp)}/{int(b.max_hp)}", (x0, 28), 17,
                  WHITE, mono=True)
        bar(screen, pygame.Rect(x0, 52, 112, 4), b.hp / max(1, b.max_hp), hpcol)
        blit_text(screen, "QUALITY", (x1, 15), 9, DIM, mono=True)
        blit_text(screen, f"{int(q)}%", (x1, 28), 17, qcol, mono=True)
        bar(screen, pygame.Rect(x1, 52, 112, 4), q / 100, qcol)
        blit_text(screen, "REF", (W - 135, 15), 9, DIM, mono=True)
        for i in range(3):
            c = CYAN if i < b.run.refs else (30, 40, 50)
            pygame.draw.circle(screen, c, (W - 124 + i * 17, 38), 5)
        if b.erase_streak:
            blit_text(screen, f"CASCADE x{b.erase_streak}", (W - 30, 54), 10,
                      GREEN, mono=True, anchor="topright")

        # Boss 血条：需要，但保持透明底
        boss = next((n for n in b.graph.nodes
                     if n.alive and n.data.get("boss")), None)
        if boss:
            bw = 560
            br = pygame.Rect(W // 2 - bw // 2, 92, bw, 8)
            pygame.draw.rect(screen, (20, 14, 24), br.inflate(4, 4),
                             border_radius=4)
            f = clamp(boss.hp / max(1, boss.max_hp), 0, 1)
            pygame.draw.rect(screen, MAGENTA,
                             (br.x, br.y, max(1, int(br.w * f)), br.h),
                             border_radius=4)
            if boss.data.get("boss") == "gc" and boss.data.get("invuln"):
                label = "IMMUNE — 拆掉三根塔架"
            else:
                label = f"{boss.name}  {int(boss.hp)}/{int(boss.max_hp)}"
            blit_text(screen, label, (W // 2, 104), 10, WHITE,
                      anchor="midtop", shadow=1)

    # ------------------------------------------------------------ 左侧内存块

    def draw_memory(self, screen, b):
        x, y, w = 24, 118, 218
        free = max(1, b.deck.grid.free_count())
        panel(screen, pygame.Rect(x, y, w, 252), (8, 12, 17),
              (34, 48, 60), 6, alpha=128)
        blit_text(screen, "MEMORY GRID", (x + 12, y + 12), 9, DIM,
                  mono=True)
        blit_text(screen, f"{sum(1 for c in b.deck.cards if c.anchor)} CARDS",
                  (x + w - 12, y + 12), 9, DIM, mono=True,
                  anchor="topright")
        self.mini_grid(screen, pygame.Rect(x + 12, y + 30, w - 24, 132),
                       b.deck.grid)
        blit_text(screen, "WORK", (x + 12, y + 176), 9, DIM, mono=True)
        blit_text(screen, f"{b.work_used:.0f}/{free}", (x + w - 12, y + 174),
                  11, CYAN, mono=True, anchor="topright")
        bar(screen, pygame.Rect(x + 12, y + 192, w - 24, 4),
            max(0.0, 1 - b.work_used / free),
            CYAN if b.work_used < free * 0.5 else AMBER)
        blit_text(screen, f"牌堆 {len(b.pile)}  ·  回收 {b.returned}  ·  耗尽 {len(b.used)}",
                  (x + 12, y + 206), 10, DIM2)
        blit_text(screen, f"手牌 {b.hand.total()}/3", (x + 12, y + 222), 10,
                  DIM2, mono=True)
        if b.run.modules:
            names = "  ".join(m["name"] for m in b.run.modules[-3:])
            blit_text(screen, names, (x + 12, y + 238), 9, DIM2)

    def mini_grid(self, screen, rect, grid):
        cw = rect.w / grid.w
        ch = rect.h / grid.h
        pygame.draw.rect(screen, (8, 10, 14), rect)
        for r in range(grid.h):
            for c in range(grid.w):
                cell = pygame.Rect(rect.x + c * cw + 1, rect.y + r * ch + 1,
                                   max(1, cw - 2), max(1, ch - 2))
                if (r, c) in grid.dead:
                    pygame.draw.rect(screen, (70, 20, 28), cell)
                elif (r, c) in grid.owner:
                    card = grid.owner[(r, c)]
                    pygame.draw.rect(screen, dim(card.color, 0.45), cell)
                    pygame.draw.rect(screen, dim(card.color, 0.85), cell, 1)
                else:
                    pygame.draw.rect(screen, (16, 22, 30), cell, 1)
        pygame.draw.rect(screen, (40, 54, 70), rect, 1)

    # ------------------------------------------------------------ 右侧提示

    def draw_hint(self, screen, b, mouse):
        hovered = None
        for rect, _where, card in self.hand_rects:
            if card and rect.collidepoint(mouse):
                hovered = card
                break
        card = hovered
        if b.aim and (b.aim.get("stage", 0) > 0 or b.edge_drag):
            card = b.aim["card"]
        if card:
            self.draw_card_detail(screen, card,
                                  pygame.Rect(W - 402, 132, 372, 246))
            return

        msg = b.toast_msg if b.toast_t > 0 else b.room.get("hint", "")
        if b.state == "clear":
            msg = "这一页内存干净了。"
        elif b.state == "dead":
            msg = "进程没了。回滚快照，别停在原地。"
        if not msg:
            return
        x, y = W - 446, 142
        blit_text(screen, "GUIDE", (x, 120), 9, CYAN, mono=True)
        draw_wrap(screen, msg, (x + 2, y + 2), 18, (0, 0, 0), 410, 26)
        h = draw_wrap(screen, msg, (x, y), 18, WHITE, 410, 26)
        pygame.draw.line(screen, dim(CYAN, 0.4), (x - 14, y + 2),
                         (x - 14, y + max(12, h - 6)), 2)

    def draw_card_detail(self, screen, card, rect):
        d = card.d
        panel(screen, rect, (8, 12, 17), dim(card.color, 0.65), 6, alpha=176)
        blit_text(screen, d["cn"] + ("++" if card.up else ""),
                  (rect.x + 14, rect.y + 12), 21,
                  GOLD if card.up else WHITE, bold=True, shadow=2)
        blit_text(screen, d["en"], (rect.right - 14, rect.y + 16), 10,
                  dim(card.color, 0.9), mono=True, anchor="topright")
        blit_text(screen,
                  f"{RARITY_CN[d['rarity']]} · {SHAPE_NAMES[d['shape']]} · 工作 {d['work']}",
                  (rect.x + 14, rect.y + 44), 11, DIM, mono=True)
        y = rect.y + 70
        y += draw_wrap(screen, d["desc"], (rect.x + 14, y), 13, WHITE,
                       rect.w - 28, 18)
        if card.up:
            y += 8
            blit_text(screen, "++", (rect.x + 14, y), 12, GOLD, bold=True)
            draw_wrap(screen, d["up"], (rect.x + 34, y), 12, GOLD,
                      rect.w - 48, 17)
        blit_text(screen,
                  f"目标：{ {'edge':'划一条边','two':'拖两个对象','node':'点一个对象','area':'点一块区域','self':'自己','dead':'自动修复'}[d['target']] }",
                  (rect.x + 14, rect.bottom - 24), 10, DIM2)

    # ------------------------------------------------------------ 过渡与提示

    def draw_banner(self, screen, b):
        if b.banner_t > 0 and b.banner:
            a = int(255 * min(1.0, b.banner_t / 0.5))
            draw_center(screen, b.banner, W // 2, 122, 24, WHITE, a,
                        bold=True)
        if b.state == "clear":
            draw_center(screen, "ROOM CLEARED", W // 2, 300, 52, GREEN, 240,
                        bold=True)
            if b.result:
                draw_center(screen, f"SCORE {b.result.get('score', 0)}",
                            W // 2, 356, 18, WHITE, 220)
        if b.state == "dead":
            draw_center(screen, "SEGFAULT", W // 2, 300, 56, RED, 240,
                        bold=True)
            draw_center(screen, "引用还在，进程没了。", W // 2, 360, 18,
                        DIM, 220)
