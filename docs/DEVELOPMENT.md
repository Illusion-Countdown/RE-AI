# 开发与协作

> 一页式入口：代码怎么分层、谁负责什么、怎么提交、怎么测试。
> 当前范围：单人不联机 · 可玩 Alpha。

---

## 1. 当前结构

```text
RE-AI/
├─ memory_run/
│  ├─ core/          Node / Edge / Graph / Card / Grid / Hand
│  ├─ content/       身体、AI 娘、模块、Boss 规则、卡牌、房间、奖励池
│  ├─ run/           远征状态、经济、商店
│  ├─ battle/        core / input / actions / gc / player / enemies
│  ├─ ui/            app / render_* / screens / deckui / fx
│  └─ platform/      程序化音频
├─ tools/            架构、机制、房间、流程、教程、界面、拖拽、音频测试
├─ docs/             本目录
├─ screenshots/
├─ run.py
├─ gameStart.bat
└─ requirements.txt
```

兼容 shim：

```text
memory_run/app.py      -> ui.app
memory_run/battle.py   -> battle.battle
memory_run/cards.py    -> core.cards
memory_run/model.py    -> core.model
memory_run/runstate.py -> run.runstate
memory_run/render.py   -> ui.render
memory_run/screens.py  -> ui.screens
memory_run/deckui.py   -> ui.deckui
memory_run/fx.py       -> ui.fx
memory_run/audio.py    -> platform.audio
```

新代码优先使用新路径；旧 shim 只用于兼容。

---

## 2. 分层规则

```text
ui/app.py
 ├─ ui/screens.py
 ├─ ui/deckui.py
 ├─ ui/render*.py
 ├─ ui/fx.py
 ├─ battle/battle.py
 ├─ run/runstate.py
 ├─ content/
 └─ platform/audio.py
```

约束：

- `battle` 不 import `ui`
- `content` 不 import `battle` / `ui`
- `ui` 只读 `battle` / `run` 状态
- `platform` 不 import 游戏逻辑
- `const.py` 只由维护者改
- 不在 `draw()` 里推进游戏状态

检查：

```powershell
python tools/architecture_test.py
```

---

## 3. 文件所有权

| 路径 | Owner | 内容 |
|---|---|---|
| `run.py` / `const.py` / `ui/app.py` | Lead | 入口、布局、状态机 |
| `core/model.py` / `core/cards.py` | B | 引用图、卡牌、网格 |
| `content/*` | A | 卡牌、敌人、房间、模块、奖励 |
| `run/runstate.py` | A | 远征、经济、商店 |
| `battle/*` | B | 卡牌动作、GC、敌人、Boss |
| `ui/render*.py` | C | 战场、HUD、卡面、低画质 |
| `ui/screens.py` / `ui/deckui.py` | C | 界面、整备、商店 |
| `ui/fx.py` | C | 屏幕 FX |
| `platform/audio.py` | D | 音频、设备切换 |
| `memory_run/events.py` | 公共注册表 | 任何人可加事件名；Lead 只审格式/重复 |
| `tools/*` | D | 测试、回归、性能 |
| `docs/*` | D 汇总 | Owner 提供内容 |

默认不改别人的目录。必须改时先和 Owner 确认。

---

## 4. 分工

| 角色 | 负责 | 不看 |
|---|---|---|
| **A 内容与数值** | 卡牌、敌人、房间、模块、Boss 规则、商店、碎片、平衡、程序化生成 | 战斗实现、UI 绘制 |
| **B 战斗与 AI** | 引用图、GC、卡牌动作、敌人、Boss、增援、可打性校验 | 内容数据、UI |
| **C UI 与表现** | 渲染、HUD、整备、商店、拖拽、CUT 划线、FX、截图 | 战斗数值、内容表 |
| **D 平台与 QA** | 音频、崩溃、测试、性能、CI、发布、文档汇总 | 玩法逻辑、UI 布局 |
| **Lead** | 接口、`app.py`、`const.py`、合并、版本、验收 | 不替队友写整块 |

协作 Issue 规则见 [`COLLABORATION.md`](COLLABORATION.md)：

- 多角色需求：父 Issue + A/B/C/D 子 Issue
- 父 Issue 只放子 Issue 链接和 Owner，不 @队友
- 子 Issue 用 Assignee 通知；一个子 Issue 一个 Owner、一个目录、一个 PR
- 只在公共接口、事件总线、跨 Owner 决策时 `@lead`；事件名按 [`EVENT_NAMING.md`](EVENT_NAMING.md) 自助注册

---

## 5. 依赖

```text
Lead 冻结接口
  → B 保持 Battle 门面稳定
    → A 继续加内容
      → C 接只读状态做表现
        → D 跑全量回归
          → A 接程序化生成
```

硬依赖：

