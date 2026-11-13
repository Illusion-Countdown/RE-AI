"""一局的元流程：节点、地图、商店、抽卡、升星、revert。"""

from __future__ import annotations

import random
from typing import Any

from core import hex as hx
from core.models import CardDef, MapNodeDef, PieceInstance, RunState


def start_node(run: RunState, node: MapNodeDef, rng: random.Random) -> None:
    run.node = node
    run.layer = node.layer
    run.language = rng.choice(node.language_pool) if node.language_pool else "C"
    ports = sorted(run.active_ports)
    count = 2 if node.layer == 0 else 3
    available = sorted(run.active_ports)
    for port in range(6):
        if len(available) >= count:
            break
        if port not in available:
            available.append(port)
    run.active_ports = set(available[:count])
    run.compute = 4
    run.vram = 6
    run.ai_charge = 0
    run.flags["node_started"] = True
    run.flags["branch_done"] = []


def complete_node(run: RunState, node: MapNodeDef) -> None:
    if node.id not in run.completed:
        run.completed.append(node.id)
    if node.id not in run.path:
        run.path.append(node.id)
    run.flags["node_done"] = True


def add_piece(run: RunState, piece: PieceInstance) -> str:
    for existing in run.bench:
        if existing.definition.id == piece.definition.id and existing.star == piece.star:
            if existing.star < 3:
                existing.star += 1
                if existing.star == 2:
                    existing.max_hp *= 1.6
                    existing.hp = existing.max_hp
                elif existing.star == 3:
                    existing.max_hp *= 2.6
                    existing.hp = existing.max_hp
                return f"{existing.name} 升到 ★{existing.star}"
    if len(run.bench) >= 6:
        run.bench.pop(0)
    run.bench.append(piece)
    return f"获得 {piece.name}"


def expand_memory(run: RunState, sector_index: int, sector_type: str) -> bool:
    cells = hx.sector_cells(sector_index)
    if not cells or any(cell in run.memory for cell in cells):
        return False
    cost = 55 + 25 * max(0, len({c for c, t in run.sector_types.items() if t != "core"}) - 1)
    if run.fragments < cost:
        return False
    run.fragments -= cost
    for cell in cells:
        run.memory.add(cell)
        run.sector_types[cell] = sector_type
    return True


def repair_piece(piece: PieceInstance) -> bool:
    if piece.durability >= 3:
        return False
    piece.durability += 1
    return True


def draft_pool(content: Any, run: RunState, rng: random.Random, count: int = 3) -> list[str]:
    ids = list(content.pieces)
    rng.shuffle(ids)
    picks = ids[:count]
    # 保底：每 3 次抽卡至少一个 6 格（高复杂度）算法
    count_so_far = int(run.flags.get("draft_count", 0))
    if count_so_far >= 2:
        six = [pid for pid in content.pieces if len(content.pieces[pid].shape) >= 6]
        if six:
            picks[-1] = rng.choice(six)
        run.flags["draft_count"] = 0
    else:
        run.flags["draft_count"] = count_so_far + 1
    return picks


def shop_stock(content: Any, rng: random.Random, count: int = 5) -> list[dict[str, Any]]:
    piece_ids = list(content.pieces)
    rng.shuffle(piece_ids)
    card_ids = [cid for cid, card in content.cards.items() if card.unlock == "common"]
    rng.shuffle(card_ids)
    return [
        {"kind": "piece", "id": piece_ids[0], "price": 60},
        {"kind": "piece", "id": piece_ids[1], "price": 60},
        {"kind": "card", "id": card_ids[0], "price": 30},
        {"kind": "card", "id": card_ids[1], "price": 30},
        {"kind": "expand", "id": "expand", "price": 55},
    ][:count]


def map_options(content: Any, layer_index: int) -> list[MapNodeDef]:
    if layer_index < 0 or layer_index >= len(content.layers):
        return []
    return list(content.layers[layer_index].nodes)


def finish_layer(run: RunState) -> bool:
    return run.layer + 1 >= 4
