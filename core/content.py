"""读取 data/*.json，构建内容与初始 run。"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from core.hex import ring
from core import hex as hx
from core.models import (
    AIDef,
    BossDef,
    BossPhaseDef,
    CardDef,
    EnemyDef,
    LanguageDef,
    MapLayerDef,
    MapNodeDef,
    PieceDef,
    PieceInstance,
    RunState,
)


class ContentError(Exception):
    pass


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContentError(f"missing {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContentError(f"bad json {path}: {exc}") from exc


def _items(raw: Any, key: str) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        value = raw.get(key, [])
        return value if isinstance(value, list) else []
    return []


class Content:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        raw_pieces = _json(data_dir / "pieces.json")
        raw_cards = _json(data_dir / "cards.json")
        raw_enemies = _json(data_dir / "enemies.json")
        raw_languages = _json(data_dir / "languages.json")
        raw_ai = _json(data_dir / "ai.json")
        raw_map = _json(data_dir / "map.json")
        raw_boss = _json(data_dir / "boss.json")

        self.pieces: dict[str, PieceDef] = {}
        for item in _items(raw_pieces, "pieces"):
            p = PieceDef(
                id=str(item["id"]),
                name=str(item.get("name", item["id"])),
                en=str(item.get("en", "")),
                time_complexity=str(item.get("time_complexity", "O(1)")),
                space_complexity=str(item.get("space_complexity", "O(1)")),
                shape=[(int(a), int(b)) for a, b in item.get("shape", [[0, 0]])],
                hp=int(item.get("hp", 60)),
                damage=int(item.get("damage", 10)),
                interval=float(item.get("interval", 1.2)),
                range=int(item.get("range", 1)),
                method=str(item.get("method", "damage")),
                tags=[str(tag) for tag in item.get("tags", [])],
                role=str(item.get("role", "")),
                desc=str(item.get("desc", "")),
                special=str(item.get("special", "")),
                star3=str(item.get("star3", "")),
            )
            self.pieces[p.id] = p
        self.cards: dict[str, CardDef] = {}
        for item in _items(raw_cards, "cards"):
            c = CardDef(
                id=str(item["id"]),
                name=str(item.get("name", item["id"])),
                system_call=str(item.get("system_call", "")),
                cost=int(item.get("cost", 1)),
                kind=str(item.get("kind", "global")),
                target=str(item.get("target", "")),
                effect=str(item.get("effect", "")),
                value=item.get("value"),
                desc=str(item.get("desc", "")),
                unlock=str(item.get("unlock", "common")),
            )
            self.cards[c.id] = c
        self.enemies: dict[str, EnemyDef] = {}
        for item in _items(raw_enemies, "enemies"):
            e = EnemyDef(
                id=str(item["id"]),
                name=str(item.get("name", item["id"])),
                en=str(item.get("en", "")),
                fault=str(item.get("fault", "data")),
                hp=int(item.get("hp", 32)),
                damage=int(item.get("damage", 5)),
                speed=float(item.get("speed", 1.0)),
                range=int(item.get("range", 1)),
                size=int(item.get("size", 1)),
                special=str(item.get("special", "")),
                desc=str(item.get("desc", "")),
                handling=str(item.get("handling", "damage")),
            )
            self.enemies[e.id] = e
        self.languages: dict[str, LanguageDef] = {}
        for item in _items(raw_languages, "languages"):
            lang = LanguageDef(
                id=str(item["id"]),
                name=str(item.get("name", item["id"])),
                color=tuple(item.get("color", [200, 200, 200])),
                rules=list(item.get("rules", [])),
                counters={str(k): float(v) for k, v in item.get("counters", {}).items()},
                weak={str(k): float(v) for k, v in item.get("weak", {}).items()},
                special_cards=[str(x) for x in item.get("special_cards", [])],
            )
            self.languages[lang.id] = lang
        ai_raw = raw_ai.get("ai", raw_ai)
        self.ai = AIDef(
            id=str(ai_raw.get("id", "deepseek")),
            name=str(ai_raw.get("name", "DeepSeek-V4")),
            context=int(ai_raw.get("context", 12)),
            color=tuple(ai_raw.get("color", [37, 99, 235])),
            passive=list(ai_raw.get("passive", [])),
            ultimate=dict(ai_raw.get("ultimate", {})),
        )
        self.layers: list[MapLayerDef] = []
        for layer_index, layer_raw in enumerate(raw_map.get("layers", [])):
            nodes = []
            for node_raw in layer_raw.get("nodes", []):
                nodes.append(
                    MapNodeDef(
                        id=str(node_raw["id"]),
                        type=str(node_raw.get("type", "battle")),
                        title=str(node_raw.get("title", node_raw["id"])),
                        desc=str(node_raw.get("desc", "")),
                        language_pool=[str(x) for x in node_raw.get("language_pool", [])],
                        enemy_ids=[str(x) for x in node_raw.get("enemy_ids", [])],
                        wave_count=int(node_raw.get("wave_count", 3)),
                        rewards=[str(x) for x in node_raw.get("rewards", [])],
                        next=[str(x) for x in node_raw.get("next", [])],
                        layer=layer_index,
                    )
                )
            self.layers.append(
                MapLayerDef(
                    id=str(layer_raw.get("id", f"l{len(self.layers)+1}")),
                    name=str(layer_raw.get("name", "层")),
                    subtitle=str(layer_raw.get("subtitle", "")),
                    nodes=nodes,
                )
            )
        self.boss = BossDef(
            total_hp=int(raw_boss.get("total_hp", 2400)),
            core_damage=int(raw_boss.get("core_damage", 40)),
            phases=[
                BossPhaseDef(
                    id=str(p["id"]),
                    name=str(p.get("name", p["id"])),
                    hp_ratio=float(p.get("hp_ratio", 1.0)),
                    behavior=str(p.get("behavior", "")),
                    spawns=[str(x) for x in p.get("spawns", [])],
                    desc=str(p.get("desc", "")),
                )
                for p in raw_boss.get("phases", [])
            ],
        )

    # ------------------------------------------------------------------
    def make_piece(self, piece_id: str, star: int = 1) -> PieceInstance:
        if piece_id not in self.pieces:
            raise ContentError(f"unknown piece {piece_id}")
        piece = PieceInstance(self.pieces[piece_id], star=star)
        return piece

    def card(self, card_id: str) -> CardDef:
        return self.cards[card_id]

    def make_run(self, rng: random.Random | None = None) -> RunState:
        rng = rng or random.Random()
        run = RunState(ai=self.ai, languages=dict(self.languages))
        run.memory = {(0, 0), *ring(1)[:4]}
        run.sector_types[(0, 0)] = "core"
        run.jurisdiction = set(run.memory)
        run.traps = {hx.ring(2)[0]}
        run.core_hp = 100
        run.max_core_hp = 100
        starting = ["greedy", "bubble", "monte_carlo"]
        for piece_id in starting:
            if piece_id in self.pieces:
                run.bench.append(self.make_piece(piece_id))
        # 四张基础手牌
        hand_ids = ["mmap", "O2", "SIGUSR1", "SIGSTOP"]
        for cid in hand_ids:
            if cid in self.cards:
                run.hand.append(self.cards[cid])
        run.language = "C"
        run.active_ports = {0, 2}
        return run

    def node_by_id(self, node_id: str) -> MapNodeDef | None:
        for layer in self.layers:
            for node in layer.nodes:
                if node.id == node_id:
                    return node
        return None

    def first_layer(self) -> MapLayerDef | None:
        return self.layers[0] if self.layers else None