| 需要 | 提供方 | 交付 |
|---|---|---|
| A 的世界生成 | B | `validate_encounter()` |
| B 的战斗解耦 | A | Room/Enemy/Card schema |
| C 的 HUD | B | Battle 只读字段 / 事件 |
| B/C 的音效 | D | `audio.play()` / 注册表 |
| A 的平衡 | D | 种子 CSV / 回归 |
| 所有合并 | D | `run_all.py` 全绿 |

关键路径只有三个阻塞点：

1. Lead 的接口冻结
2. B 的 Battle 门面
3. D 的一键回归

---

## 6. 接口

### Battle 只读

```python
battle.graph
battle.player_node
battle.projectiles
battle.time
battle.state
battle.quality
battle.quality_band()
battle.deck
```

UI 不能直接改 `node.hp`、`edge.kind`、`graph.nodes`。

### Battle 命令

```python
battle.update(dt, input_state)
battle.on_mouse_down(pos, button, mods)
battle.on_mouse_move(pos)
battle.on_mouse_up(pos, button, mods)
battle.select_slot(i)
battle.select_reserve(i)
battle.select_overflow(i)
battle.drop_card_at(pos)
battle.use_card(card, where, target=None)
```

### 内容 schema

```python
RoomDef(code, title, cn, zone, danger, nodes, edges, boss=False, intro="", hint="")
NodeDef(id, kind, pos, name=None, hp=None, **data)
EdgeDef(src, dst, kind=STRONG)
CardDef(key, cn, shape, target, work, rarity, desc, up)
```

### RunState

```python
run.shards
run.hp
run.deck
run.room
run.zone
run.zone_name
run.make_card_rewards(...)
run.make_shop_items(...)
run.buy_shop_item(item)
run.sell_card(card)
run.repair_dead(n, cost_per)
run.advance()
```

### FX / Audio

```python
fx.add_flash(...); fx.add_shake(...); fx.add_parts(...)
fx.add_ring(...); fx.add_text(...)

audio.play(name, vol=1.0, gap=0.045)
audio.toggle_mute()
audio.next_device()
```

音效名必须先注册在 `platform/audio.py`。

### 事件 / Events

事件名注册表：

```text
memory_run/events.py
```

规则见 [`EVENT_NAMING.md`](EVENT_NAMING.md)：

- 格式 `DOMAIN_ACTION[_STATE]`，全大写，2–5 段
- 常量名与字符串值完全一致
- 同一个 PR 里注册并使用，不预埋空事件
- 业务模块只使用 `events.XXX`，不写裸字符串
- 当前还没有事件总线，注册表暂时为空；第一个跨层事件再按规范接线

检查：

```powershell
python tools/events_test.py
```

---

## 7. 提交与 PR

分支：

```text
feat/<name>
fix/<name>
docs/<name>
refactor/<name>
test/<name>
```

提交信息示例：

```text
feat: 新增回滚卡
fix: 修复 WARD 计时器
docs: 合并开发文档
refactor: 拆分 render
test: 增加 ECC 回归
```

提交前：

```powershell
python tools/run_all.py
```

PR 必须写：

- 改了什么
- 为什么
- 事件契约（没有写“无”）
- 怎么测
- 影响哪些文件
- 关联 Issue，以及 `Parent: #父`（单点需求写 `Parent: 无`）
- UI 截图（如适用）

不要：

- 直接 push `main`
- force push
- 一张 PR 同时改四个目录
- 提交 `crash.log` / `__pycache__` / 临时截图
- 为了过测试删断言

---

## 8. 测试

```powershell
python tools/run_all.py
```

包含：

- 分层依赖
- 事件命名与注册表
- 机制
- 18 关清场
- 教程
- 完整流程
- 全界面
- 拖拽
- 音频

单独跑：

```powershell
python tools/events_test.py
python tools/mechanics_test.py
python tools/rooms_test.py
python tools/screens_test.py
python tools/audio_test.py
```

验收：

- 22 房可加载
- 18 正式关可通
- 4 教程可完成
- 商店/整备/卖卡/++/修格可用
- 无新增 `crash.log`

---

## 9. 程序化世界生成

Owner：A
校验：B
接口：Lead
种子回归：D

```text
content/procgen/
  seed.py
  templates.py
  room_graph.py
  encounter.py
  pacing.py
  validate.py
```

阶段：

1. 固定 18 关 + 种子选择商店/奖励
2. 模板 + 遭遇槽位随机
3. 房间图变体
4. 整局 `RunPlan`

硬约束：

- 可通关
- 至少一种解法
- 不超预算
- 不连续 3 房无卡
- Boss 不在第一房
- 同种子同结果

---

## 10. 文档维护

- 内容改动 → `docs/CONTENT.md`
- 结构/所有权/流程 → 本文件
- 协作 Issue / 通知 / @lead 边界 → `docs/COLLABORATION.md`
- 路线/版本 → `ROADMAP.md` / `CHANGELOG.md`
- 新功能需求 → `docs/FEATURE_REQUESTS.md`
- 设计历史 → `docs/DESIGN.md`

当前内容以 `docs/CONTENT.md` 为准；设计稿只作历史归档。
