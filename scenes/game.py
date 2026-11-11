"""主场景：地图 → 编译 → 运行时 → 抽卡/商店 → Boss → 结算。"""

from __future__ import annotations

import random

import pygame

import settings
from core import hex as hx
from core.battle import Battle
from core.models import CardDef, EnemyInstance, MapNodeDef, PieceInstance, RunState
from core.run import (
    add_piece,
    complete_node,
    draft_pool,
    expand_memory,
    shop_stock,
    start_node,
)
from scenes.base import Scene
from ui.fx import FXManager
from ui.guide import Guide
from ui.hexview import BoardSnapshot, HexView
from ui.widgets import (
    draw_background,
    draw_bar,
    draw_text,
    draw_topbar,
    draw_wrapped_text,
    panel,
)

AREA_NAMES = {
    "inference": "推理区",
    "compile": "编译区",
    "cache": "缓存区",
    "concurrency": "并发区",
    "sandbox": "沙盒区",
}
MODE_NAMES = {
    "map": "选路",
    "compile": "编译期",
    "battle": "运行时",
    "draft": "节点结算",
    "shop": "商店",
    "event": "事件",
    "merge": "合并",
    "result": "结算",
}
NODE_TYPE_NAMES = {
    "battle": "战斗",
    "elite": "精英",
    "shop": "商店",
    "boss": "首领",
    "event": "事件",
}


class GameScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.run: RunState = app.run
        self.rng = random.Random(20261111)
        self.view = HexView()
        self.fx = FXManager(self.view)
        self.guide = Guide()
        self.paused = False
        self.ui_time = 0.0
        self.mode = "map"
        self.node: MapNodeDef | None = None
        self.battle: Battle | None = None
        self.layer = 0
        self.message = ""
        self.message_timer = 0.0
        self.compile_time = 120.0
        self.hover: tuple[int, int] | None = None
        self.hover_node: MapNodeDef | None = None
        self.selected_bench: int | None = None
        self.selected_piece: PieceInstance | None = None
        self.selected_card: CardDef | None = None
        self.paint_jurisdiction = False
        self.branch_nodes: list[MapNodeDef] = []
        self.branch_index = 0
        self.branch_active = False
        self.draft_ids: list[str] = []
        self.shop_items: list[dict] = []
        self.shop_from_map = False
        self.ghost_mode = False
        self.event_options: list[dict] = []
        self.merge_options: list[dict] = []
        self.result_won = False
        self.result_text = ""
        self.pre_battle_pieces: list[PieceInstance] = []
        self._buttons: list[tuple[pygame.Rect, str, str, callable]] = []
        self._map_options: list[MapNodeDef] = []
        self._draw_map_buttons()

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def _say(self, text: str, duration: float = 2.4) -> None:
        self.message = text
        self.message_timer = duration
        self.run.add_log(text)

    def _button(self, rect: pygame.Rect, key: str, label: str, callback) -> None:
        self._buttons.append((rect, key, label, callback))

    def _hit_button(self, pos) -> bool:
        for rect, key, label, callback in self._buttons:
            if rect.collidepoint(pos):
                callback()
                return True
        return False

    def _draw_buttons(self, surface: pygame.Surface) -> None:
        mouse = self.app.to_logical(pygame.mouse.get_pos()) or (-1, -1)
        for rect, key, label, callback in self._buttons:
            hover = rect.collidepoint(mouse)
            panel(surface, rect, fill=settings.PANEL_2, border=settings.BLUE if hover else settings.GRID)
            draw_text(surface, label, 13, settings.WHITE, rect.center, center=True, bold=True)
            if key:
                draw_text(surface, key, 9, settings.MUTED, (rect.right - 5, rect.y + 2))

    def _clear_buttons(self) -> None:
        self._buttons = []

    # ------------------------------------------------------------------
    # 地图
    # ------------------------------------------------------------------
    def _map_layer(self):
        if self.layer >= len(self.app.content.layers):
            return None
        return self.app.content.layers[self.layer]

    @staticmethod
    def _display_title(title: str) -> str:
        return str(title).replace("deploy", "部署")

    @staticmethod
    def _format_rewards(rewards: list[str]) -> str:
        names = {
            "victory": "通关",
            "shop": "商店",
        }
        out = []
        for raw in rewards[:3]:
            if ":" in raw:
                key, _, value = raw.partition(":")
                label = {
                    "fragments": "碎片",
                    "piece_draft": "抽卡",
                    "card_draft": "卡牌",
                    "rare_piece": "稀有棋子",
                    "version_fragment": "版本碎片",
                }.get(key, key)
                out.append(f"{label}+{value}")
            else:
                out.append(names.get(raw, raw))
        return " / ".join(out) or "碎片 / 抽卡"

    def _draw_map_buttons(self) -> None:
        self._clear_buttons()
        layer = self._map_layer()
        if layer is None:
            return
        x = 80 + self.layer * 235
        for index, node in enumerate(layer.nodes):
            rect = pygame.Rect(x, 230 + index * 110, 210, 82)
            self._button(rect, "", node.title, lambda n=node: self._choose_node(n))
        self._button(pygame.Rect(40, 470, 150, 36), "B", "分支", self._branch)
        self._button(pygame.Rect(210, 470, 150, 36), "R", "回退", self._revert)
        self._button(pygame.Rect(380, 470, 150, 36), "S", "商店", self._open_shop)
        self._button(pygame.Rect(550, 470, 110, 36), "V", "事件", self._open_event)
        if self.run.flags.get("orphans"):
            self._button(pygame.Rect(700, 470, 130, 36), "G", "残影", self._enter_ghost)
        self._button(pygame.Rect(850, 470, 100, 36), "?", "帮助", self._show_help)

    def _open_shop(self) -> None:
        self.shop_from_map = True
        self.shop_items = shop_stock(self.app.content, self.rng)
        self.mode = "shop"
        self._say("商店：买完按 Enter 返回地图。")

    def _open_event(self) -> None:
        self.event_options = [
            {"id": "fragments", "title": "领取 60 碎片", "desc": "修复 / 扩容 / 买棋子"},
            {"id": "card", "title": "获得一张随机指令卡", "desc": "加入手牌"},
            {"id": "durability", "title": "修复全部棋子耐久", "desc": "耐久是棋子的命"},
        ]
        self.mode = "event"
        self._say("事件：三选一。")

    def _choose_event(self, option: dict) -> None:
        if option["id"] == "fragments":
            self.run.fragments += 60
        elif option["id"] == "card":
            common = [c for c in self.app.content.cards.values() if c.unlock == "common"]
            if len(self.run.hand) < 8:
                self.run.hand.append(self.rng.choice(common))
        elif option["id"] == "durability":
            for piece in self.run.bench + self.run.pieces:
                piece.durability = 3
        self._say("事件完成：" + option["title"])
        self.mode = "map"
        self._draw_map_buttons()

    def _open_merge(self) -> None:
        self.merge_options = [
            {"id": "fragments", "title": "保留碎片", "desc": "+100 碎片"},
            {"id": "piece", "title": "保留棋子", "desc": "获得一个随机算法"},
        ]
        self.mode = "merge"
        self._say("合并：稀有奖励冲突，二选一。")

    def _enter_ghost(self) -> None:
        orphans = list(self.run.flags.get("orphans", []))
        if not orphans:
            self._say("没有孤儿节点可打。")
            return
        orphan_id = orphans.pop(0)
        self.run.flags["orphans"] = orphans
        ghost = MapNodeDef(
            id="ghost_" + orphan_id,
            type="battle",
            title="孤儿节点 · 残影",
            desc="上一个版本的你，是敌人。",
            language_pool=["C", "Rust"],
            enemy_ids=["bug"],
            wave_count=1,
            layer=self.layer,
        )
        self.ghost_mode = True
        self._choose_node(ghost)
        self.compile_time = 90.0
        self._say(f"残影 {orphan_id}：打穿它，技术债 -1")

    def _choose_merge(self, option: dict) -> None:
        if option["id"] == "fragments":
            self.run.fragments += 100
        else:
            ids = list(self.app.content.pieces)
            self._say(add_piece(self.run, self.app.content.make_piece(self.rng.choice(ids))))
        self.layer += 1
        self.mode = "map"
        self.node = None
        self._draw_map_buttons()

    def _branch(self) -> None:
        layer = self._map_layer()
        if layer is None or len(layer.nodes) < 2 or self.branch_active:
            self._say("当前层不能开分支。")
            return
        if self.run.quota <= 0:
            self._say("额度不足。")
            return
        self.run.quota -= 1
        self.branch_nodes = list(layer.nodes)
        self.branch_index = 0
        self.branch_active = True
        self._say("分支：两条时间线都要打，最后合并。")
        self._choose_node(self.branch_nodes[0])

    def _revert(self) -> None:
        if self.layer <= 0 or self.run.quota <= 0:
            self._say("没有可回退的节点。")
            return
        self.run.quota -= 1
        self.run.tech_debt = min(6, self.run.tech_debt + 1)
        if self.run.completed:
            self.run.completed.pop()
        if self.run.path:
            self.run.path.pop()
        self.layer = max(0, self.layer - 1)
        self.branch_active = False
        self.mode = "map"
        self._draw_map_buttons()
        self._say("回退：回到上一层，技术债 +1")

    def _choose_node(self, node: MapNodeDef) -> None:
        # 未选中的同层节点变成孤儿，之后可以打残影
        if not self.branch_active and node.type != "boss" and not self.ghost_mode:
            layer = self._map_layer()
            if layer:
                for other in layer.nodes:
                    if other.id != node.id and other.id not in self.run.completed:
                        self.run.flags.setdefault("orphans", [])
                        if other.id not in self.run.flags["orphans"]:
                            self.run.flags["orphans"].append(other.id)
        self.node = node
        start_node(self.run, node, self.rng)
        self.fx.clear()
        lang = self.run.languages.get(self.run.language)
        if lang:
            for card_id in lang.special_cards:
                if card_id in self.app.content.cards and all(c.id != card_id for c in self.run.hand):
                    self.run.hand.append(self.app.content.cards[card_id])
        for card_id in ("cot", "long_context"):
            if card_id in self.app.content.cards and all(c.id != card_id for c in self.run.hand):
                self.run.hand.append(self.app.content.cards[card_id])
        self.run.flags["branch_layer"] = self.layer if self.branch_active else None
        self.mode = "shop" if node.type == "shop" else "compile"
        self.compile_time = 120.0
        self.guide.set_step("place")
        self.pre_battle_pieces = [p.clone() for p in self.run.pieces]
        self._clear_buttons()
        if self.mode == "shop":
            self.shop_items = shop_stock(self.app.content, self.rng)
            self._say("商店节点：买完按 ENTER 离开。")
        else:
            if not self.run.pieces:
                self._say("编译期：从交换区把棋子放进内存。")
            else:
                self._say(f"节点：{node.title}  // 环境 {self.run.language}")

    # ------------------------------------------------------------------
    # 编译期
    # ------------------------------------------------------------------
    def _place_selected(self, cell: tuple[int, int]) -> None:
        if self.selected_bench is None or self.selected_bench >= len(self.run.bench):
            return
        piece = self.run.bench[self.selected_bench]
        cells = [(cell[0] + q, cell[1] + r) for q, r in piece.definition.shape]
        if any(c not in hx.cells() for c in cells):
            self._say("形状越界。")
            return
        if any(c not in self.run.memory or c in self.run.broken_cells for c in cells):
            self._say("只能放在已分配内存格。")
            return
        if any(any(c in p.cells for p in self.run.pieces) for c in cells):
            self._say("和已有棋子重叠。")
            return
        piece.cells = cells
        piece.main_thread = (0, 0) in cells
        self.run.pieces.append(piece)
        self.run.bench.pop(self.selected_bench)
        self.selected_bench = None
        self.guide.set_step("jurisdiction")
        self._say(f"部署 {piece.name}" + ("（主线程）" if piece.main_thread else ""))

    def _pick_bench(self, index: int) -> None:
        if 0 <= index < len(self.run.bench):
            self.selected_bench = index
            self.selected_piece = self.run.bench[index]
            self._say(f"选中 {self.selected_piece.name}，点击内存格放置。")

    def _toggle_jurisdiction(self, cell: tuple[int, int]) -> None:
        if cell not in self.run.memory:
            return
        if cell in self.run.jurisdiction:
            self.run.jurisdiction.discard(cell)
        elif len(self.run.jurisdiction) < self.run.ai.context:
            self.run.jurisdiction.add(cell)
            self.run.ai_charge = min(100, self.run.ai_charge)
        self.guide.set_step("run")

    def _expand(self) -> None:
        for index in range(6):
            cells = hx.sector_cells(index)
            if cells and not any(c in self.run.memory for c in cells):
                if expand_memory(self.run, index, "compile"):
                    self.run.jurisdiction.update(cells)
                    self._say("扩容：点亮一个扇区，内存 +2")
                else:
                    self._say("碎片不足，扩容 55 碎片。")
                return
        self._say("没有可扩容的扇区。")

    def _run_battle(self) -> None:
        if not self.run.pieces:
            self._say("至少部署一个棋子。")
            return
        self.selected_card = None
        self.fx.clear()
        self.pre_battle_pieces = [p.clone() for p in self.run.pieces]
        self.battle = Battle(self.run, self.app.content, self.node, boss_mode=self.node.type == "boss")
        self.mode = "battle"
        self.guide.set_step("cards")
        self._clear_buttons()
        self._say("运行 ▶ 运行时开始：棋子自己打。")

    def _return_bench(self, piece: PieceInstance) -> None:
        if piece in self.run.pieces and self.mode == "compile":
            self.run.pieces.remove(piece)
            if len(self.run.bench) < 6:
                self.run.bench.append(piece)
            self._say(f"{piece.name} 撤回交换区。")

    # ------------------------------------------------------------------
    # 战斗
    # ------------------------------------------------------------------
    def _recover_dead(self) -> None:
        for old in self.pre_battle_pieces:
            live = next((p for p in self.run.pieces if p.definition.id == old.definition.id and p.alive), None)
            if live is None:
                old.durability -= 1
                if old.durability > 0:
                    old.hp = old.max_hp
                    old.alive = True
                    old.cells = []
                    if len(self.run.bench) < 6:
                        self.run.bench.append(old)
                else:
                    self._say(f"{old.name} 耐久归零，移除。")

    def _finish_battle(self) -> None:
        battle = self.battle
        if battle is None:
            return
        if battle.won:
            if self.ghost_mode:
                self.ghost_mode = False
                self.run.tech_debt = max(0, self.run.tech_debt - 1)
                self.run.fragments += 40
                self._recover_dead()
                self.mode = "map"
                self.node = None
                self.battle = None
                self._draw_map_buttons()
                self._say("残影清除：技术债 -1，碎片 +40")
                return
            self.run.fragments += 45 if self.node and self.node.type == "battle" else 80
            self._recover_dead()
            if self.node and self.node.layer == 1 and not self.run.flags.get("pre_commit_seen"):
                self.run.flags["pre_commit_seen"] = True
                if self.run.hand:
                    lost = self.run.hand.pop(self.rng.randrange(len(self.run.hand)))
                    self._say(f"提交前钩子：{lost.name} 被消耗")
            complete_node(self.run, self.node)
            if self.node and self.node.type == "boss":
                self.result_won = True
                self.result_text = "v1.0 已部署到生产环境"
                self.mode = "result"
                return
            self.draft_ids = draft_pool(self.app.content, self.run, self.rng)
            self.mode = "draft"
            self._say("节点结算：选择 1 个算法加入交换区。")
            self.battle = None
        else:
            self._recover_dead()
            self.run.quota -= 1
            if self.run.quota < 0:
                self.result_won = False
                self.result_text = "额度耗尽，本局结束"
                self.mode = "result"
            else:
                self.run.core_hp = self.run.max_core_hp
                self.mode = "compile"
                self.battle = None
                self._say("节点失败：花 1 额度重打。")

    def _use_card_target(self, pos) -> None:
        if self.selected_card is None or self.battle is None:
            return
        card = self.selected_card
        target = None
        cell = self.view.cell_at(pos)
        if cell:
            target = self.battle.piece_at(cell)
            if target is None:
                for enemy in self.battle.enemies:
                    if enemy.cell == cell:
                        target = enemy
        if card.kind == "single" and not isinstance(target, PieceInstance):
            self._say("这张卡要拖到一个棋子上。")
            return
        if card.kind == "area" and target is None and cell is None:
            return
        if self.battle.use_card(card, target):
            if card in self.run.hand:
                self.run.hand.remove(card)
            self.selected_card = None
            self.guide.set_step("ultimate")

    # ------------------------------------------------------------------
    # 抽卡 / 商店
    # ------------------------------------------------------------------
    def _draft(self, piece_id: str) -> None:
        piece = self.app.content.make_piece(piece_id)
        self._say(add_piece(self.run, piece))
        self._after_node()

    def _after_node(self) -> None:
        if self.shop_from_map:
            self.shop_from_map = False
            self.mode = "map"
            self._draw_map_buttons()
            return
        if self.branch_active and self.branch_index + 1 < len(self.branch_nodes):
            self.branch_index += 1
            self._choose_node(self.branch_nodes[self.branch_index])
            return
        if self.branch_active:
            self.branch_active = False
            self._open_merge()
            return
        self.layer += 1
        if self.layer >= len(self.app.content.layers):
            self.result_won = True
            self.result_text = "v1.0 已部署"
            self.mode = "result"
            return
        self.mode = "map"
        self.node = None
        self._draw_map_buttons()

    def _buy(self, item: dict) -> None:
        price = int(item["price"])
        if item["kind"] == "expand":
            self._expand()
            return
        if self.run.fragments < price:
            self._say("碎片不足。")
            return
        self.run.fragments -= price
        if item["kind"] == "piece":
            self._say(add_piece(self.run, self.app.content.make_piece(item["id"])))
        elif item["kind"] == "card":
            if len(self.run.hand) < 8:
                self.run.hand.append(self.app.content.cards[item["id"]])
    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_h, pygame.K_F1):
            self.guide.toggle_help()
            return
        if self.guide.help_visible:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_h, pygame.K_F1):
                self.guide.help_visible = False
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_t:
            if self.mode == "map" and self.guide.step == 0:
                self.guide.hide()
            else:
                self.guide.advance()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.selected_card is not None:
                self.selected_card = None
                self._say("已取消选牌。")
                return
            self.paused = not self.paused
            return
        if self.paused:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                self.app.quit()
            return
        if self.mode == "map":
            self._handle_map_event(event)
        elif self.mode == "compile":
            self._handle_compile_event(event)
        elif self.mode == "battle":
            self._handle_battle_event(event)
        elif self.mode == "draft":
            self._handle_draft_event(event)
        elif self.mode == "shop":
            self._handle_shop_event(event)
        elif self.mode == "event":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for index, option in enumerate(self.event_options):
                    if pygame.Rect(300, 240 + index * 80, 680, 60).collidepoint(event.pos):
                        self._choose_event(option)
                        return
        elif self.mode == "merge":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for index, option in enumerate(self.merge_options):
                    if pygame.Rect(350 + index * 300, 300, 260, 180).collidepoint(event.pos):
                        self._choose_merge(option)
                        return
        elif self.mode == "result":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                self.app.start_game()

    def _handle_map_event(self, event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.hover_node = None
            layer = self._map_layer()
            if layer:
                x = 80 + self.layer * 235
                for index, node in enumerate(layer.nodes):
                    if pygame.Rect(x, 230 + index * 110, 210, 82).collidepoint(event.pos):
                        self.hover_node = node
                        break
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hit_button(event.pos):
                return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_b:
                self._branch()
            elif event.key == pygame.K_r:
                self._revert()

    def _handle_compile_event(self, event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.view.cell_at(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hit_button(event.pos):
                return
            cell = self.view.cell_at(event.pos)
            if cell is not None:
                if self.paint_jurisdiction:
                    self._toggle_jurisdiction(cell)
                elif self.selected_bench is not None:
                    self._place_selected(cell)
                else:
                    piece = next((p for p in self.run.pieces if cell in p.cells), None)
                    if piece:
                        self.selected_piece = piece
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_j:
                self.paint_jurisdiction = not self.paint_jurisdiction
                self._say("管辖权画笔：" + ("开" if self.paint_jurisdiction else "关"))
            elif event.key == pygame.K_r:
                self._run_battle()
            elif event.key == pygame.K_m:
                self.mode = "map"
                self._draw_map_buttons()
            elif event.key == pygame.K_x:
                if self.selected_piece:
                    self._return_bench(self.selected_piece)
            elif event.key == pygame.K_o:
                if self.selected_piece:
                    piece = self.selected_piece
                    if id(piece) in self.run.overclocked:
                        self.run.overclocked.discard(id(piece))
                        piece.state.pop("overclock", None)
                        self._say(f"{piece.name} 关闭超频")
                    else:
                        self.run.overclocked.add(id(piece))
                        piece.state["overclock"] = 1
                        piece.max_hp *= 0.85
                        piece.hp = min(piece.hp, piece.max_hp)
                        self._say(f"{piece.name} 超频：攻速 +60%，最大生命 -15%")
            elif pygame.K_1 <= event.key <= pygame.K_6:
                self._pick_bench(event.key - pygame.K_1)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            self._expand()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._run_battle()

    def _handle_battle_event(self, event) -> None:
        if self.battle is None:
            return
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.view.cell_at(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.selected_card = None
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # AI 大招按钮
            if pygame.Rect(1160, 92, 76, 62).collidepoint(event.pos):
                if self.battle.use_ai_ultimate():
                    self.guide.set_step("ultimate")
                return
            if self.selected_card is not None:
                self._use_card_target(event.pos)
                return
            for index, card in enumerate(self.run.hand):
                rect = pygame.Rect(680, 282 + index * 34, 520, 30)
                if rect.collidepoint(event.pos):
                    self.selected_card = card
                    self._say(f"选中卡 {card.name}，点击目标释放。")
                    return

    def _handle_draft_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, piece_id in enumerate(self.draft_ids):
                if pygame.Rect(300 + index * 240, 250, 210, 200).collidepoint(event.pos):
                    self._draft(piece_id)
                    return

    def _handle_shop_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, item in enumerate(self.shop_items):
                if pygame.Rect(250, 180 + index * 68, 780, 54).collidepoint(event.pos):
                    self._buy(item)
                    return
            if pygame.Rect(900, 620, 200, 42).collidepoint(event.pos):
                self._after_node()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._after_node()

    # ------------------------------------------------------------------
    # 更新
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.ui_time += dt
        self.view.update(dt)
        self.guide.update(dt)
        self.fx.update(dt)
        if self.paused or self.guide.help_visible:
            return
        self.message_timer = max(0.0, self.message_timer - dt)
        if self.mode == "compile":
            self.compile_time = max(0.0, self.compile_time - dt)
            if self.compile_time <= 0:
                self._run_battle()
        elif self.mode == "battle" and self.battle is not None:
            self.battle.update(dt)
            self.fx.spawn(self.battle.pop_fx())
            if self.battle.done:
                self._finish_battle()
        elif self.mode == "result":
            pass

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        title = self.node.title if self.node else {
            "map": "提交图", "shop": "商店", "event": "事件", "merge": "合并", "result": "结算"
        }.get(self.mode, "提交图")
        draw_topbar(surface, "RUNTIME 4.0", self._display_title(title), MODE_NAMES.get(self.mode, self.mode))
        if self.mode == "map":
            self._draw_map(surface)
        elif self.mode in ("compile", "battle"):
            board_layer = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            self._draw_board(board_layer)
            offset = self.fx.shake_offset() if self.mode == "battle" else (0, 0)
            surface.blit(board_layer, offset)
            self.fx.draw_world(surface)
            self._draw_side(surface)
            if self.battle:
                self._draw_battle_hud(surface)
            else:
                self._draw_compile_hud(surface)
            self.fx.draw_overlay(surface)
        elif self.mode == "draft":
            self._draw_draft(surface)
        elif self.mode == "shop":
            self._draw_shop(surface)
        elif self.mode == "event":
            self._draw_event(surface)
        elif self.mode == "merge":
            self._draw_merge(surface)
        elif self.mode == "result":
            self._draw_result(surface)
        if self.message_timer > 0 and self.message:
            draw_text(surface, self.message, 13, settings.AMBER,
                      (settings.WIDTH // 2, 700), center=True)
        self._draw_tooltip(surface)
        self.guide.draw_objective(surface, self)
        self.guide.draw_card(surface, self)
        if self.paused:
            self._draw_pause(surface)
        self.guide.draw_help(surface)

    def _snapshot(self) -> BoardSnapshot:
        cells = {}
        for cell in hx.cells():
            port = hx.port_index(cell)
            cells[cell] = {
                "allocated": cell in self.run.memory,
                "sector_type": self.run.sector_types.get(cell),
                "port": port,
                "core": cell == (0, 0),
                "trap": cell in self.run.traps,
                "broken": cell in self.run.broken_cells,
            }
        pieces = [
            {
                "cells": list(p.cells),
                "name": p.name,
                "color": settings.AI_COLOR,
                "hp_ratio": p.hp_ratio,
                "active": p.alive,
                "main_thread": p.main_thread,
                "progress": (
                    max(0.0, min(1.0, 1.0 - p.next_action / max(0.2, self.battle.piece_interval(p))))
                    if self.battle else 1.0
                ),
            }
            for p in self.run.pieces
            if p.alive
        ]
        enemies = []
        if self.battle:
            enemies = [
                {
                    "cell": e.cell,
                    "name": e.definition.name,
                    "hp_ratio": e.hp_ratio,
                    "fault": e.definition.fault,
                    "ghost": e.ghost,
                }
                for e in self.battle.enemies
                if e.hp > 0 and e.cell
            ]
        return BoardSnapshot(
            cells=cells,
            pieces=pieces,
            enemies=enemies,
            jurisdiction=set(self.run.jurisdiction),
            active_ports=set(self.run.active_ports),
        )

    def _draw_board(self, surface: pygame.Surface) -> None:
        deployable = set(self.run.memory) if self.mode == "compile" else None
        self.view.draw(
            surface,
            self._snapshot(),
            hover=self.hover,
            selected_cells=set(self.selected_piece.cells) if self.selected_piece else None,
            range_cells=set(),
            path_cells=None,
            deployable_cells=deployable,
        )

    def _draw_side(self, surface: pygame.Surface) -> None:
        side = pygame.Rect(*settings.SIDE_PANEL)
        panel(surface, side, fill=settings.PANEL)
        run = self.run
        phase = "编译期" if self.mode == "compile" else "运行时"
        draw_text(surface, phase, 18, settings.CYAN if self.mode == "compile" else settings.GREEN,
                  (side.x + 18, side.y + 12), bold=True)
        draw_text(surface, f"· {self._display_title(self.node.title) if self.node else '—'}", 13, settings.TEXT,
                  (side.x + 78, side.y + 16))
        if self.mode == "compile":
            draw_text(surface, f"剩余 {int(self.compile_time)}s", 12,
                      settings.AMBER if self.compile_time < 30 else settings.MUTED,
                      (side.x + 476, side.y + 16))

        # 资源
        draw_text(surface, f"核心 {run.core_hp}/100", 12, settings.GREEN if run.core_hp > 35 else settings.RED,
                  (side.x + 18, side.y + 46))
        draw_bar(surface, pygame.Rect(side.x + 118, side.y + 49, 120, 5), run.core_hp / 100.0,
                 settings.GREEN if run.core_hp > 35 else settings.RED)
        draw_text(surface, f"内存 {len(run.memory)}/19", 12, settings.BLUE, (side.x + 260, side.y + 46))
        draw_text(surface, f"碎片 {run.fragments}", 12, settings.AMBER, (side.x + 360, side.y + 46))
        draw_text(surface, f"额度 {run.quota}", 12, settings.TEXT, (side.x + 470, side.y + 46))
        draw_text(surface, f"算力 {run.compute}/8", 12, settings.CYAN, (side.x + 18, side.y + 68))
        draw_text(surface, f"显存 {run.vram}/12", 12, settings.CYAN, (side.x + 128, side.y + 68))
        draw_text(surface, f"技术债 {run.tech_debt}", 12, settings.RED if run.tech_debt else settings.MUTED,
                  (side.x + 238, side.y + 68))
        lang = run.languages.get(run.language)
        if lang:
            rule = lang.rules[0]["desc"] if lang.rules else ""
            draw_text(surface, f"环境 {run.language} · {rule}", 11, settings.CYAN,
                      (side.x + 18, side.y + 90))

        # DeepSeek
        draw_text(surface, f"DeepSeek-V4  辖区 {len(run.jurisdiction)}/{run.ai.context}", 12,
                  settings.BLUE, (side.x + 18, side.y + 116), bold=True)
        draw_text(surface, "辖区内的棋子 +20% 技能伤害", 10, settings.MUTED,
                  (side.x + 18, side.y + 136))
        pips_x = side.x + 270
        for i in range(12):
            color = settings.BLUE if i < len(run.jurisdiction) else settings.GRID
            pygame.draw.rect(surface, color, (pips_x + i * 17, side.y + 119, 12, 9), border_radius=2)
        draw_text(surface, f"大招充能 {run.ai_charge}/100", 10, settings.CYAN,
                  (side.x + 18, side.y + 154))
        draw_bar(surface, pygame.Rect(side.x + 150, side.y + 157, 390, 5),
                 run.ai_charge / 100.0, settings.CYAN)

        if self.mode == "compile":
            draw_text(surface, "交换区（按 1-6 选择）", 11, settings.MUTED, (side.x + 18, side.y + 178))
            draw_text(surface, "已部署（点棋子看详情）", 11, settings.MUTED, (side.x + 300, side.y + 178))
            y = side.y + 202
            for index, piece in enumerate(run.bench[:6]):
                selected = index == self.selected_bench
                rect = pygame.Rect(side.x + 18, y - 2, 268, 32)
                if selected:
                    pygame.draw.rect(surface, (24, 42, 64), rect, border_radius=5)
                    pygame.draw.rect(surface, settings.AMBER, rect, 1, border_radius=5)
                color = settings.AMBER if selected else settings.TEXT
                draw_text(surface, f"{index+1}. {piece.name}  ★{piece.star}", 11, color, (rect.x + 8, rect.y + 6))
                draw_text(surface, f"{piece.definition.time_complexity} · {len(piece.definition.shape)}格",
                          9, settings.MUTED, (rect.x + 172, rect.y + 8))
                y += 36
            y = side.y + 202
            for piece in run.pieces[:6]:
                draw_text(surface, f"{piece.name}  {int(piece.hp)}/{int(piece.max_hp)}", 11,
                          settings.GREEN if piece.hp_ratio > 0.35 else settings.RED,
                          (side.x + 300, y))
                y += 24
            detail = self.selected_piece
            if detail is None and run.pieces:
                detail = run.pieces[0]
            if detail:
                box = pygame.Rect(side.x + 18, side.y + 414, 540, 112)
                panel(surface, box, fill=(10, 15, 23), border=settings.GRID)
                draw_text(surface, f"{detail.name} · {detail.definition.role or '算法进程'}", 12,
                          settings.WHITE, (box.x + 10, box.y + 8), bold=True)
                draw_text(surface, f"时间 {detail.definition.time_complexity}   空间 {detail.definition.space_complexity}   射程 {detail.definition.range}",
                          10, settings.CYAN, (box.x + 10, box.y + 30))
                draw_wrapped_text(surface, detail.definition.desc, 10, settings.MUTED,
                                  (box.x + 10, box.y + 48), box.width - 20, line_height=14)
                draw_text(surface, "O 超频  ·  X 撤回  ·  J 辖区画笔", 9, settings.AMBER,
                          (box.x + 10, box.y + 94))
        else:
            draw_text(surface, "指令卡（点一张，再点目标）", 11, settings.MUTED,
                      (side.x + 18, side.y + 180))
            y = side.y + 202
            for index, card in enumerate(run.hand[:8]):
                rect = pygame.Rect(side.x + 18, y - 2, 540, 30)
                if card is self.selected_card:
                    pygame.draw.rect(surface, (44, 36, 8), rect, border_radius=4)
                    pygame.draw.rect(surface, settings.AMBER, rect, 1, border_radius=4)
                draw_text(surface, f"{card.name}  ⚡{card.cost}", 11,
                          settings.WHITE if card is self.selected_card else settings.CARD_COLOR,
                          (rect.x + 8, rect.y + 6))
                draw_text(surface, card.desc[:34].replace("Boss", "首领"), 9, settings.MUTED, (rect.x + 180, rect.y + 8))
                y += 34
            if self.selected_card:
                box = pygame.Rect(side.x + 18, side.y + 474, 540, 54)
                panel(surface, box, fill=(10, 15, 23), border=settings.AMBER)
                draw_wrapped_text(surface, self.selected_card.desc.replace("Boss", "首领"), 10, settings.TEXT,
                                  (box.x + 8, box.y + 6), box.width - 16, line_height=14)
                draw_text(surface, "点击目标释放  ·  右键/Esc 取消", 9, settings.MUTED,
                          (box.x + 8, box.y + 36))
        draw_text(surface, "T 引导 · H 手册 · Esc 暂停", 10, settings.MUTED,
                  (side.x + 18, side.y + 540))

    def _draw_compile_hud(self, surface: pygame.Surface) -> None:
        self._clear_buttons()
        self._button(pygame.Rect(660, 610, 160, 36), "R", "开始运行", self._run_battle)
        self._button(pygame.Rect(836, 610, 130, 36), "J", "辖区画笔", lambda: setattr(self, "paint_jurisdiction", not self.paint_jurisdiction))
        self._button(pygame.Rect(982, 610, 110, 36), "E", "扩容", self._expand)
        self._button(pygame.Rect(1108, 610, 110, 36), "M", "地图", self._show_map)
        self._draw_buttons(surface)

    def _draw_battle_hud(self, surface: pygame.Surface) -> None:
        if self.battle is None:
            return
        b = self.battle
        if b.boss_mode:
            draw_text(surface, f"首领战  {int(b.wave_timer)}s", 14,
                      settings.WHITE, (56, 62), bold=True)
        else:
            draw_text(surface, f"第 {b.wave}/{self.node.wave_count if self.node else 3} 波  {int(b.wave_timer)}s", 14,
                      settings.WHITE, (56, 62), bold=True)
        draw_text(surface, f"核心 {self.run.core_hp}/100  ·  算力 {self.run.compute}",
                  12, settings.TEXT, (220, 62))
        if b.boss_mode:
            draw_text(surface, f"首领 {int(b.boss_hp)}/{int(b.boss_max_hp)}  阶段 {b.boss_phase+1}", 11,
                      settings.RED, (430, 62), bold=True)
            draw_bar(surface, pygame.Rect(430, 79, 190, 4), b.boss_hp / max(1.0, b.boss_max_hp), settings.RED)
        if b.ai_ult_timer > 0:
            draw_text(surface, f"长思考 {b.ai_ult_timer:.1f}s", 11, settings.CYAN, (560, 46))
        ai_rect = pygame.Rect(1160, 92, 76, 62)
        pygame.draw.rect(surface, settings.PANEL_2, ai_rect, border_radius=6)
        pygame.draw.rect(surface, settings.CYAN, ai_rect, 1, border_radius=6)
        draw_text(surface, "DS", 15, settings.CYAN, (ai_rect.centerx, ai_rect.y + 16), center=True, bold=True)
        draw_text(surface, "大招", 10, settings.WHITE, (ai_rect.centerx, ai_rect.y + 38), center=True)
        draw_bar(surface, pygame.Rect(ai_rect.x + 4, ai_rect.bottom - 7, ai_rect.width - 8, 4),
                 self.run.ai_charge / 100.0, settings.CYAN)

    def _draw_map(self, surface: pygame.Surface) -> None:
        draw_text(surface, "提交图 // 4 层", 28, settings.WHITE, (70, 100), bold=True)
        draw_text(surface, "前两层二选一；B 开分支；R 回退；节点打完后自动 commit。", 13, settings.MUTED, (72, 140))
        for layer in self.app.content.layers:
            x = 80 + layer.nodes[0].layer * 235
            draw_text(surface, f"L{layer.nodes[0].layer + 1} · {layer.name}", 12, settings.AMBER, (x, 188))
            for index, node in enumerate(layer.nodes):
                y = 230 + index * 110
                rect = pygame.Rect(x, y, 210, 82)
                done = node.id in self.run.completed
                current = node.layer == self.layer
                border = settings.GREEN if done else settings.CYAN if current else settings.GRID
                if current:
                    pulse = 0.55 + 0.45 * abs((self.ui_time * 1.8) % 2.0 - 1.0)
                    glow = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
                    pygame.draw.rect(glow, (59, 130, 246, int(46 * pulse)), rect.inflate(8, 8), border_radius=12)
                    surface.blit(glow, (0, 0))
                panel(surface, rect, fill=settings.PANEL, border=border)
                draw_text(surface, self._display_title(node.title), 15, settings.WHITE if current or done else settings.MUTED,
                          (rect.x + 12, rect.y + 12), bold=True)
                draw_text(surface, f"{NODE_TYPE_NAMES.get(node.type, node.type)} · {node.wave_count} 波",
                          10, settings.MUTED, (rect.x + 12, rect.y + 38))
                lang_text = " / ".join(node.language_pool) if node.language_pool else "随机"
                draw_text(surface, f"环境 {lang_text}", 9, settings.CYAN, (rect.x + 12, rect.y + 54))
                draw_text(surface, "✓" if done else ("← 当前" if current else ""), 11,
                          settings.GREEN if done else settings.CYAN, (rect.x + 120, rect.y + 56))
                if node.id in self.run.flags.get("orphans", []):
                    draw_text(surface, "孤儿", 10, settings.RED, (rect.x + 148, rect.y + 54))
            if layer.nodes:
                x2 = x + 220
                if layer.nodes[0].layer < len(self.app.content.layers) - 1:
                    pygame.draw.line(surface, settings.GRID, (x2, 270), (x2 + 30, 270), 2)
        draw_text(surface, "选择节点：" + " / ".join(n.title for n in self._map_layer().nodes) if self._map_layer() else "",
                  13, settings.TEXT, (72, 440))
        detail = self.hover_node
        if detail is None and self._map_layer() and self._map_layer().nodes:
            detail = self._map_layer().nodes[0]
        if detail:
            info = pygame.Rect(1000, 330, 246, 300)
            panel(surface, info, fill=(11, 17, 26), border=settings.BLUE)
            draw_text(surface, "节点详情", 11, settings.AMBER, (info.x + 16, info.y + 12), bold=True)
            draw_text(surface, self._display_title(detail.title), 18, settings.WHITE, (info.x + 16, info.y + 36), bold=True)
            draw_text(surface, f"{NODE_TYPE_NAMES.get(detail.type, detail.type)} · {detail.wave_count} 波",
                      11, settings.CYAN, (info.x + 16, info.y + 64))
            draw_wrapped_text(surface, detail.desc.replace("Boss", "首领"), 11, settings.TEXT,
                              (info.x + 16, info.y + 90), info.width - 32, line_height=17)
            y = info.y + 160
            draw_text(surface, "环境", 10, settings.MUTED, (info.x + 16, y))
            draw_text(surface, " / ".join(detail.language_pool) or "随机", 11, settings.CYAN, (info.x + 70, y))
            y += 22
            draw_text(surface, "敌人", 10, settings.MUTED, (info.x + 16, y))
            enemy_names = [self.app.content.enemies[eid].name for eid in detail.enemy_ids if eid in self.app.content.enemies]
            draw_text(surface, "、".join(enemy_names[:4]) or "—", 10, settings.RED,
                      (info.x + 70, y))
            y += 22
            draw_text(surface, "奖励", 10, settings.MUTED, (info.x + 16, y))
            draw_text(surface, self._format_rewards(detail.rewards), 10, settings.AMBER,
                      (info.x + 70, y))
            draw_text(surface, "点节点进入 · 悬停查看", 10, settings.MUTED, (info.x + 16, info.bottom - 24))
        self._draw_buttons(surface)

    def _draw_draft(self, surface: pygame.Surface) -> None:
        draw_text(surface, "节点结算 // 三选一", 30, settings.WHITE, (280, 150), bold=True)
        for index, piece_id in enumerate(self.draft_ids):
            piece = self.app.content.pieces[piece_id]
            rect = pygame.Rect(300 + index * 240, 250, 210, 200)
            panel(surface, rect, fill=settings.PANEL_2, border=settings.CYAN)
            draw_text(surface, piece.name, 20, settings.WHITE, (rect.x + 16, rect.y + 18), bold=True)
            draw_text(surface, f"{piece.time_complexity} / {piece.space_complexity}", 11,
                      settings.MUTED, (rect.x + 16, rect.y + 52))
            draw_wrapped_text(surface, piece.desc, 12, settings.TEXT,
                              (rect.x + 16, rect.y + 82), rect.width - 32)
        draw_text(surface, "点击一个算法加入交换区", 13, settings.MUTED, (settings.WIDTH // 2, 510), center=True)

    def _draw_shop(self, surface: pygame.Surface) -> None:
        draw_text(surface, "商店 // 碎片 " + str(self.run.fragments), 28, settings.WHITE, (250, 120), bold=True)
        for index, item in enumerate(self.shop_items):
            rect = pygame.Rect(250, 180 + index * 68, 780, 54)
            panel(surface, rect, fill=settings.PANEL_2, border=settings.GRID)
            name = item["id"]
            if item["kind"] == "piece":
                name = self.app.content.pieces[item["id"]].name
            elif item["kind"] == "card":
                name = self.app.content.cards[item["id"]].name
            else:
                name = "扩容一个扇区"
            draw_text(surface, f"{name}  ·  {item['price']} 碎片", 15, settings.TEXT,
                      (rect.x + 18, rect.y + 16))
            draw_text(surface, {"piece": "算法", "card": "指令卡", "expand": "内存"}.get(item["kind"], item["kind"]),
                      10, settings.MUTED, (rect.right - 80, rect.y + 20))
        draw_text(surface, "点击购买 · Enter 离开商店", 13, settings.MUTED, (settings.WIDTH // 2, 620), center=True)

    def _draw_event(self, surface: pygame.Surface) -> None:
        draw_text(surface, "事件 // 三选一", 30, settings.WHITE, (300, 160), bold=True)
        for index, option in enumerate(self.event_options):
            rect = pygame.Rect(300, 240 + index * 80, 680, 60)
            panel(surface, rect, fill=settings.PANEL_2, border=settings.AMBER)
            draw_text(surface, option["title"], 17, settings.AMBER, (rect.x + 18, rect.y + 10), bold=True)
            draw_text(surface, option["desc"], 12, settings.MUTED, (rect.x + 18, rect.y + 34))

    def _draw_merge(self, surface: pygame.Surface) -> None:
        draw_text(surface, "合并 // 稀有奖励冲突", 30, settings.WHITE, (300, 190), bold=True)
        draw_text(surface, "两条时间线都要留下什么？", 14, settings.MUTED, (302, 228))
        for index, option in enumerate(self.merge_options):
            rect = pygame.Rect(350 + index * 300, 300, 260, 180)
            panel(surface, rect, fill=settings.PANEL_2, border=settings.PURPLE)
            draw_text(surface, option["title"], 20, settings.WHITE, (rect.x + 18, rect.y + 20), bold=True)
            draw_text(surface, option["desc"], 13, settings.MUTED, (rect.x + 18, rect.y + 62))

    def _draw_result(self, surface: pygame.Surface) -> None:
        panel(surface, pygame.Rect(240, 160, 800, 380), fill=settings.PANEL, border=settings.GREEN if self.result_won else settings.RED)
        draw_text(surface, "v1.0" if self.result_won else "构建失败", 54,
                  settings.GREEN if self.result_won else settings.RED, (settings.WIDTH // 2, 250), center=True, bold=True)
        draw_text(surface, self.result_text, 20, settings.WHITE, (settings.WIDTH // 2, 320), center=True)
        draw_text(surface, f"完成节点 {len(self.run.completed)}  ·  技术债 {self.run.tech_debt}  ·  碎片 {self.run.fragments}",
                  13, settings.MUTED, (settings.WIDTH // 2, 370), center=True)
        draw_text(surface, "R 重开一局  ·  Esc 暂停/退出", 15, settings.CYAN, (settings.WIDTH // 2, 470), center=True)

    def _draw_pause(self, surface: pygame.Surface) -> None:
        dim = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 185))
        surface.blit(dim, (0, 0))
        rect = pygame.Rect(430, 230, 420, 260)
        panel(surface, rect, fill=(10, 16, 24), border=settings.CYAN)
        draw_text(surface, "已暂停", 32, settings.WHITE, (rect.centerx, rect.y + 40), center=True, bold=True)
        draw_text(surface, "程序还在跑，但时间片停住了。", 13, settings.MUTED, (rect.centerx, rect.y + 86), center=True)
        draw_text(surface, "Esc  继续", 16, settings.CYAN, (rect.centerx, rect.y + 140), center=True)
        draw_text(surface, "H / F1  调度器手册", 13, settings.TEXT, (rect.centerx, rect.y + 176), center=True)
        draw_text(surface, "Q  退出", 13, settings.RED, (rect.centerx, rect.y + 208), center=True)

    def _draw_tooltip(self, surface: pygame.Surface) -> None:
        if not self.hover or self.mode not in ("compile", "battle"):
            return
        cell = self.hover
        lines = []
        piece = next((p for p in self.run.pieces if cell in p.cells), None)
        enemy = None
        if self.battle:
            enemy = next((e for e in self.battle.enemies if e.hp > 0 and e.cell == cell), None)
        if piece:
            lines = [
                f"算法 · {piece.name}",
                f"时间 {piece.definition.time_complexity} / 空间 {piece.definition.space_complexity}",
                f"生命 {int(piece.hp)}/{int(piece.max_hp)}  射程 {piece.definition.range}",
                f"辖区：{'是（+20% 技能伤害）' if any(c in self.run.jurisdiction for c in piece.cells) else '否'}",
                piece.definition.desc,
            ]
        elif enemy:
            lines = [
                f"敌人 · {enemy.definition.name}",
                f"故障类型：{enemy.definition.fault}",
                f"生命 {int(enemy.hp)}/{int(enemy.max_hp)}  处理：{enemy.definition.handling}",
                enemy.definition.desc,
            ]
        else:
            sector = self.run.sector_types.get(cell)
            if cell == (0, 0):
                lines = ["推理核心", "主线程所在格", "被敌人打穿即失败"]
            elif sector:
                lines = [AREA_NAMES.get(sector, sector), "已分配内存",
                         "DeepSeek 辖区" if cell in self.run.jurisdiction else "未管辖"]
            elif cell in self.run.memory:
                lines = ["已分配内存", "点击可部署棋子", "J 可增删辖区"]
            elif hx.port_index(cell) is not None:
                lines = [f"端口 {hx.port_index(cell)+1}", "敌人从这里进入", "端口不是可部署格"]
            else:
                lines = ["未分配内存", "敌人可以穿过", "按 E 扩容后可用"]
        mx, my = self.view.cell_center(*cell)
        rect = pygame.Rect(min(mx + 28, settings.WIDTH - 300), min(my + 28, settings.HEIGHT - 170), 270, 146)
        panel(surface, rect, fill=(10, 15, 23), border=settings.BLUE)
        y = rect.y + 9
        for index, line in enumerate(lines[:5]):
            color = settings.WHITE if index == 0 else settings.MUTED
            size = 12 if index == 0 else 10
            draw_text(surface, str(line)[:30], size, color, (rect.x + 10, y))
            y += 18 if index == 0 else 16

    def _show_map(self) -> None:
        self.mode = "map"
        self._draw_map_buttons()

    def _show_help(self) -> None:
        self.guide.help_visible = True
