# -*- coding: utf-8 -*-
from .render_deps import *


class HandMixin:
    def draw_hand(self, screen, b):
        cx = W // 2
        cy = H - 122
        cw, ch = 204, 100
        # [选中, 下一张, 上一张] -> 屏幕位置 [中, 右, 左]
        positions = [(cx - cw // 2, cy),
                     (cx + 228 - cw // 2, cy),
                     (cx - 228 - cw // 2, cy)]
        order = b.hand_order()
        for n, ((idx, card), (x, y)) in enumerate(zip(order, positions)):
            rect = pygame.Rect(x, y, cw, ch)
            selected = n == 0 and card is not None
            hover = bool(card) and rect.collidepoint(b.screen_mouse)
            if card is None:
                pygame.draw.rect(screen, (10, 14, 20), rect, border_radius=7)
                pygame.draw.rect(screen, (36, 46, 58), rect, 1,
                                 border_radius=7)
                blit_text(screen, "EMPTY", (rect.centerx, rect.centery), 11,
                          (40, 50, 62), mono=True, anchor="center")
            else:
                draw_card(screen, rect, card.key, card.up,
                          selected=selected, hover=hover)
                if selected:
                    blit_text(screen, "SELECTED", (rect.centerx, rect.y - 14),
                              9, GOLD, mono=True, anchor="midtop", bold=True)
                # 槽位编号放在卡牌上方，避免压住圆角描边
                bx, by = rect.x + 16, rect.y - 14
                pygame.draw.circle(screen, (9, 13, 19), (bx, by), 11)
                pygame.draw.circle(screen, GOLD if selected else DIM2,
                                   (bx, by), 11, 1)
                blit_text(screen, str(idx + 1), (bx, by), 9,
                          WHITE if selected else DIM,
                          mono=True, anchor="center", bold=selected)
            self.hand_rects.append((rect, ("slot", idx), card))

        blit_text(screen, "1 2 3 选牌   ·   C 上一张   ·   SPACE 下一张",
                  (cx, H - 168), 10, DIM, mono=True, anchor="midtop")
        # FOCUS 与冲刺提示：放在右下角，不再占用顶部/左侧
        blit_text(screen, "FOCUS", (W - 238, H - 52), 9, DIM, mono=True)
        bar(screen, pygame.Rect(W - 238, H - 36, 174, 4),
            b.focus / max(1, b.focus_max), PURPLE)
        blit_text(screen, "中键减速   ·   E 冲刺",
                  (W - 24, H - 24), 10, DIM2, mono=True, anchor="topright")
