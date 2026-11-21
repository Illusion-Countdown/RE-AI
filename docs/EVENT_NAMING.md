# 事件命名规范

> 目标：任何协作者都可以自己给事件起名，不需要等 Lead 签发。
> Lead / Reviewer 只检查三件事：**格式对不对、有没有重复、是不是同一个 PR 里真的用上了**。

---

## 1. 适用范围

本规范只管**跨层、跨模块的语义事件**，例如：

- `battle` 告诉 `ui`：某个节点被 GC 了
- `battle` 告诉音频层：振刀成功
- `run` 告诉 `ui`：商店刷新了
- `ui` 告诉战斗层：某个按钮被点击

不适用：

| 东西 | 应该放哪 |
|---|---|
| Pygame 输入事件（`KEYDOWN` / `MOUSEBUTTONDOWN`） | 直接用 `pygame`，不要注册 |
| 音效 cue（`cut` / `gc` / `select`） | `memory_run/platform/audio.py` 的 `_build()`，它是资源键，不是语义事件 |
| 卡牌 / 敌人 / 房间 / 模块 ID | 对应内容表，例如 `content/card_defs.py`、`content/rooms.py` |
| 屏幕上的 `CUT!` / `PARRY` / `WEAKEN` | UI 文案，不是事件名 |
| 命令（“使用卡牌”“选择目标”） | 方法调用，例如 `battle.use_card(...)`，不要叫事件 |

事件描述**已经发生的事实**，不是命令，也不是“请帮我做某事”。

---

## 2. 格式

```text
<DOMAIN>_<ACTION>[_<STATE>]
```

- 全大写，单词之间用单个下划线。
- 至少 2 段，最多 5 段；总长度不超过 48 个字符。
- 第一段是**事实归属的系统**，不是“谁监听”。
- 第二段是发生的事；第三段以后是可选时机、阶段或条件。
- 常量名和字符串值必须完全一样：

```python
ENEMY_SPLIT_ON_DEATH = "ENEMY_SPLIT_ON_DEATH"
```

推荐的第一段（不是白名单，新系统可以自己加）：

```text
BATTLE  CARD  ENEMY  PLAYER  GC  RUN  ROOM  SHOP  UI  SYSTEM  TUTORIAL  BOSS
```

### 好例子

```text
ENEMY_SPLIT_ON_DEATH
BATTLE_TURN_START
BATTLE_TURN_END
UI_BUTTON_CLICKED
CARD_CAST
GC_NODE_RECYCLED
PLAYER_DASH_STARTED
ROOM_CLEARED
SHOP_REROLLED
```

### 坏例子

| 名字 | 问题 |
|---|---|
| `enemy_split` | 不是全大写 |
| `ENEMYSPLIT` | 没有下划线分段 |
| `ENEMY_SPLIT_EVENT` | 多余的 `_EVENT` 后缀 |
| `EVENT_ENEMY_SPLIT` | 不要用 `EVENT_` 前缀 |
| `SHOW_SPLIT_TOAST` | 把 UI 表现写进了事实名 |
| `PLAY_SPLIT_SOUND` | 事件不是音频指令 |
| `ENEMY_SPLIT_2` | 不要用数字做版本；改名就改语义 |
| `SPLIT` | 缺少来源域，换一个系统就冲突 |

---

## 3. 唯一注册表

所有事件名只写在：

```text
memory_run/events.py
```

格式是一行一个常量（下面是格式示例，实际注册以 `events.py` 为准）：

```python
# --- 敌人 / Enemy ---
ENEMY_SPLIT_ON_DEATH = "ENEMY_SPLIT_ON_DEATH"

# --- 战斗 / Battle ---
BATTLE_TURN_START = "BATTLE_TURN_START"
```

规则：

