# -*- coding: utf-8 -*-
from .modules import MODULES

# ---------------------------------------------------------------- 奖励池
CARD_POOL_ZONE = {
    1: ["CUT", "LINK", "WEAK", "CLIP", "SWEEP", "WEAKEN", "ALIAS", "ECC"],
    2: ["CUT", "LINK", "WEAK", "CLIP", "SWEEP", "WEAKEN", "ALIAS", "VOID",
        "TRUNC", "DELAY", "REFLECT", "COMPRESS", "ECC", "DOWN"],
    3: ["CUT", "LINK", "WEAK", "CLIP", "SWEEP", "WEAKEN", "ALIAS", "VOID",
        "TRUNC", "DELAY", "REFLECT", "STEAL", "COMPRESS", "ECC", "LOSSY",
        "DOWN"],
    4: ["CUT", "LINK", "WEAK", "CLIP", "SWEEP", "WEAKEN", "ALIAS", "VOID",
        "TRUNC", "DELAY", "REFLECT", "STEAL", "COMPRESS", "ECC", "LOSSY",
        "DOWN"],
    5: ["CUT", "LINK", "WEAK", "CLIP", "SWEEP", "WEAKEN", "ALIAS", "VOID",
        "TRUNC", "DELAY", "REFLECT", "STEAL", "COMPRESS", "ECC", "LOSSY",
        "DOWN"],
}

MODULE_POOL = [m["id"] for m in MODULES]
