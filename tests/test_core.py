from __future__ import annotations

import random
import unittest
from pathlib import Path

from core import hex as hx
from core.battle import Battle
from core.content import Content
from core.models import EnemyInstance, PieceInstance
from core.run import start_node

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = Content(DATA)
        cls.state = cls.content.make_run()
        node = cls.content.layers[0].nodes[0]
        start_node(cls.state, node, random.Random(1))
        cls.battle = Battle(cls.state, cls.content, node)

    def test_content_counts(self) -> None:
        self.assertEqual(len(self.content.pieces), 26)
        self.assertEqual(len(self.content.cards), 32)
        self.assertEqual(len(self.content.enemies), 6)
        self.assertEqual(len(self.content.languages), 2)
        self.assertEqual(len(self.content.layers), 4)

    def test_hex(self) -> None:
        self.assertEqual(len(hx.cells()), 37)
        self.assertEqual([len(hx.sector_cells(i)) for i in range(6)], [2] * 6)
        for cell in hx.cells():
            px, py = hx.hex_to_pixel(cell[0], cell[1], 39, (330, 360))
            self.assertEqual(hx.pixel_to_hex((px, py), 39, (330, 360)), cell)
        for i in range(6):
            path = hx.port_path(i)
            self.assertEqual(len(path), 4)
            self.assertEqual(path[-1], (0, 0))

    def test_all_piece_shapes(self) -> None:
        for piece in self.content.pieces.values():
            self.assertTrue(piece.shape)
            self.assertEqual(len(piece.shape), len(set(piece.shape)))
            for q, r in piece.shape:
                self.assertIn((q, r), hx.cells())

    def test_all_piece_specials_dispatch(self) -> None:
        battle = self.battle
        battle.enemies = [EnemyInstance(self.content.enemies["bug"], path=[(0, 0)], cell=(0, 0))]
        for piece_def in self.content.pieces.values():
            piece = PieceInstance(piece_def, cells=[(0, 0)])
            battle.run.pieces = [piece]
            battle.enemies = [EnemyInstance(self.content.enemies["bug"], path=[(0, 0)], cell=(0, 0))]
            battle.enemies[0].hp = 9999
            battle.piece_attack(piece)

    def test_all_cards_dispatch(self) -> None:
        battle = self.battle
        battle.run.pieces = [PieceInstance(self.content.pieces["greedy"], cells=[(0, 0)])]
        for card in self.content.cards.values():
            battle.run.compute = 99
            target = battle.run.pieces[0] if card.kind == "single" else ((0, 0) if card.kind == "area" else None)
            battle.use_card(card, target)


if __name__ == "__main__":
    unittest.main()