1. **同一个 PR 里注册并使用**。至少有一个真实的发送方或监听方；只加一行常量、没有任何接线的 PR 不合并。不要提前预埋一堆没人发、没人听的事件。
2. **不要在 `enemy.py`、`ui.py`、`battle.py` 里写事件字符串**。发送和监听都用 `events.XXX`。
3. **一个名字只表达一个事实**。同一个事件不要一会儿带节点、一会儿不带节点；payload 不同就拆成两个事件。
4. **不建别名**。改名时在同一个 PR 里改掉所有引用；Alpha 阶段不承诺外部事件兼容。
5. **不按监听方命名**。叫 `ENEMY_DIED`，不要叫 `AUDIO_PLAY_DEATH` 或 `UI_SHOW_DEATH`。
6. **不写裸字符串**。`emit("ENEMY_DIED")` 和 `subscribe("ENEMY_DIED", ...)` 都会被检查脚本拦下。

当前仓库已经接入每场战斗独立的 `EventBus`：

- 每次 `App.start_battle()` 创建新的 `EventBus`，传给 `Battle`。
- `battle/` 只 `emit`，不 import `ui` / `platform.audio`。
- `ui/battle_fx.py` 负责视觉，`platform/audio_feedback.py` 负责音频。
- 总线是同步的，`emit` 当场按订阅顺序执行，表现与旧直接调用同一帧。
- 游戏内总线 `strict=False`：监听器异常记录后继续；测试/开发用 `strict=True` 让异常暴露。
- 不预埋没有发送方/接收方的事件；新增事件必须在同一个 PR 里接线。

事件只用于“已经发生的事实”的通知，不用于伤害/GC/卡牌结算等确定性规则。

---

## 4. 加一个新事件（协作者自助）

1. 在 `memory_run/events.py` 里找一下有没有现成的。
2. 没有就按格式加一行，例如：

   ```python
   ENEMY_SPLIT_ON_DEATH = "ENEMY_SPLIT_ON_DEATH"
   ```

3. 在同一个 PR 里：
   - 发送方用 `self.bus.emit(events.ENEMY_SPLIT_ON_DEATH, ...)`；
   - 视觉监听方在 `ui/battle_fx.py` 里 `bus.subscribe(...)`；
   - 音频监听方在 `platform/audio_feedback.py` 里订阅；
   - 在发送方 docstring 或 PR 描述里写清 payload（带哪些字段、字段含义）。
4. 跑：

   ```powershell
   python tools/events_test.py
   ```

5. 提 PR。**不需要先问 Lead 叫什么名字**。

Issue 里怎么写事件契约、谁来发/谁监听，见 [`COLLABORATION.md`](COLLABORATION.md#5-事件契约)。
现有战斗事件的 payload 见 [`BATTLE_EVENTS.md`](BATTLE_EVENTS.md)。

---

## 5. Review 清单（60 秒）

Reviewer 只看这些，不讨论“我更喜欢哪个词”：

- [ ] 符合 `<DOMAIN>_<ACTION>[_<STATE>]`，2–5 段，全大写
- [ ] `events.py` 里没有重名、没有重复值
- [ ] 常量值等于常量名
- [ ] 没有在业务模块里写裸字符串
- [ ] 描述的是事实，不是 UI 指令 / 音频指令 / 方法命令
- [ ] 同一个 PR 里至少有一个真实使用点（发送或监听），不是只注册一行
- [ ] 如果发送/监听只接了一边，PR 里写明下一步；不要长期留半截
- [ ] payload 写清楚了，没有同名不同 payload
- [ ] `python tools/events_test.py` 通过

只要以上都过，**名字本身由作者拍板**。Lead 不负责起名，只负责拦违规。

---

## 6. 和现有命名的关系

- 卡牌 / 敌人 / 房间 / 模块 ID：沿用各自内容表的既有短名，不要套事件格式。
- 音效 cue：继续用 `platform/audio.py` 里的短键；如果以后改成事件驱动，再把 cue 映射到 `AUDIO_*` 事件。
- Pygame 事件：保持 `pygame.KEYDOWN` 等原生名字，不进入注册表。
- 本规范生效后，新增的跨层事件常量**只能**出现在 `memory_run/events.py`；检查脚本会扫描其他模块里的同名常量和裸字符串。

---

## 7. 一句话

> 作者按格式自己起名，写进 `events.py`，同一个 PR 里接线；Reviewer 只当海关，不当起名机器。
