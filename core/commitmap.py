# -*- coding: utf-8 -*-
"""提交图：这一局走过的路。

只负责"图的结构和查询"，不负责"回退的代价"。
代价在 actions.py。
"""
from dataclasses import dataclass, field

from data import EDGES, NODES


@dataclass
class CommitMap:
    head: str = "c0"
    path: list = field(default_factory=lambda: ["c0"])
    orphans: list = field(default_factory=list)     # 被放弃的节点
    scouted: list = field(default_factory=list)     # 分支侦察过的节点

    # ---------------- 查询 ----------------

    def children(self, node=None) -> list:
        return list(EDGES.get(node or self.head, []))

    def label(self, node) -> str:
        return NODES.get(node, {}).get("label", node)

    def node_type(self, node) -> str:
        return NODES.get(node, {}).get("type", "combat")

    def is_orphan(self, node) -> bool:
        return node in self.orphans

    def can_revert_to(self, node) -> bool:
        """只能退到走过的节点，且不能退到当前节点。"""
        return node in self.path and node != self.head

    # ---------------- 推进 ----------------

    def advance(self, node):
        if node not in self.children():
            raise ValueError(f"{node} 不是 {self.head} 的子节点")
        self.head = node
        self.path.append(node)
        if node in self.orphans:
            self.orphans.remove(node)      # 重走孤儿节点，它就不再是孤儿

    # ---------------- 回退 ----------------

    def revert_to(self, node):
        """回到 node。之后的路径全部丢弃，被丢弃的第一个节点变成孤儿。"""
        if not self.can_revert_to(node):
            raise ValueError(f"没法退到 {node}")

        idx = self.path.index(node)
        dropped = self.path[idx + 1:]
        if dropped:
            self.orphans.append(dropped[0])   # 只记第一个，避免一堆灰点

        self.path = self.path[:idx + 1]
        self.head = node
        return dropped

    # ---------------- 分支 ----------------

    def sibling(self, node):
        """和 node 同父的另一个节点（用来做分支侦察）。"""
        for parent, kids in EDGES.items():
            if node in kids:
                others = [k for k in kids if k != node]
                return others[0] if others else None
        return None

    def mark_scouted(self, node):
        if node not in self.scouted:
            self.scouted.append(node)

    # ---------------- 绘制用 ----------------

    def ascii(self) -> str:
        """把走过的路画成一行，方便命令行演示。"""
        parts = []
        for n in self.path:
            mark = "*" if n == self.head else "o"
            tag = "(孤儿)" if self.is_orphan(n) else ""
            parts.append(f"{mark}{n}{tag}")
        return " → ".join(parts)

    def ascii_branch(self) -> str:
        if not self.scouted:
            return ""
        return " 支线侦察: " + ", ".join(self.scouted)
