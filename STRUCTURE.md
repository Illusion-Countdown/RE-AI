# MEMORY_RUN 当前代码结构

> 2026-11-16 重构后的实际结构。
> 设计目标与分工见 `TEAM_PLAN.md`；本文件只描述“现在代码长什么样”。

---

## 1. 顶层

```text
MEMORY_RUN/
├─ run.py                 启动入口
├─ README.md              玩家/运行说明
├─ TEAM_PLAN.md           分工、依赖、A/B/C/D/Lead 附录
├─ STRUCTURE.md           本文件
├─ requirements.txt
├─ 开始游戏.bat
├─ screenshots/
├─ tools/
└─ memory_run/
```

`run.py` 只导入 `memory_run.app.main()`。
`memory_run/app.py` 是兼容入口，实际实现在 `memory_run/ui/app.py`。

---

## 2. 当前包结构

```text
memory_run/
├─ __init__.py
├─ const.py                    布局 / 配色 / 字体 / 绘制工具
│
├─ core/
│  ├─ __init__.py
│  ├─ model.py                 Node / Edge / Graph / refcount
│  └─ cards.py                 Card / Grid / Hand / Deck / 画质公式
│
├─ content/
│  ├─ __init__.py              内容包统一出口
│  ├─ content.py               兼容聚合入口
│  ├─ bodies.py                3 种身体
│  ├─ avatars.py               4 个 AI 娘
│  ├─ modules.py               14 个模块
│  ├─ boss_rules.py            6 条 Boss 规则
│  ├─ card_defs.py             16 张卡牌定义
│  ├─ rooms.py                 教程 + 5 区 18 战房间数据
│  ├─ pools.py                 分区奖励池 / 模块池
│  └─ progression.py           room_for_step / zone_of / 区域名
│
├─ run/
│  ├─ __init__.py
│  └─ runstate.py              一局远征状态、碎片、商店、卖卡
│
├─ battle/
│  ├─ __init__.py
│  ├─ battle.py                门面：导出 Battle / Projectile / AliasPool
│  ├─ core.py                  Battle 本体：初始化、建房、update、finalize
│  ├─ input.py                 选卡、拖拽、划线 CUT、鼠标/键盘
│  ├─ actions.py               卡牌费用、use_card、apply_card、所有 do_*
│  ├─ gc.py                    伤害、死亡、GC 级联、清房
│  ├─ player.py                玩家移动、工作内存、画质、别名、受击
│  ├─ enemies.py               敌人/Boss/增援波/投射物
│  ├─ entities.py              Projectile / AliasPool
│  └─ constants.py             PLAYER_R / DEFAULT_HP / NODE_COLOR
│
├─ ui/
│  ├─ __init__.py
│  ├─ app.py                   状态机、输入分发、主循环
│  ├─ render.py                渲染门面
│  ├─ render_common.py         卡面/文字/轨迹等公共绘制函数
│  ├─ render_core.py           BattleRenderer：初始化/draw/降质/拖拽残影
│  ├─ render_world.py          战场/引用线/敌人/玩家/refcount
│  ├─ render_hud.py            HUD/网格/房间信息/卡牌详情
│  ├─ render_hand.py           手牌/执行槽/横幅/开场
│  ├─ screens.py               标题/帮助/暂停/奖励/结算/教程
│  ├─ deckui.py                整备/BENCH/升级/卖卡/商店入口
│  └─ fx.py                    屏幕级 FX API
│
├─ platform/
│  ├─ __init__.py
│  └─ audio.py                 程序化音频、F2/F3、静音
│
└─ 兼容 shim（旧导入路径）
   ├─ app.py                   -> ui.app
   ├─ battle.py                -> battle.battle
   ├─ cards.py                 -> core.cards
   ├─ model.py                 -> core.model
   ├─ runstate.py              -> run.runstate
   ├─ render.py                -> ui.render
   ├─ screens.py               -> ui.screens
   ├─ deckui.py                -> ui.deckui
   ├─ fx.py                    -> ui.fx
   └─ audio.py                 -> platform.audio（模块别名）
```

