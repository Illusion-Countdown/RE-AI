# 战斗事件 payload 契约

> 事件名注册在 `memory_run/events.py`；本文只列 payload。
> 事件同步派发，监听方按订阅顺序执行；payload 只读，不要改战斗状态或长期持有。

## 1. 手牌与卡牌动作

| 事件 | payload |
|---|---|
| `BATTLE_DECK_ONLINE` | `player` |
| `BATTLE_DRAW` | `player, card` |
| `BATTLE_CARD_CAST` | `card, work, player` |
| `BATTLE_CARD_RELEASED` | `card, player` |
| `BATTLE_NOTICE` | `player, msg` |
| `BATTLE_CUT_RESULT` | `player, count` |
| `BATTLE_EDGE_CUT` | `edge, dst` |
| `BATTLE_EDGE_BARRIER` | `dst` |
| `BATTLE_PARRY` | `edge, src, player` |
| `BATTLE_LINK` | `a, b, angle` |
| `BATTLE_WEAK` | `a, b, angle, label` |
| `BATTLE_WEAKEN_EDGE` | `edge` |
| `BATTLE_SWEEP` | `point, count` |
| `BATTLE_ALIAS` | `a, b, mid` |
| `BATTLE_CAST` | `node, void, color` |
| `BATTLE_REFLECT` | `start, end` |
| `BATTLE_STEAL` | `edge, dst` |
| `BATTLE_COMPRESS` | `player` |
| `BATTLE_ECC` | `player, count` |
| `BATTLE_DOWNSAMPLE` | `point` |
| `BATTLE_DELAY_SET` | `player, delay` |
| `BATTLE_LOSSY` | `player, added` |

## 2. 伤害、GC 与节点

| 事件 | payload |
|---|---|
| `BATTLE_EXPLODE` | `x, y, radius, color, dud` |
| `BATTLE_DAMAGE` | `node, dmg, color, mode` |
| `BATTLE_NODE_KILLED` | `node, source` |
| `BATTLE_ALIAS_POOL_KILLED` | 无 |
| `BATTLE_SCORE` | `node, score` |
| `BATTLE_LEAK` | `node` |
| `BATTLE_GC_SHOCKWAVE` | `node, radius, color, big` |
| `BATTLE_SHOCK_HIT` | `player, dmg, color, corrupt` |
| `BATTLE_GC_ERASED` | `node` |
| `BATTLE_CASCADE` | `tier, player` |
| `BATTLE_ALIAS_EXPIRED` | `player` |

`BATTLE_DAMAGE.mode`：`normal` / `alias` / `immune` / `shielded`。

`BATTLE_EXPLODE.dud`：`True` 表示只有绿色冲击环和 weak 音效。

`BATTLE_CASCADE.tier`：`3` / `5` / `8`。

`BATTLE_GC_SHOCKWAVE.big`：半径是否超过 360。

`BATTLE_SHOCK_HIT.corrupt`：是否新增了坏死格。

## 3. 敌人

| 事件 | payload |
|---|---|
| `BATTLE_WARD` | `target` |
| `BATTLE_REINFORCEMENT` | `x, y` |
| `BATTLE_MINION_SPAWN` | `x, y` |
| `BATTLE_MELEE_TELEGRAPH` | `node` |
| `BATTLE_MELEE_WINDUP` | `node` |
| `BATTLE_MELEE_HIT` | `node, player` |
| `BATTLE_ENEMY_SHOT` | `node` |
| `BATTLE_CYCLER_LINK` | `node, other` |
| `BATTLE_BOSS_EXPOSED` | `node` |
| `BATTLE_BOSS_RING` | `node` |
| `BATTLE_AUDIT` | `node, corrupted` |
| `BATTLE_BAD_ACCESS` | `player` |

## 4. 玩家与房间

| 事件 | payload |
|---|---|
| `BATTLE_PLAYER_HURT` | `player, dmg, linked, share, mode` |
| `BATTLE_PLAYER_DIED` | `player, reason` |
| `BATTLE_REDUNDANCY` | `player` |
| `BATTLE_DASH` | `player, start, end` |
| `BATTLE_WRITE` | `player, start, end` |
| `BATTLE_WRITE_HIT` | `player, start, end, hit` |
| `BATTLE_FREE_GC` | `player` |
| `BATTLE_NECRO_BOMB` | `player` |
| `BATTLE_DEAD_CODE` | `player` |
| `BATTLE_SLASH_TRAIL` | `pos` |
| `BATTLE_TARGET_PICK` | `node, color` |
| `BATTLE_ROOM_CLEAR` | `player` |

`BATTLE_PLAYER_HURT.mode`：`normal` / `alias`。

`BATTLE_WRITE` 是命中判定前的斩击轨迹；`BATTLE_WRITE_HIT` 是结算后的命中反馈和 `write` 音效。

`BATTLE_PLAYER_DIED.reason`：`hp` / `render` / `necro` / `alias` / `self`。

---

## 5. 谁监听

- 视觉：`memory_run/ui/battle_fx.py` → `FX.add_*`
- 音频：`memory_run/platform/audio_feedback.py` → `audio.play(...)`

新增事件时必须同时更新这两处之一或两处，并在 `tools/feedback_test.py` 的“所有事件都有监听方”检查通过。
