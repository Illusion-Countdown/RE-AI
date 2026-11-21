# -*- coding: utf-8 -*-
import math
import random
from memory_run.const import *

class Projectile:
    __slots__ = ("x", "y", "vx", "vy", "r", "dmg", "color", "life", "dead",
                 "necro")

    def __init__(self, x, y, vx, vy, r, dmg, color, life=6.0, necro=False):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.r = r
        self.dmg = dmg
        self.color = color
        self.life = life
        self.dead = False
        self.necro = necro


class AliasPool:
    _next = [1]

    def __init__(self, members, duration=6.0):
        self.gid = AliasPool._next[0]
        AliasPool._next[0] += 1
        self.members = list(members)
        self.max = sum(max(1.0, m.max_hp) for m in members)
        self.hp = sum(max(0.0, m.hp) for m in members)
        self.t = duration
        self.cow_used = False
        for m in members:
            m.alias = self

    def sync(self):
        self.hp = max(0.0, self.hp)
        for m in self.members:
            m.hp = self.hp * (m.max_hp / max(1.0, self.max))

    def alive_members(self):
        return [m for m in self.members if m.alive]

    def clear(self):
        for m in self.members:
            if m.alias is self:
                m.alias = None
