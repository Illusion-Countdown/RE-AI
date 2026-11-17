# -*- coding: utf-8 -*-
"""Tiny procedural UI sound bank. No external files."""

from __future__ import annotations

import math
from array import array
from pathlib import Path

import pygame


class UIAudio:
    RATE = 44100

    def __init__(self):
        self.enabled = False
        self.sounds = {}
        self.files = {}
        try:
            if pygame.mixer.get_init() is not None:
                pygame.mixer.quit()
            pygame.mixer.init(self.RATE, -16, 1, 512)
            self.enabled = True
            self._build()
        except Exception:
            self.enabled = False

    def _tone(self, notes, wave="square", volume=0.22, release=0.03):
        """notes = [(freq, seconds), ...]"""
        buf = array("h")
        phase = 0.0
        for freq, dur in notes:
            n = max(1, int(self.RATE * dur))
            attack = max(1, int(n * 0.06))
            for i in range(n):
                if freq <= 0:
                    v = 0.0
                else:
                    phase += freq / self.RATE
                    p = phase % 1.0
                    if wave == "square":
                        v = 1.0 if p < 0.5 else -1.0
                    elif wave == "saw":
                        v = p * 2.0 - 1.0
                    else:
                        v = math.sin(p * math.tau)
                env = 1.0
                if i < attack:
                    env = i / attack
                tail = n - i
                if tail < self.RATE * release:
                    env *= max(0.0, tail / (self.RATE * release))
                buf.append(int(v * env * volume * 32767))
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _build(self):
        self.sounds = {
            "pick": self._tone([(520, 0.045), (760, 0.045)], "square", 0.18),
            "place": self._tone([(420, 0.05), (650, 0.08)], "square", 0.22),
            "invalid": self._tone([(180, 0.11), (140, 0.12)], "saw", 0.20),
            "rotate": self._tone([(900, 0.025), (1120, 0.025)], "square", 0.12),
            "open": self._tone([(500, 0.04), (760, 0.05), (1020, 0.06)], "square", 0.14),
            "close": self._tone([(800, 0.035), (520, 0.06)], "square", 0.12),
            "tab": self._tone([(620, 0.04), (840, 0.04)], "square", 0.13),
            "necro": self._tone([(220, 0.08), (160, 0.08), (110, 0.10)], "saw", 0.16),
            "clear": self._tone([(300, 0.05), (460, 0.05), (640, 0.06)], "square", 0.14),
            "repair": self._tone([(520, 0.05), (780, 0.06), (1040, 0.10)], "triangle", 0.16),
            "reset": self._tone([(700, 0.05), (520, 0.05), (360, 0.09)], "saw", 0.15),
            "drop": self._tone([(260, 0.06), (190, 0.08)], "square", 0.16),
        }
        base = Path(__file__).resolve().parent / "assets" / "audio"
        for key, filename in (("necro_card", "necro_card.wav"),
                              ("necro_cell", "necro_cell.wav")):
            path = base / filename
            if path.exists():
                snd = pygame.mixer.Sound(str(path))
                snd.set_volume(0.9)
                self.files[key] = snd

    def play(self, name):
        if not self.enabled:
            return
        snd = self.files.get(name) or self.sounds.get(name)
        if snd is not None:
            snd.play()

    def play_file(self, name):
        self.play(name)
