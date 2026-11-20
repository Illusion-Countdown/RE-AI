# -*- coding: utf-8 -*-
"""战斗时间控制：顿帧与慢放。

只包含确定性逻辑，不依赖 pygame / UI。Battle 只依赖这个窄接口；
FX 继承它，渲染层仍可读取同一个时钟。
"""


class BattleClock:
    __slots__ = ("hitstop", "slow_scale", "slow_t")

    def __init__(self):
        self.hitstop = 0.0
        self.slow_scale = 1.0
        self.slow_t = 0.0

    def add_hitstop(self, t):
        self.hitstop = max(self.hitstop, t)

    def slow(self, scale=0.35, dur=0.45):
        self.slow_scale = scale
        self.slow_t = max(self.slow_t, dur)

    def time_scale(self):
        return self.slow_scale if self.slow_t > 0 else 1.0

    def update(self, dt):
        if self.slow_t > 0:
            self.slow_t = max(0.0, self.slow_t - dt)
            if self.slow_t <= 0:
                self.slow_scale = 1.0
