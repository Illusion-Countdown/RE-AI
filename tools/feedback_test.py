# -*- coding: utf-8 -*-
"""无头验证：事件总线、BattleFx/BattleAudio 接线与旧表现等价性。"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from memory_run import events
from memory_run.app import App
from memory_run.battle.clock import BattleClock
from memory_run.platform import audio

ROOT = Path(__file__).resolve().parent.parent


def test_bus():
    bus = events.EventBus()
    order = []
    h1 = bus.subscribe("TEST_EVENT_A", lambda p: order.append(("a", p["n"])))
    bus.subscribe("TEST_EVENT_A", lambda p: order.append(("b", p["n"])))
    assert bus.emit("TEST_EVENT_A", n=1) == 2
    assert order == [("a", 1), ("b", 1)]
    assert bus.subscriber_count("TEST_EVENT_A") == 2
    assert bus.unsubscribe("TEST_EVENT_A", h1)
    assert bus.emit("TEST_EVENT_A", n=2) == 1
    assert order[-1] == ("b", 2)
    bus.clear()
    assert bus.subscriber_count() == 0
    print("event bus order/remove/clear ok")


def test_clock():
    clock = BattleClock()
    clock.add_hitstop(0.2)
    assert clock.hitstop == 0.2
    clock.slow(0.5, 0.1)
    assert abs(clock.time_scale() - 0.5) < 1e-9
    clock.update(0.2)
    assert clock.time_scale() == 1.0
    assert clock.slow_t == 0.0
    print("battle clock ok")


def test_static_no_direct_feedback():
    for path in (ROOT / "memory_run" / "battle").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "self.fx.add_" not in text, path
        assert "audio.play" not in text, path
        assert "self.fx.add_hitstop" not in text, path
        assert "self.fx.slow" not in text, path
    print("battle has no direct FX/audio calls ok")


def test_wiring_and_effects():
    pygame.init()
    app = App(fullscreen=False, headless=True)
    app.new_run(False)
    app.start_battle()
    b = app.battle
    b.state = "playing"
    b.intro_t = 0
    fx = b.fx

    names = [v for k, v in vars(events).items()
             if k.isupper() and isinstance(v, str) and v.startswith("BATTLE_")]
    missing = [n for n in names if b.bus.subscriber_count(n) == 0]
    assert not missing, f"events without listeners: {missing}"
    assert len(names) >= 50

    # 旧 nope 会生成一条浮动文字
    before = len(fx.floaters)
    b.nope("EVENT TEST")
    assert len(fx.floaters) == before + 1
    assert fx.floaters[-1].text == "EVENT TEST"

    # CUT：spark + parts + flash + shake + cut 音效
    cut_edge = next(e for e in b.graph.edges
                    if e.alive and e.kind != "PARRY")
    before = (len(fx.sparks), len(fx.parts), len(fx.rings), len(fx.floaters))
    calls = []
    original_play = audio.play
    audio.play = lambda name, *a, **k: calls.append(name)
    try:
        assert b.cut_edge(cut_edge)
    finally:
        audio.play = original_play
    assert len(fx.sparks) >= before[0] + 1
    assert len(fx.parts) >= before[1] + 1
    assert "cut" in calls
    assert b.clock.hitstop > 0

    # 每条战斗事件都应有至少一个监听方；新增事件忘了接线会在这里失败
    assert b.bus.subscriber_count() > 50
    print("event wiring, notice and cut effects ok")

    pygame.quit()


def main():
    test_bus()
    test_clock()
    test_static_no_direct_feedback()
    test_wiring_and_effects()
    print("FEEDBACK OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
