"""运行时：时间片自动战斗、敌人、指令卡、Boss。"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from core import hex as hx
from core.models import (
    CardDef,
    EnemyInstance,
    MapNodeDef,
    PieceInstance,
    RunState,
)

STALL_CHANCE = {"O(n²)": 0.10, "O(2ⁿ)": 0.18}
COMPLEXITY_INTERVAL = {
    "O(1)": 1.2,
    "O(log n)": 1.5,
    "O(n)": 1.9,
    "O(n log n)": 2.3,
    "O(n²)": 3.0,
    "O(2ⁿ)": 4.2,
}


@dataclass
class Battle:
    run: RunState
    content: Any
    node: MapNodeDef | None = None
    boss_mode: bool = False
    boss_phase: int = 0
    boss_hp: float = 0.0
    boss_max_hp: float = 1.0
    time: float = 0.0
    wave: int = 1
    wave_timer: float = 0.0
    wave_gap: float = 0.0
    wave_duration: float = 25.0
    enemies: list[EnemyInstance] = field(default_factory=list)
    active_ports: set[int] = field(default_factory=lambda: {0, 2})
    done: bool = False
    won: bool = False
    effects: dict[str, float] = field(default_factory=dict)
    ai_ult_timer: float = 0.0
    messages: list[str] = field(default_factory=list)
    boss_phase_timer: float = 0.0
    boss_phase_triggered: set[int] = field(default_factory=set)
    fx_events: list[dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------
    def _fx(self, kind: str, **payload: Any) -> None:
        event = {"kind": kind}
        event.update(payload)
        self.fx_events.append(event)
        if len(self.fx_events) > 160:
            self.fx_events = self.fx_events[-160:]

    def pop_fx(self) -> list[dict[str, Any]]:
        events = self.fx_events
        self.fx_events = []
        return events

    def __post_init__(self) -> None:
        if self.node is not None:
            self.active_ports = set(self.run.active_ports)
        self.wave = 1
        self.wave_timer = 0.0
        self.start_wave()
        if self.boss_mode:
            self.boss_max_hp = max(480.0, float(self.content.boss.total_hp) * 0.2)
            self.boss_hp = self.boss_max_hp
            self.boss_phase = 0
            self.boss_phase_timer = 0.0

    # ------------------------------------------------------------------
    def _msg(self, text: str) -> None:
        self.messages.append(text)
        self.run.add_log(text)
        self.messages = self.messages[-12:]

    def start_wave(self) -> None:
        self.run.compute = min(self.run.max_compute, 4)
        self.run.vram = min(self.run.max_vram, 6)
        self.wave_timer = 0.0
        self.wave_gap = 0.0
        if not self.boss_mode:
            ids = list(self.node.enemy_ids) if self.node else ["bug"]
            if not ids:
                ids = ["bug"]
            count = 2 + self.wave
            for i in range(count):
                eid = ids[i % len(ids)]
                if eid not in self.content.enemies:
                    eid = next(iter(self.content.enemies))
                path = hx.port_path(sorted(self.active_ports)[i % max(1, len(self.active_ports))])
                enemy = EnemyInstance(self.content.enemies[eid], path=path, cell=path[0])
                enemy.hp = enemy.max_hp = enemy.max_hp * (1 + 0.10 * self.run.tech_debt)
                enemy.next_move = 0.5 + i * 0.25
                self.enemies.append(enemy)
            self._msg(f"第 {self.wave} / {self.node.wave_count if self.node else 3} 波：{len(self.enemies)} 个进程")
            self._fx("wave", wave=self.wave, total=(self.node.wave_count if self.node else 3))
        else:
            self._spawn_boss_adds()
            self._fx("boss_start")

    def _spawn_boss_adds(self) -> None:
        port = sorted(self.active_ports)[self.boss_phase % max(1, len(self.active_ports))]
        path = hx.port_path(port)
        for i in range(2 + self.boss_phase):
            eid = "bug" if self.boss_phase < 2 else "cache_miss"
            e = EnemyInstance(self.content.enemies.get(eid, next(iter(self.content.enemies.values()))), path=path, cell=path[0])
            e.next_move = 0.4 + i * 0.3
            self.enemies.append(e)
            self._fx("spawn", cell=e.cell, name=e.definition.name)

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.done:
            return
        dt = min(0.1, max(0.0, float(dt)))
        self.time += dt
        self.wave_timer += dt
        if self.ai_ult_timer > 0:
            self.ai_ult_timer = max(0.0, self.ai_ult_timer - dt)
        for key in list(self.effects):
            self.effects[key] = max(0.0, self.effects[key] - dt)
            if self.effects[key] <= 0:
                self.effects.pop(key, None)

        if self.boss_mode:
            self._update_boss_phases(dt)

        if self.wave_gap > 0:
            self.wave_gap = max(0.0, self.wave_gap - dt)
            if self.wave_gap <= 0:
                self.wave += 1
                self.start_wave()
            return

        self._update_enemies(dt)
        self._update_pieces(dt)
        self._cleanup()

        if not self.boss_mode and self.node and self.wave < self.node.wave_count and not self.enemies:
            self.wave_gap = 3.0
            self._msg("波间 3 秒：可以打牌，也可以提前 commit")
        if not self.boss_mode and self.node and self.wave >= self.node.wave_count and not self.enemies:
            self.done = True
            self.won = True
            self._msg("节点清理完成")
        if self.boss_mode and self.boss_hp <= 0:
            self.done = True
            self.won = True
            self._msg("首领已清除")
        if self.run.core_hp <= 0:
            self.done = True
            self.won = False
            self._msg("推理核心被打穿")

    # ------------------------------------------------------------------
    def _update_enemies(self, dt: float) -> None:
        if self.effects.get("freeze", 0) > 0:
            return
        for enemy in list(self.enemies):
            if enemy.hp <= 0:
                continue
            if "interrupted" in enemy.status:
                continue
            if enemy.definition.special == "leak":
                enemy.hp = min(enemy.max_hp, enemy.hp + 2 * dt)
            if enemy.cell is None:
                continue
            if enemy.next_move > 0:
                enemy.next_move -= dt
                if enemy.next_move > 0:
                    continue
            enemy.next_move = max(0.25, 1.0 / max(0.1, enemy.definition.speed))
            if "slowed" in enemy.status:
                enemy.next_move *= 1.5
            index = enemy.path_index
            next_cell = enemy.path[index + 1] if index + 1 < len(enemy.path) else None
            if next_cell is None:
                self.run.core_hp -= 4
                self._fx("core_hit", amount=4)
                enemy.hp = 0
                continue
            piece = self.piece_at(next_cell)
            if piece is not None:
                self._enemy_attack_piece(enemy, piece)
            elif next_cell in self.run.broken_cells:
                envelope = 1.0
                enemy.cell = next_cell
                enemy.path_index += 1
            else:
                enemy.cell = next_cell
                enemy.path_index += 1
                if next_cell == (0, 0):
                    self.run.core_hp -= 4
                    self._fx("core_hit", amount=4)
                    enemy.hp = 0

    def _enemy_attack_piece(self, enemy: EnemyInstance, piece: PieceInstance) -> None:
        if enemy.next_attack > 0:
            enemy.next_attack -= 0.1
            return
        enemy.next_attack = 1.2
        damage = enemy.definition.damage
        if enemy.definition.special == "segfault":
            damage *= 3
        self.damage_piece(piece, damage, enemy)

    def _update_pieces(self, dt: float) -> None:
        for index, piece in enumerate(list(self.run.pieces)):
            if not piece.alive or piece.stall > 0:
                piece.stall = max(0.0, piece.stall - dt)
                continue
            piece.next_action -= dt
            if piece.next_action > 0:
                continue
            piece.next_action = self.piece_interval(piece)
            self.piece_attack(piece)

    def _cleanup(self) -> None:
        self.enemies = [e for e in self.enemies if e.hp > 0]
        for piece in self.run.pieces:
            if piece.hp <= 0:
                piece.alive = False
        self.run.pieces = [p for p in self.run.pieces if p.alive]

    # ------------------------------------------------------------------
    def piece_interval(self, piece: PieceInstance) -> float:
        base = COMPLEXITY_INTERVAL.get(piece.definition.time_complexity, piece.definition.interval)
        if piece.main_thread:
            base *= 0.65
        if self.ai_ult_timer > 0 and piece.definition.time_complexity in ("O(n²)", "O(2ⁿ)"):
            base *= 0.5
        if piece.state.get("overclock"):
            base *= 0.65
        if "attack_speed" in piece.state:
            base *= 0.8
        if piece.main_thread:
            base *= 0.65
        return max(0.2, base)

    def piece_at(self, cell: tuple[int, int]) -> PieceInstance | None:
        for piece in self.run.pieces:
            if cell in piece.cells:
                return piece
        return None

    def enemies_in_range(self, cell: tuple[int, int], radius: int) -> list[EnemyInstance]:
        return [e for e in self.enemies if e.hp > 0 and e.cell and hx.distance(cell, e.cell) <= radius]

    def choose_target(self, piece: PieceInstance) -> EnemyInstance | None:
        targets = self.enemies_in_range(piece.cells[0], piece.definition.range)
        if not targets:
            return None
        mode = self.run.prompt_mode
        if piece.definition.special == "greedy":
            return min(targets, key=lambda e: e.hp)
        if piece.definition.special == "heap":
            return max(targets, key=lambda e: e.hp)
        if mode == "lowest_hp":
            return min(targets, key=lambda e: e.hp)
        if mode == "core_threat":
            return min(targets, key=lambda e: len(e.path) - e.path_index)
        return min(targets, key=lambda e: hx.distance(piece.cells[0], e.cell or (0, 0)))

    def piece_attack(self, piece: PieceInstance) -> None:
        target = self.choose_target(piece)
        if target is None and not self.boss_mode:
            return
        if target is not None and target.cell is not None:
            self._fx("beam", source=piece.cells[0], target=target.cell, color=(80, 170, 255))
        damage = piece.damage
        if piece.main_thread:
            damage *= 1.4
        if self.in_ai_jurisdiction(piece):
            damage *= 1.2
            self.run.ai_charge = min(100, self.run.ai_charge + int(damage))
        if self.run.language == "C":
            damage *= 1.4
            if random.random() < 0.15 and self.run.pieces:
                victim = random.choice(self.run.pieces)
                self.damage_piece(victim, damage * 0.2)
        if piece.state.get("overclock"):
            damage *= 1.25
        if piece.state.get("damage_buff"):
            damage *= float(piece.state["damage_buff"])
        if any(cell in self.run.traps for cell in piece.cells) and random.random() < 0.2:
            self.damage_piece(piece, damage * 0.2)
            self._msg("野指针：攻击打到了自己人")
            return
        if self.boss_mode:
            self.boss_hp -= damage * 0.55
            self._fx("boss_hit", amount=damage * 0.55, cell=(0, 0))
            if self.boss_hp <= 0:
                self.boss_hp = 0
                self.done = True
                self.won = True
                self._fx("boss_death")
                self._msg("首领已清除：生产环境发布完成")
                return
        if target is None:
            return
        if piece.definition.time_complexity in ("O(n²)", "O(2ⁿ)"):
            chance = STALL_CHANCE.get(piece.definition.time_complexity, 0)
            if "cot" not in self.effects and "no_stall" not in piece.state and self.in_ai_jurisdiction(piece):
                chance = 0.0
            if self.ai_ult_timer > 0:
                chance = 0.0
            if random.random() < chance:
                piece.stall = 1.5
                piece.next_action += 1.5
                return
        self.apply_piece_special(piece, target, damage)

    def apply_piece_special(self, piece: PieceInstance, target: EnemyInstance, damage: float) -> None:
        special = piece.definition.special
        if special == "prune":
            target.status.add("pruned")
            piece.state["prune_count"] = piece.state.get("prune_count", 0) + 1
            return
        if special == "lru":
            piece.state["lru_charge"] = piece.state.get("lru_charge", 0) + 1
            if piece.state["lru_charge"] >= 3:
                piece.state["lru_charge"] = 0
                for friend in self.run.pieces:
                    friend.next_action = min(friend.next_action, 1.0)
            return
        if special == "genetic":
            piece.state["gene"] = piece.state.get("gene", 0) + 1
            if piece.state["gene"] >= 5:
                piece.state["gene"] = 0
                piece.state["damage_buff"] = 1.2
            self.damage_enemy(target, damage * (1 + piece.state.get("gene", 0) * 0.04), piece)
            return
        if special == "merge_sort":
            self.damage_enemy(target, damage, piece)
            if len(self.run.pieces) < 8:
                summon = PieceInstance(piece.definition, star=1, cells=list(piece.cells[:1]), hp=piece.max_hp * 0.4, max_hp=piece.max_hp * 0.4)
                self.run.pieces.append(summon)
            return
        if special == "divide":
            self.damage_enemy(target, damage, piece)
            if len(self.run.pieces) < 8:
                for _ in range(2):
                    summon = PieceInstance(piece.definition, star=1, cells=list(piece.cells[:1]), hp=piece.max_hp * 0.25, max_hp=piece.max_hp * 0.25)
                    self.run.pieces.append(summon)
            return
        if special == "binary_search":
            target.hp -= target.hp * 0.5
        elif special == "hash":
            target.status.add("hashed")
            damage *= 1.2
            self.damage_enemy(target, damage, piece)
        elif special == "bubble":
            self.push_enemy_back(target)
            self.damage_enemy(target, damage, piece)
            piece.state["bubble_stacks"] = piece.state.get("bubble_stacks", 0) + 1
        elif special == "insertion":
            piece.state["growth"] = piece.state.get("growth", 0) + 1
            self.damage_enemy(target, damage, piece)
        elif special == "semaphore":
            target.status.add("interrupted")
            self.damage_enemy(target, damage * 0.5, piece)
        elif special == "monte_carlo":
            self.damage_enemy(target, damage * random.choice([0.5, 1.0, 1.5, 2.0]), piece)
        elif special == "quicksort":
            for enemy in self.enemies_in_range(target.cell or (0, 0), 1):
                self.damage_enemy(enemy, damage * 0.6, piece)
        elif special == "union_find":
            for friend in self.run.pieces:
                if friend is not piece and hx.distance(piece.cells[0], friend.cells[0]) <= 1:
                    friend.state["link"] = 1
            piece.state["link"] = 1
        elif special == "bloom":
            if "bloomed" in target.status:
                if random.random() < 0.5:
                    return
                self.damage_enemy(target, damage, piece)
            else:
                target.status.add("bloomed")
                self.damage_enemy(target, damage * 1.5, piece)
        elif special == "dfs":
            line = self.line_targets(piece, target)
            for enemy in line:
                self.damage_enemy(enemy, damage, piece)
        elif special == "bfs":
            for enemy in self.enemies_in_range(piece.cells[0], 1 + self.wave // 2):
                self.damage_enemy(enemy, damage * 0.8, piece)
        elif special == "topo":
            chain = sorted(self.enemies, key=lambda e: hx.distance(piece.cells[0], e.cell or (0, 0)))[:4]
            for i, enemy in enumerate(chain):
                self.damage_enemy(enemy, damage * (0.85 ** i), piece)
        elif special == "heap":
            self.damage_enemy(target, damage, piece)
            for enemy in self.enemies_in_range(target.cell or (0, 0), 1):
                if enemy is not target:
                    self.damage_enemy(enemy, damage * 0.5, piece)
        elif special == "brute_force":
            for enemy in self.enemies_in_range(piece.cells[0], piece.definition.range):
                self.damage_enemy(enemy, damage, piece)
        elif special == "gradient":
            piece.state["stacks"] = min(30, piece.state.get("stacks", 0) + 1)
            self.damage_enemy(target, damage * (1 + piece.state["stacks"] * 0.03), piece)
        elif special == "backprop":
            self.damage_enemy(target, damage * (1 + piece.state.get("stacks", 0) * 0.04), piece)
        elif special == "dp":
            if piece.state.get("last_target") == target.definition.id:
                piece.state["dp"] = min(5, piece.state.get("dp", 0) + 1)
            else:
                piece.state["dp"] = 0
            piece.state["last_target"] = target.definition.id
            self.damage_enemy(target, damage * (1 + piece.state["dp"] * 0.25), piece)
        elif special == "backtracking":
            self.damage_enemy(target, damage, piece)
            for friend in self.run.pieces:
                friend.hp = min(friend.max_hp, friend.hp + 4)
        elif special == "recursion":
            self.damage_enemy(target, damage, piece)
            if random.random() < 0.2:
                piece.hp -= piece.max_hp * 0.3
        elif special == "mapreduce":
            piece.state["pool"] = piece.state.get("pool", 0) + damage
            self.damage_enemy(target, damage + piece.state["pool"] * 0.2, piece)
        else:
            self.damage_enemy(target, damage, piece)

    def line_targets(self, piece: PieceInstance, target: EnemyInstance) -> list[EnemyInstance]:
        if target.cell is None:
            return [target]
        best = [target]
        for enemy in self.enemies:
            if enemy is target or enemy.cell is None:
                continue
            if hx.distance(piece.cells[0], enemy.cell) <= piece.definition.range:
                best.append(enemy)
            if len(best) >= 3:
                break
        return best

    def push_enemy_back(self, enemy: EnemyInstance) -> None:
        if enemy.path_index > 0:
            enemy.path_index -= 1
            enemy.cell = enemy.path[enemy.path_index]

    def damage_enemy(self, enemy: EnemyInstance, amount: float, piece: PieceInstance | None = None) -> None:
        if enemy.hp <= 0:
            return
        if "interrupted" in enemy.status and enemy.definition.special == "deadloop":
            return
        if enemy.definition.special == "deadloop":
            if "interrupt" not in enemy.status and "reclaimed" not in enemy.status:
                return
        amount = max(0.0, amount)
        enemy.hp -= amount
        self._fx("enemy_hit", cell=enemy.cell, amount=round(amount, 1), damage_type=enemy.definition.fault)
        if piece is not None:
            self.run.ai_charge = min(100, self.run.ai_charge + int(amount * (1 if self.in_ai_jurisdiction(piece) else 0)))
        if enemy.hp <= 0:
            self._fx("enemy_death", cell=enemy.cell, name=enemy.definition.name)
            self.on_enemy_death(enemy)
        elif enemy.definition.special == "race" and "interrupt" not in enemy.status and random.random() < 0.15:
            self.spawn_clone(enemy)

    def spawn_clone(self, enemy: EnemyInstance) -> None:
        if len(self.enemies) > 24:
            return
        clone = EnemyInstance(enemy.definition, path=list(enemy.path), path_index=max(0, enemy.path_index - 1), cell=enemy.cell)
        clone.hp = clone.max_hp = enemy.max_hp * 0.4
        self.enemies.append(clone)
        self._fx("spawn", cell=clone.cell, name=clone.definition.name)

    def on_enemy_death(self, enemy: EnemyInstance) -> None:
        if enemy.definition.special == "null_pointer":
            for piece in self.run.pieces:
                if hx.distance(enemy.cell or (0, 0), piece.cells[0]) <= 1:
                    piece.hp -= 8
            self._fx("explosion", cell=enemy.cell, color=(255, 120, 80))
        if enemy.definition.special == "deadloop":
            enemy.hp = 0
        self.run.fragments += 1

    def damage_piece(self, piece: PieceInstance, amount: float, enemy: EnemyInstance | None = None) -> None:
        for friend in self.run.pieces:
            if friend is piece or "link" not in friend.state:
                continue
            if hx.distance(piece.cells[0], friend.cells[0]) <= 1:
                amount *= 0.7
                break
        piece.hp -= max(0.0, amount)
        self._fx("piece_hit", cells=list(piece.cells), amount=round(amount, 1))
        if piece.hp <= 0:
            piece.alive = False
            self._fx("piece_death", cells=list(piece.cells), name=piece.name)

    def in_ai_jurisdiction(self, piece: PieceInstance) -> bool:
        if self.run.language == "Rust":
            return False
        return any(cell in self.run.jurisdiction for cell in piece.cells)

    def _update_boss_phases(self, dt: float) -> None:
        self.boss_phase_timer += dt
        total = max(1.0, self.boss_max_hp)
        if self.boss_phase == 0 and self.boss_hp <= total * 0.66:
            self.boss_phase = 1
            self._fx("boss_phase", phase=2, name="全量发布")
            self._msg("首领阶段 2 / 全量发布：开始碎内存")
        elif self.boss_phase == 1 and self.boss_hp <= total * 0.33:
            self.boss_phase = 2
            self._fx("boss_phase", phase=3, name="熔断")
            self._msg("首领阶段 3 / 熔断：清空增益，进入伤害检查")
            self.effects.clear()
        if self.boss_phase_timer >= 8:
            self.boss_phase_timer = 0
            if self.boss_phase == 1:
                if self.run.memory:
                    cell = sorted(self.run.memory)[-1]
                    self.run.memory.discard(cell)
                    self.run.broken_cells.add(cell)
                    self._msg(f"内存格 {cell} 被打碎")
            self._spawn_boss_adds()

    # ------------------------------------------------------------------
    def use_card(self, card: CardDef, target: Any = None) -> bool:
        if self.done:
            return False
        if card.cost > self.run.compute:
            self._msg(f"{card.name}: 算力不足")
            return False
        self.run.compute -= card.cost
        effect = card.effect
        if effect == "aoe":
            for enemy in list(self.enemies):
                self.damage_enemy(enemy, float(card.value or 20))
        elif effect == "freeze":
            self.effects["freeze"] = float(card.value or 2)
        elif effect == "slow":
            for enemy in self.enemies:
                enemy.status.add("slowed")
        elif effect == "heal":
            if isinstance(target, PieceInstance):
                target.hp = min(target.max_hp, target.hp + float(card.value or target.max_hp * 0.4))
        elif effect == "damage_buff":
            if isinstance(target, PieceInstance):
                target.state["damage_buff"] = float(card.value or 1.4)
        elif effect == "attack_speed":
            if isinstance(target, PieceInstance):
                target.state["attack_speed"] = 1
        elif effect == "copy":
            if isinstance(target, PieceInstance):
                clone = PieceInstance(
                    target.definition, star=target.star,
                    cells=list(target.cells[:1]),
                    hp=target.max_hp * 0.4, max_hp=target.max_hp * 0.4,
                )
                self.run.pieces.append(clone)
        elif effect == "cooldown_reset":
            if isinstance(target, PieceInstance):
                target.next_action = 0
                target.stall = 0
        elif effect == "control_immunity":
            if isinstance(target, PieceInstance):
                target.state["control_immune"] = 1
        elif effect == "complexity_down":
            if isinstance(target, PieceInstance):
                target.state["complexity_down"] = 1
        elif effect == "banish":
            if isinstance(target, PieceInstance):
                target.state["banished"] = 3.0
        elif effect == "force_action":
            for piece in self.run.pieces:
                piece.next_action = 0
        elif effect == "block_area":
            if target is not None:
                for enemy in self.enemies:
                    if enemy.cell and hx.distance(enemy.cell, target) <= 2:
                        enemy.status.add("interrupted")
        elif effect == "balance_hp":
            if self.run.pieces:
                avg = sum(p.hp for p in self.run.pieces) / len(self.run.pieces)
                for piece in self.run.pieces:
                    piece.hp = avg
        elif effect == "max_hp_shred":
            for enemy in self.enemies:
                enemy.hp -= enemy.max_hp * 0.15
                enemy.max_hp *= 0.85
        elif effect == "draw":
            self.run.hand.extend([card for card in self.content.cards.values() if card.unlock == "common"][:2])
            self.run.hand = self.run.hand[:8]
        elif effect == "cooldown_delay":
            for enemy in self.enemies:
                enemy.next_move += 1.5
        elif effect == "vram_cost_down":
            self.effects["vram_cost_down"] = 8
        elif effect == "reveal":
            self.effects["reveal"] = 10
        elif effect == "action_delay":
            for enemy in self.enemies:
                enemy.status.add("slowed")
        elif effect == "damage_down":
            self.effects["enemy_damage_down"] = 3
        elif effect == "enemy_space":
            for enemy in self.enemies:
                enemy.status.add("slowed")
        elif effect == "merge":
            if isinstance(target, PieceInstance) and self.run.bench:
                target.max_hp += self.run.bench[0].max_hp * 0.5
                target.hp = target.max_hp
                target.definition = target.definition
                self.run.bench.pop(0)
        elif effect == "unsafe_power":
            if isinstance(target, PieceInstance):
                target.state["unsafe_power"] = 1
                target.state["damage_buff"] = 1.8
        elif effect == "no_stall":
            if isinstance(target, PieceInstance):
                target.state["no_stall"] = 1
        elif effect == "range_buff":
            if isinstance(target, PieceInstance):
                target.state["range_buff"] = 2
        elif effect == "kill":
            if not isinstance(target, EnemyInstance):
                candidates = [e for e in self.enemies if e.hp > 0]
                target = max(candidates, key=lambda e: e.hp) if candidates else None
            if isinstance(target, EnemyInstance):
                target.hp = 0
        elif effect == "interrupt":
            if not isinstance(target, EnemyInstance):
                candidates = [e for e in self.enemies if e.hp > 0]
                target = candidates[0] if candidates else None
            if isinstance(target, EnemyInstance):
                target.status.add("interrupt")
                target.status.add("interrupted")
        elif effect == "reclaim":
            if not isinstance(target, EnemyInstance):
                candidates = [e for e in self.enemies if e.definition.handling == "reclaim"]
                target = candidates[0] if candidates else None
            if isinstance(target, EnemyInstance) and target.definition.handling == "reclaim":
                target.hp = 0
        elif effect == "resource":
            self.run.vram = min(self.run.max_vram, self.run.vram + 2)
        elif effect == "cleanse":
            for piece in self.run.pieces:
                piece.state.pop("attack_speed", None)
        elif effect == "shield":
            self.effects["shield"] = float(card.value or 4)
        else:
            self._msg(f"{card.name}: {card.desc or effect}")
        self._msg(f"指令卡 {card.system_call or card.name}")
        self._fx("card", name=card.name, effect=effect, target=getattr(target, "cell", None) if not isinstance(target, PieceInstance) else (target.cells[0] if target.cells else None))
        return True

    def use_ai_ultimate(self) -> bool:
        if self.run.ai_charge < 100:
            self._msg("DeepSeek 充能不足")
            return False
        self.run.ai_charge = 0
        self.ai_ult_timer = 6.0
        self._fx("ultimate", text="CHAIN OF THOUGHT")
        self._msg("DeepSeek 长思考：6 秒不卡顿，高复杂度加速")
        return True
