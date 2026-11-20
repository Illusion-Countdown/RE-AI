# -*- coding: utf-8 -*-
import traceback

from .deps import *

class ActionsMixin:
    def card_work(self, card):
        w = card.d["work"]
        if card.key == "WEAK" and self.run.has("weak_net"):
            w = 0
        if card.up and card.key == "STEAL":
            w = max(0, w - 1)
        return w

    def spend_work(self, card):
        cost = self.card_work(card)
        if cost <= 0:
            return True
        free = max(1, self.deck.grid.free_count())
        if self.work_used + cost > free + 0.001:
            self.nope("工作内存不足：修坏死格、删卡或等它恢复")
            return False
        self.work_used += cost
        return True

    def use_card(self, card, where, target=None):
        if self.state != "playing":
            return False
        if card in self.deck.cards and card.anchor and \
                self.deck.grid.card_corroded(card) and card.key != "ECC":
            self.nope("这张卡被坏死格腐蚀了，先用 ECC 修格")
            return False
        if not self.spend_work(card):
            return False
        try:
            ok = self.apply_card(card, target)
        except Exception as exc:
            # 工具输入异常不能把整局游戏带崩；记录并安全退费
            traceback.print_exc()
            self.work_used = max(0.0, self.work_used - self.card_work(card))
            self.nope("工具执行失败，已安全取消")
            return False
        if not ok:
            # 费用已经付出，但无效目标不该吃掉卡：把工作内存退回
            self.work_used = max(0.0, self.work_used - self.card_work(card))
            return False
        _kind, idx = where
        self.hand.take_slot(idx)
        # 先抽牌：牌堆已空时不补抽；随后再处理这张卡的单次回收
        self.draw_one()
        self.recycle_after_use(card)
        self.normalize_selection()
        self.aim_selected()
        self.edge_drag = None
        self.stats["cards"] += 1
        self.run.stats["cards"] += 1
        self.bus.emit(events.BATTLE_CARD_CAST, card=card,
                      work=self.card_work(card), player=self.player_node)
        return True

    def release_without_target(self, card, where):
        """单剪/横扫等非连接卡：没有有效目标时也允许释放并进入抽牌循环。"""
        if self.state != "playing":
            return False
        if not self.spend_work(card):
            return False
        _kind, idx = where
        self.hand.take_slot(idx)
        self.draw_one()
        self.recycle_after_use(card)
        self.normalize_selection()
        self.aim_selected()
        self.edge_drag = None
        self.stats["cards"] += 1
        self.run.stats["cards"] += 1
        self.bus.emit(events.BATTLE_CARD_RELEASED, card=card,
                      player=self.player_node)
        return True

    def apply_card(self, card, target):
        key = card.key
        up = card.up
        if key == "CUT":
            edges = target if isinstance(target, list) else [target]
            edges = [e for e in edges if e is not None]
            if not edges:
                return False
            n = 2 if up else 1
            cut = 0
            for e in edges[:n]:
                if self.cut_edge(e):
                    cut += 1
            if cut:
                self.bus.emit(events.BATTLE_CUT_RESULT,
                              player=self.player_node, count=cut)
            return cut > 0
        if key == "LINK":
            if not isinstance(target, (list, tuple)) or len(target) < 2:
                return False
            a, b = target[0], target[1]
            return self.do_link(a, b, up)
        if key == "WEAK":
            if not isinstance(target, (list, tuple)) or len(target) < 2:
                return False
            a, b = target[0], target[1]
            return self.do_weak(a, b)
        if key == "CLIP":
            return self.do_clip(target, up)
        if key == "SWEEP":
            return self.do_sweep(target, 5 if up else 3)
        if key == "WEAKEN":
            edges = target if isinstance(target, list) else [target]
            edges = [e for e in edges if e is not None]
            n = 2 if up else 1
            done = 0
            for e in edges[:n]:
                if self.do_weaken_edge(e):
                    done += 1
            return done > 0
        if key == "ALIAS":
            if not isinstance(target, (list, tuple)) or len(target) < 2:
                return False
            a, b = target[0], target[1]
            return self.do_alias(a, b, 8.0 if up else 6.0)
        if key == "VOID":
            if isinstance(target, (list, tuple)):
                target = target[0] if target else None
            return self.do_cast(target, void=True, up=up)
        if key == "TRUNC":
            if isinstance(target, (list, tuple)):
                target = target[0] if target else None
            return self.do_cast(target, void=False, up=up)
        if key == "DELAY":
            edges = target if isinstance(target, list) else [target]
            edges = [e for e in edges if e is not None]
            n = 2 if up else 1
            delay = 2.0 if up else 3.0
            for e in edges[:n]:
                self.pending_cuts.append({"edge": e, "t": delay})
            if edges:
                self.bus.emit(events.BATTLE_DELAY_SET,
                              player=self.player_node, delay=delay)
            return bool(edges)
        if key == "REFLECT":
            e = target[0] if isinstance(target, (list, tuple)) and target else target
            return self.do_reflect(e, 80 if up else 40)
        if key == "STEAL":
            e = target[0] if isinstance(target, (list, tuple)) and target else target
            return self.do_steal(e, up)
        if key == "COMPRESS":
            return self.do_compress(up)
        if key == "ECC":
            return self.do_ecc(2 if up else 1)
        if key == "LOSSY":
            self.explode(target[0], target[1], 180, 120 if up else 80, GOLD)
            added = self.run.add_dead_cells(3 if up else 2)
            if added:
                self.toast(f"有损爆发：永久毁掉 {added} 个空闲格")
            self.bus.emit(events.BATTLE_LOSSY,
                          player=self.player_node, added=added)
            return True
        if key == "DOWN":
            self.slow_t = max(self.slow_t, 7.0 if up else 5.0)
            self.quality_penalty = min(45.0, self.quality_penalty + (15 if up else 20))
            self.toast("降采样：敌人和子弹变慢，画质下降")
            self.bus.emit(events.BATTLE_DOWNSAMPLE, point=target)
            return True
        return False

    # ================================================================ 工具动作

    def cut_edge(self, e):
        if e is None or not e.alive:
            return False
        if e.kind == PARRY:
            return self.parry_melee(e)
        dst = e.dst
        if dst.data.get("cut_immune") and not dst.data.get("cast_stripped"):
            self.nope(f"{dst.name} 拒绝被 CUT：先用 CAST 赋予类型")
            return False
        if dst.data.get("barrier") and not dst.data.get("barrier_used"):
            dst.data["barrier_used"] = True
            self.toast("屏障吸收了这次剪断（每个对象一次）")
            self.bus.emit(events.BATTLE_EDGE_BARRIER, dst=dst)
            return False
        if self.run.has("steal") and e.src is not self.player_node and \
                self.run.rng.random() < 0.30 and dst.alive:
            self.graph.remove_edge(e)
            if not self.graph.between(self.player_node, dst, STRONG):
                self.graph.add_edge(self.player_node, dst, STRONG)
            dst.data["held"] = True
            self.toast("引用窃取：这条边归你了")
        else:
            self.graph.remove_edge(e)
        self.stats["cuts"] += 1
        self.run.stats["cuts"] += 1
        self.clock.add_hitstop(0.018)
        self.bus.emit(events.BATTLE_EDGE_CUT, edge=e, dst=dst)
        self.gc_dirty = True
        if e.src is self.player_node:
            dst.data["held"] = False
        self.resolve_gc()
        return True

    def parry_melee(self, e):
        src = e.src
        self.graph.remove_edge(e)
        if src is not None and src.alive:
            src.data["attack_edge"] = None
            src.data["windup"] = 0.0
            src.stun = max(src.stun, 1.6)
            src.timers["atk"] = max(src.timers.get("atk", 0.0), 1.0)
            self.apply_damage(src, 8, GOLD, source="parry")
        self.work_used = max(0.0, self.work_used - 1.0)
        self.focus = min(self.focus_max, self.focus + 0.6)
        self.stats["cuts"] += 1
        self.stats["parries"] = self.stats.get("parries", 0) + 1
        self.run.stats["cuts"] += 1
        self.clock.add_hitstop(0.05)
        self.clock.slow(0.35, 0.25)
        self.toast("振刀：红色攻击引用被剪断")
        self.bus.emit(events.BATTLE_PARRY, edge=e, src=src,
                      player=self.player_node)
        return True

    def do_link(self, a, b, up=False):
        if a is None or b is None or a is b:
            return False
        if not a.alive or not b.alive:
            return False
        if self.graph.between(a, b, STRONG):
            self.nope("这两个对象之间已经有强引用了")
            return False
        e = self.graph.add_edge(a, b, STRONG)
        if not e:
            return False
        self.stats["links"] += 1
        self.run.stats["links"] += 1
        if a is self.player_node:
            b.data["held"] = True
            self.toast(f"持有 {b.name}：它停火，替你分摊 15% 伤害（每多 1 条 +15%，上限 45%）；不占 refcount")
        self.bus.emit(events.BATTLE_LINK, a=a, b=b,
                      angle=math.atan2(b.y - a.y, b.x - a.x))
        self.gc_dirty = True
        if up:
            self.work_used = max(0.0, self.work_used - 1)
        return True

    def do_weak(self, a, b):
        if a is None or b is None or a is b or not a.alive or not b.alive:
            return False
        strong = self.graph.between(a, b, STRONG)
        weak = self.graph.between(a, b, WEAK)
        if weak:
            self.nope("这里已经有弱引用了")
            return False
        if strong:
            for e in strong:
                e.kind = WEAK
                e.alive = True
            b.data["weak_mark"] = True
            if a is self.player_node:
                b.data["held"] = False
            self.gc_dirty = True
            self.bus.emit(events.BATTLE_WEAK, a=a, b=b,
                          angle=math.atan2(b.y - a.y, b.x - a.x),
                          label="STRONG→WEAK")
            self.resolve_gc()
            return True
        self.graph.add_edge(a, b, WEAK)
        b.data["weak_mark"] = True
        self.bus.emit(events.BATTLE_WEAK, a=a, b=b,
                      angle=math.atan2(b.y - a.y, b.x - a.x),
                      label="ref+1")
        self.gc_dirty = True
        return True

    def do_clip(self, n, up=False):
        if n is None or not n.alive:
            return False
        ins = self.graph.incoming(n, STRONG)
        if not ins:
            self.nope("它没有强引用入边")
            return False
        cut = 0
        for e in list(ins):
            if self.cut_edge(e):
                cut += 1
        if cut and up:
            self.work_used = max(0.0, self.work_used - 1)
        return cut > 0

    def do_sweep(self, point, limit=3):
        def edist(e):
            pts = e.points(12)
            return min(seg_point_dist(point[0], point[1], pts[i][0], pts[i][1],
                                      pts[i + 1][0], pts[i + 1][1])
                       for i in range(len(pts) - 1))
        edges = [e for e in self.graph.edges if e.alive and edist(e) < 155]
        edges.sort(key=edist)
        cut = 0
        for e in edges[:limit]:
            if self.cut_edge(e):
                cut += 1
        if cut:
            self.bus.emit(events.BATTLE_SWEEP, point=point, count=cut)
        return cut > 0

    def do_weaken_edge(self, e):
        if isinstance(e, (list, tuple)):
            e = e[0] if e else None
        if e is None or not e.alive or e.kind != STRONG:
            return False
        e.kind = WEAK
        e.dst.data["weak_mark"] = True
        if e.src is self.player_node:
            e.dst.data["held"] = False
        self.bus.emit(events.BATTLE_WEAKEN_EDGE, edge=e)
        self.gc_dirty = True
        self.resolve_gc()
        return True

    def do_alias(self, a, b, duration):
        if a is None or b is None or a is b or not a.alive or not b.alive:
            return False
        if a.alias or b.alias:
            self.nope("其中一个对象已经在别名组里了")
            return False
        pool = AliasPool([a, b], duration)
        self.aliases.append(pool)
        if a is self.player_node or b is self.player_node:
            self.alias_pool = pool
        mid = ((a.x + b.x) / 2, (a.y + b.y) / 2)
        self.clock.add_hitstop(0.06)
        self.bus.emit(events.BATTLE_ALIAS, a=a, b=b, mid=mid)
        return True

    def do_cast(self, n, void=True, up=False):
        if n is None or not n.alive or n.kind in ("ROOT", "PLAYER"):
            return False
        if n.data.get("boss"):
            self.nope("核心对象不可 CAST")
            return False
        stripped = bool(n.data.get("destructor")) or bool(n.data.get("cut_immune"))
        n.data["cast_stripped"] = True
        n.data["cut_immune"] = False
        n.data["destructor"] = False
        n.data["cast_disable"] = 3.0 if (void and up) else (2.0 if void else 1.0)
        n.stun = max(n.stun, 3.0 if (void and up) else (2.0 if void else 1.0))
        color = WHITE if void else AMBER
        self.clock.add_hitstop(0.02)
        self.bus.emit(events.BATTLE_CAST, node=n, void=void, color=color)
        if not void:
            self.explode(n.x, n.y, 120, 50 if up else 34, AMBER, hit_player=False)
        if stripped:
            self.toast("析构器/类型免疫已被剥离")
        return True

    def do_reflect(self, e, dmg):
        if isinstance(e, (list, tuple)):
            e = e[0] if e else None
        if e is None or not e.alive:
            return False
        pos = (e.dst.x, e.dst.y)
        if not self.cut_edge(e):
            return False
        targets = [n for n in self.graph.hostiles() if n.alive]
        targets.sort(key=lambda n: vdist(n.x, n.y, pos[0], pos[1]))
        if targets:
            self.apply_damage(targets[0], dmg, GOLD, source="reflect")
            self.bus.emit(events.BATTLE_REFLECT, start=pos,
                          end=(targets[0].x, targets[0].y))
        return True

    def do_steal(self, e, up=False):
        if isinstance(e, (list, tuple)):
            e = e[0] if e else None
        if e is None or not e.alive:
            return False
        dst = e.dst
        if dst.data.get("cut_immune") and not dst.data.get("cast_stripped"):
            return False
        if dst.data.get("barrier") and not dst.data.get("barrier_used"):
            dst.data["barrier_used"] = True
            self.nope("屏障吸收了这次窃取")
            return False
        self.graph.remove_edge(e)
        self.graph.add_edge(self.player_node, dst, STRONG)
        dst.data["held"] = True
        if up:
            self.work_used = max(0.0, self.work_used - 1)
        self.toast("引用窃取：它现在归你持有")
        self.bus.emit(events.BATTLE_STEAL, edge=e, dst=dst)
        self.gc_dirty = True
        return True

    def do_compress(self, up=False):
        free = self.deck.grid.free_count()
        if free <= 0:
            self.nope("没有空闲格可以压缩")
            return False
        self.work_used = max(self.work_used, free * (0.9 if not up else 0.95))
        self.compress_t = 12.0 if (up or self.run.has("compressor")) else 8.0
        self.compress_up = bool(up)
        self.toast("压缩：工作内存拉到 90%，伤害提升，画质正在掉")
        self.bus.emit(events.BATTLE_COMPRESS, player=self.player_node)
        return True

    def do_ecc(self, n):
        dead = list(self.deck.grid.dead)
        if not dead:
            self.nope("没有坏死格需要修复")
            return False
        # 优先修脚下的卡，避免把整张卡腐蚀掉
        cards = [c for c in self.deck.grid.all_cards()
                 if c.anchor and any(cell in self.deck.grid.dead for cell in c.cells())]
        cells = []
        if cards:
            for c in cards:
                for cell in c.cells():
                    if cell in self.deck.grid.dead and cell not in cells:
                        cells.append(cell)
        for cell in dead:
            if cell not in cells:
                cells.append(cell)
        fixed = min(n, len(cells))
        for cell in cells[:n]:
            self.deck.grid.dead.discard(cell)
        self.toast(f"纠错码：修复 {fixed} 个坏死格")
        self.bus.emit(events.BATTLE_ECC, player=self.player_node, count=fixed)
        return True

    # ================================================================ 伤害
