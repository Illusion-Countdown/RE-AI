# -*- coding: utf-8 -*-
from .deps import *

class InputMixin:
    def select_slot(self, i):
        if self.state != "playing" or not 0 <= i < len(self.hand.slots):
            return
        self.drag_active = False
        card = self.hand.slots[i]
        if card is None:
            self.nope("这个手牌槽是空的")
            return
        self.selected = i
        self.aim = {"card": card, "where": ("slot", i), "stage": 0, "src": None}

    def cycle_card(self, delta):
        if self.state != "playing":
            return
        if not any(self.hand.slots):
            self.nope("手牌是空的")
            return
        for step in range(1, len(self.hand.slots) + 1):
            idx = (self.selected + delta * step) % len(self.hand.slots)
            card = self.hand.slots[idx]
            if card is not None:
                self.selected = idx
                self.drag_active = False
                self.aim = {"card": card, "where": ("slot", idx),
                            "stage": 0, "src": None}
                return

    # 拖拽：按住手牌 -> 拖到世界 -> 松开

    def card_in(self, where, idx):
        if where == "slot" and 0 <= idx < len(self.hand.slots):
            return self.hand.slots[idx]
        return None

    def preview_card(self, where, idx):
        card = self.card_in(where, idx)
        if card is None:
            return
        self.selected = idx
        self.aim = {"card": card, "where": (where, idx),
                    "stage": 0, "src": None}
        self.drag_active = True

    def select_where(self, where, idx, immediate=True):
        card = self.card_in(where, idx)
        if card is None:
            self.nope("这张卡已经不在手牌里了")
            return
        self.selected = idx
        self.aim = {"card": card, "where": (where, idx),
                    "stage": 0, "src": None}
        self.drag_active = False
        if immediate and card.d["target"] in ("self", "dead"):
            self.use_card(card, (where, idx))

    def drop_card_at(self, pos):
        """松手落点：按卡的 target 模式结算。"""
        if not self.aim or self.state != "playing":
            return False
        card = self.aim["card"]
        where = self.aim["where"]
        mode = card.d["target"]
        if mode == "edge":
            e = self.edge_at(pos[0], pos[1])
            if e is None:
                return self.release_without_target(card, where)
            return self.use_card(card, where, target=e)
        if mode == "node":
            n = self.node_at(pos[0], pos[1])
            if n is None:
                self.nope("松手处没有对象")
                return False
            return self.use_card(card, where, target=n)
        if mode == "area":
            return self.use_card(card, where, target=pos)
        if mode in ("self", "dead"):
            return self.use_card(card, where)
        if mode == "two":
            n = self.node_at(pos[0], pos[1])
            if n is None:
                self.nope("松手处没有对象")
                return False
            if card.key == "LINK":
                if n is self.player_node:
                    self.nope("LINK 需要一个目标")
                    return False
                return self.use_card(card, where,
                                     target=(self.player_node, n))
            # WEAK / ALIAS：先落第一个目标，再点第二个
            self.aim.update({"stage": 1, "src": n})
            self.toast("已选中第一个目标：再点第二个；右键取消")
            return False
        return False

    def on_key(self, key, mods=0):
        if self.state != "playing":
            return
        if pygame.K_1 <= key <= pygame.K_3:
            self.select_slot(key - pygame.K_1)
        elif key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT):
            self.cycle_card(-1)
        elif key == pygame.K_SPACE:
            self.cycle_card(1)
        elif key == pygame.K_g:
            self.free_gc()
        elif key == pygame.K_r:
            self.necro_bomb()
        elif key == pygame.K_t:
            self.dead_code()

    def free_gc(self):
        if not self.run.has_rule("free_gc") or self.free_gc_used:
            self.nope("没有免费的 GC")
            return
        self.free_gc_used = True
        self.gc_dirty = True
        self.toast("免费 GC：引用归零的对象立即回收")
        self.fx.add_flash(0.18, CYAN, 6)
        self.fx.add_glitch(0.3)

    def necro_bomb(self):
        if not self.run.has("necro_bomb") or self.necro_bomb_used:
            self.nope("没有可用的坏死引爆")
            return
        if not self.deck.grid.dead:
            self.nope("没有坏死格可以引爆")
            return
        self.necro_bomb_used = True
        self.deck.grid.dead.pop()
        self.explode(self.player_node.x, self.player_node.y, 230, 60, MAGENTA)
        self.work_used = max(0.0, self.work_used - 2)
        self.toast("坏死引爆：消耗 1 个坏死格")
        audio.play("boom")

    def dead_code(self):
        if not self.run.has("dead_code") or self.dead_code_used:
            self.nope("没有死代码消除")
            return
        self.dead_code_used = True
        for n in self.graph.hostiles():
            n.stun = max(n.stun, 3.0)
            n.timers["atk"] = max(n.timers["atk"], 3.0)
        self.fx.add_flash(0.2, CYAN, 5)
        self.toast("死代码消除：全场敌人停火 3 秒")
        audio.play("cast")

    def on_mouse_move(self, pos):
        self.mouse = pos
        self.hover_node = self.node_at(*pos)
        self.hover_edge = None if self.hover_node else self.edge_at(*pos)
        if self.edge_drag and self.aim:
            if not self.slash:
                self.slash = [self.edge_drag]
            if vdist(self.slash[-1][0], self.slash[-1][1], pos[0], pos[1]) >= 6:
                self.slash.append(pos)
                if len(self.slash) > 64:
                    self.slash.pop(1)
            self.fx.add_parts(pos[0], pos[1], CYAN, 1, 40, 0.18, 1.2)

    def on_mouse_down(self, pos, button, mods=0):
        self.mouse = pos
        if self.state != "playing":
            return
        if button == 3:
            # 右键仍可 WRITE；只有正在选第二个目标/划边时才用于取消
            if self.aim and (self.aim.get("stage", 0) > 0 or self.edge_drag):
                self.edge_drag = None
                self.slash = []
                self.aim_selected()
                self.toast("已取消目标选择")
            else:
                self.write_attack()
                self.aim_selected()
            return
        if button != 1:
            return
        if not self.aim:
            return
        card = self.aim["card"]
        mode = card.d["target"]
        if mode in ("self", "dead"):
            # 纠错码、压缩等不需要目标：左键点战场任意处直接释放
            return self.use_card(card, self.aim["where"])
        if mode == "two":
            n = self.node_at(*pos)
            if n is None:
                self.nope("需要选中一个对象")
                return
            if self.aim["stage"] == 0:
                self.aim["src"] = n
                self.aim["stage"] = 1
                self.two_drag = pos
                self.fx.add_ring(n.x, n.y, 5, 28, card.color, 0.25, 2)
            else:
                if n is self.aim["src"]:
                    return
                self.use_card(card, self.aim["where"], target=(self.aim["src"], n))
        elif mode == "edge":
            self.edge_drag = pos
            self.slash = [pos]
        elif mode == "node":
            n = self.node_at(*pos)
            if n is not None:
                self.use_card(card, self.aim["where"], target=n)
        elif mode == "area":
            self.use_card(card, self.aim["where"], target=pos)

    def on_mouse_up(self, pos, button, mods=0):
        self.mouse = pos
        if button != 1:
            return
        if self.state != "playing" or not self.aim:
            self.edge_drag = None
            self.two_drag = None
            return
        card = self.aim["card"]
        mode = card.d["target"]
        if mode == "edge" and self.edge_drag:
            a = self.edge_drag
            path = list(self.slash)
            if len(path) < 2 or vdist(path[-1][0], path[-1][1],
                                      pos[0], pos[1]) > 4:
                path.append(pos)
            self.edge_drag = None
            self.slash = []
            edges = self.edges_on_path(path)
            if not edges:
                self.release_without_target(card, self.aim["where"])
                return
            self.use_card(card, self.aim["where"], target=edges)
        elif mode == "two" and self.aim["stage"] == 1 and self.two_drag:
            n = self.node_at(*pos)
            self.two_drag = None
            if n is not None and n is not self.aim["src"]:
                self.use_card(card, self.aim["where"], target=(self.aim["src"], n))

    def edges_on_path(self, path):
        """按“第一次被划到”的顺序返回边；单剪只取第一条。"""
        found = []
        if len(path) < 2:
            return []
        for e in self.graph.edges:
            if not e.alive:
                continue
            first = None
            for i in range(len(path) - 1):
                if e.segment_cross(path[i], path[i + 1]):
                    first = i
                    break
            if first is None:
                for i in range(len(path) - 1):
                    mx = (path[i][0] + path[i + 1][0]) / 2
                    my = (path[i][1] + path[i + 1][1]) / 2
                    if e.hit_test(mx, my, 12):
                        first = i
                        break
            if first is not None:
                found.append((first, e))
        found.sort(key=lambda pair: pair[0])
        return [e for _i, e in found]

    def edges_on_line(self, a, b):
        out = []
        for e in self.graph.edges:
            if not e.alive:
                continue
            if e.segment_cross(a, b) or e.hit_test(b[0], b[1], 16):
                out.append(e)
        out.sort(key=lambda e: vdist(e.src.x, e.src.y, b[0], b[1]))
        return out

    # ================================================================ 用卡
