# -*- coding: utf-8 -*-
"""兼容入口：实际实现已迁到 platform.audio。"""
import sys as _sys
from .platform import audio as _audio
_sys.modules[__name__] = _audio