---

## 3. 依赖方向

```text
ui/app.py
 ├─ ui/screens.py
 ├─ ui/deckui.py
 ├─ ui/render.py
 ├─ ui/fx.py
 ├─ battle/battle.py
 ├─ run/runstate.py
 ├─ content/
 └─ platform/audio.py

battle/
 ├─ core/model.py
 ├─ core/cards.py
 ├─ content/
 ├─ run/runstate.py
 └─ platform/audio.py

content/
 ├─ const.py
 └─ core/cards.py（只读 CARD_DEFS）

core/
 └─ const.py
```

约束：

- `battle` 不 import `ui`
- `content` 不 import `battle`
- `ui` 只读 `battle` / `run` 状态
- `platform` 不 import 游戏逻辑
- `const.py` 只由 Lead 改

---

## 4. 文件所有权

| 路径 | Owner | 说明 |
|---|---|---|
| `const.py` | Lead | 冻结 |
| `ui/app.py` | Lead | 状态机 |
| `core/model.py` | B | 引用图 |
| `core/cards.py` | B | 卡牌/网格逻辑 |
| `content/*` | A | 全部内容数据 |
| `run/runstate.py` | A | 经济/推进 |
| `battle/*` | B | 战斗规则 |
| `ui/render.py` | C | 表现 |
| `ui/screens.py` | C | 界面 |
| `ui/deckui.py` | C | 整备/商店 |
| `ui/fx.py` | C | FX |
| `platform/audio.py` | D | 音频 |
| `tools/*` | D | 测试/工具 |

---

## 5. 战斗模块怎么协作

`Battle` 由五个 mixin 组成：

```python
class Battle(InputMixin, ActionsMixin, GcMixin, PlayerMixin, EnemiesMixin):
    ...
```

| 模块 | 负责 | 典型修改 |
|---|---|---|
| `core.py` | 初始化、建房、update、finalize | 新增房间字段、Boss 结算 |
| `input.py` | 选卡、拖拽、划线 | 改 CUT 路径、拖拽手感 |
| `actions.py` | 卡牌动作 | 新卡效果、费用 |
| `gc.py` | 伤害、死亡、GC | 级联规则、清房 |
| `player.py` | 玩家/画质/别名/受击 | 玩家移动、WEAK 承伤 |
| `enemies.py` | 敌人/Boss/增援 | 新敌人、Boss 阶段 |

修改规则：

- 卡牌数据改 `content/card_defs.py`，不改 `actions.py`
- 敌人数据改 `content/rooms.py`，不改 `enemies.py`
- 新敌人行为才改 `enemies.py`
- 新增伤害来源优先走 `gc.apply_damage`
- 不在 `core.update` 里堆具体卡牌逻辑

---

## 6. 兼容层

为了不一次性改所有测试和导入，根目录保留了同名的 shim：

```python
# memory_run/cards.py
from .core.cards import *
```

这意味着：

- 旧代码 `from memory_run.cards import CARD_DEFS` 仍然可用
- 新代码应优先写 `from memory_run.core.cards import ...`
- 新代码内容写 `from memory_run.content.card_defs import CARD_DEFS`
- 不要在新文件里继续依赖 shim

shim 只是迁移期兼容，不是长期架构。

---

## 7. 当前进度

已完成：

- [x] `core/` 拆分
- [x] `content/` 数据拆分
- [x] `run/` 目录
- [x] `battle/` 六模块拆分
- [x] `ui/` 目录
- [x] `ui/render.py` 拆成 common/core/world/hud/hand
- [x] `platform/` 目录
- [x] `tools/run_all.py` 一键回归
- [x] 18 关/教程/界面/拖拽/音频回归通过

下一步（可选）：

- [ ] `ui/screens.py` 再拆 `title/reward/shop/end`
- [ ] `run/runstate.py` 再拆 `shop/rewards/loadout`
- [ ] `content/procgen/` 程序化世界生成

这些不阻塞 4 人并行；当前结构已经可以按 Owner 分工。
