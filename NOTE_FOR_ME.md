# NOTE FOR ME · 仓库逐文件说明

> 这是给你自己看的维护笔记，不是对外文档。
> 目标：打开仓库后，能快速知道“这是什么、谁负责、我该不该改”。
> 当前代码：MEMORY_RUN / 悬垂：内存远征，单人不联机，可玩 Alpha。

---

## 0. 你日常只需要记住这几件事

### 你作为 Lead 最常改

```text
memory_run/ui/app.py      状态机、输入分发、主循环
memory_run/const.py       布局、颜色、字体、公共常量
run.py                    入口
```

### 你最常看，但不要随便改

```text
memory_run/battle/*        B 的战斗规则
memory_run/content/*       A 的内容与数值
memory_run/ui/render_*     C 的表现
memory_run/platform/audio  D 的音频
```

### 合并前必须跑

```powershell
python tools/run_all.py
```

### 当前最容易踩的坑

- `RoomDef.zone` 还是旧编号，区域名/奖励池会错位。
- `discount` Boss 规则没有实际效果。
- `perfect` 规则描述写“翻倍”，实际只 +1 碎片。
- `ZOMBIE` 只有 HP 定义，没有房间和行为。
- `screenshots/` 被 `.gitignore` 忽略，但已有旧截图仍被 Git 跟踪。

---

## 1. 根目录文件

| 文件 | 作用 | 你该不该改 |
|---|---|---|
| `README.md` | 项目门面：是什么、怎么跑、操作、内容、测试、贡献入口 | 项目范围/玩法大改时改 |
| `CONTRIBUTING.md` | 贡献流程、分支、提交规范、PR 要求、测试要求 | 流程变化时改 |
| `CODE_OF_CONDUCT.md` | 社区行为准则 | 很少改 |
| `ROADMAP.md` | 当前阶段与 v0.5–v1.0 路线、非目标 | 版本目标变化时改 |
| `CHANGELOG.md` | 每个版本的 Added/Changed/Fixed | 每次发布改 |
| `SECURITY.md` | 漏洞报告渠道、支持版本、处理时间 | 安全策略变化时改 |
| `LICENSE` | MIT 许可证 | 不建议改 |
| `requirements.txt` | `pygame-ce` 依赖 | 依赖变化时改 |
| `run.py` | 启动入口，调用 `memory_run.app.main()` | 很少改 |
| `gameStart.bat` | Windows 启动器：切 UTF-8、进目录、运行、暂停 | 打包/启动方式变化时改 |
| `NOTE_FOR_ME.md` | 本文件，个人维护笔记 | 可随时改 |
| `.gitignore` | 忽略缓存、构建、截图、日志 | 注意：`screenshots/` 被忽略 |

### `run.py` 的真实路径

```python
from memory_run.app import main
```

`memory_run/app.py` 只是兼容 shim，真正实现在 `memory_run/ui/app.py`。

---

## 2. `.github/` 文件

| 文件 | 作用 |
|---|---|
| `.github/PULL_REQUEST_TEMPLATE.md` | 新建 PR 时自动带出的检查清单 |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Bug 表单：版本、环境、复现、crash.log |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | 功能表单：一句话、规则、交互、验收 |
| `.github/ISSUE_TEMPLATE/config.yml` | Issue 入口配置，链接贡献指南/路线图/安全 |
| `.github/workflows/ci.yml` | GitHub Actions：装依赖、架构检查、全量回归、上传截图 |

### CI 触发

- push 到 `main`
- PR 到 `main`
- 手动 `workflow_dispatch`

CI 环境：

```text
SDL_VIDEODRIVER=dummy
SDL_AUDIODRIVER=dummy
PYTHONIOENCODING=utf-8
```

### CI 实际执行

```text
python tools/architecture_test.py
python tools/run_all.py
```

注意：`tools/tool_test.py` 不在 `run_all.py` 里，需要手动跑。

---

## 3. `docs/` 文件

| 文件 | 作用 | 维护时机 |
|---|---|---|
| `docs/README.md` | 文档索引，4 份主文档的入口 | 新增/删除文档时 |
| `docs/DEVELOPMENT.md` | 代码结构、分层、所有权、依赖、接口、测试、提交流程 | 结构/分工/接口变化时 |
| `docs/CONTENT.md` | 当前卡牌、模块、敌人、Boss、房间、经济、音频清单 | 新增内容后 |
| `docs/FEATURE_REQUESTS.md` | 新功能一页式模板、A/B/C/D 拆单、验收写法 | 需求流程变化时 |
| `docs/DESIGN.md` | 原始设计稿与实现修订记录 | 设计历史，不是当前规格 |

### 阅读优先级

```text
想运行 → README
想改代码 → docs/DEVELOPMENT.md
想加内容 → docs/CONTENT.md
想提新玩法 → docs/FEATURE_REQUESTS.md
想查设计来源 → docs/DESIGN.md
```

### 重要区别

- `docs/CONTENT.md` 是**当前实际内容**。
- `docs/DESIGN.md` 是**历史设计稿**，里面可能写过未实现的东西。
- 不要拿设计稿当验收标准；以代码和 CONTENT 为准。

---

## 4. `memory_run/` 代码总览

```text
memory_run/
├─ __init__.py
├─ app.py / battle.py / cards.py / ...   兼容 shim
├─ core/                                规则底座
├─ content/                             内容数据
├─ run/                                 远征状态
├─ battle/                              战斗
├─ ui/                                  界面与表现
└─ platform/                            音频
```

### 4.1 根目录 shim（不要写业务逻辑）

| 文件 | 实际指向 |
|---|---|
| `memory_run/app.py` | `ui.app` |
| `memory_run/audio.py` | `platform.audio`（模块别名） |
| `memory_run/battle.py` | `battle.battle` |
| `memory_run/cards.py` | `core.cards` |
| `memory_run/deckui.py` | `ui.deckui` |
| `memory_run/fx.py` | `ui.fx` |
| `memory_run/model.py` | `core.model` |
| `memory_run/render.py` | `ui.render` |
| `memory_run/runstate.py` | `run.runstate` |
| `memory_run/screens.py` | `ui.screens` |

这些文件只有 1–5 行，旧测试和旧脚本靠它们还能导入。**新代码不要继续从 shim 加逻辑。**

### 4.2 `memory_run/__init__.py`

- 包标记。
- 里面有 `__version__ = "0.1.0"`。
- **这个版本号是旧的**，和 `ROADMAP` 的 `v0.5.1-alpha` 不一致；以后统一版本时再改。

### 4.3 `core/`：规则底座

| 文件 | 行数 | 作用 |
|---|---:|---|
| `core/model.py` | 200 | `Node` / `Edge` / `Graph`、refcount、邻居查询 |
| `core/cards.py` | 329 | `Card` / `Grid` / `Hand` / `Deck`、画质公式、网格装箱 |
| `core/__init__.py` | 1 | 导出 `model` / `cards` |

你一般不需要改；这是 B 的领地。

### 4.4 `content/`：内容数据

| 文件 | 行数 | 作用 |
|---|---:|---|
| `content/bodies.py` | 15 | 3 种身体：链表/数组/树 |
| `content/avatars.py` | 25 | 4 个 AI 娘 |
| `content/modules.py` | 34 | 14 个模块 |
| `content/boss_rules.py` | 10 | 6 条 Boss 规则 |
| `content/card_defs.py` | 104 | 16 张卡牌定义 |
| `content/rooms.py` | 260 | 教程 + 5 区 18 战房间数据 |
| `content/pools.py` | 18 | 分区奖励池 / 模块池 |
| `content/progression.py` | 24 | `room_for_step` / `zone_of` / 区域名 |
| `content/__init__.py` | 10 | 内容包统一出口 |

这是 A 的领地。加卡/房/敌人优先只改这里。

### 4.5 `run/`：远征状态

| 文件 | 行数 | 作用 |
|---|---:|---|
| `run/runstate.py` | 319 | HP、碎片、卡组、模块、规则、商店、卖卡、修格、推进 |
| `run/__init__.py` | 1 | 包标记 |

经济/奖励/商店相关优先改这里，A 负责。

### 4.6 `battle/`：战斗

| 文件 | 行数 | 作用 |
|---|---:|---|
| `battle/battle.py` | 3 | 门面，导出 `Battle` / `Projectile` / `AliasPool` |
| `battle/core.py` | 288 | `Battle` 本体：初始化、建房、update、finalize |
| `battle/input.py` | 273 | 选卡、拖拽、划线 CUT、鼠标/键盘 |
| `battle/actions.py` | 422 | 卡牌费用、`use_card`、`apply_card`、`do_*` |
| `battle/gc.py` | 212 | 伤害、死亡、GC 级联、清房 |
| `battle/player.py` | 227 | 玩家移动、工作内存、画质、别名、受击 |
| `battle/enemies.py` | 286 | 敌人、Boss、增援、投射物 |
| `battle/entities.py` | 39 | `Projectile` / `AliasPool` |
| `battle/constants.py` | 16 | `PLAYER_R` / `DEFAULT_HP` / `NODE_COLOR` |
| `battle/deps.py` | 10 | 战斗公共 import 汇总 |

`Battle` 由五个 mixin 组成：

```python
class Battle(InputMixin, ActionsMixin, GcMixin, PlayerMixin, EnemiesMixin):
```

这是 B 的领地。

### 4.7 `ui/`：界面与表现

| 文件 | 行数 | 作用 |
|---|---:|---|
| `ui/app.py` | 685 | 状态机、输入分发、主循环、F2/F3、截图 |
| `ui/screens.py` | 520 | 标题/帮助/暂停/奖励/模块/规则/商店/结算/教程 |
| `ui/deckui.py` | 423 | 整备/BENCH/拖拽/免费 `++`/修格/卖卡/商店入口 |
| `ui/fx.py` | 279 | 屏幕 FX：闪白/震屏/粒子/浮字/故障/慢放 |
| `ui/render.py` | 4 | 渲染门面 |
| `ui/render_common.py` | 168 | 卡面/文字/轨迹等公共绘制 |
| `ui/render_core.py` | 130 | `BattleRenderer` 初始化/draw/降质/拖拽残影 |
| `ui/render_world.py` | 451 | 战场/引用线/敌人/玩家/refcount |
| `ui/render_hud.py` | 226 | HUD/网格/房间信息/卡牌详情 |
| `ui/render_hand.py` | 133 | 手牌/执行槽/横幅/开场 |
| `ui/render_deps.py` | 10 | 渲染公共 import 汇总 |

`ui/app.py` 是你和 C 的边界；状态机归你，表现归 C。

### 4.8 `platform/`

| 文件 | 行数 | 作用 |
|---|---:|---|
| `platform/audio.py` | 221 | 27 个程序化音效、F2 测试、F3 切设备、静音、节流 |
| `platform/__init__.py` | 1 | 包标记 |

D 负责。

---

## 5. `tools/` 测试工具

| 文件 | 作用 | 是否在 run_all |
|---|---|---|
| `tools/architecture_test.py` | 分层依赖检查，禁止 battle→ui 等反向依赖 | ✅ |
| `tools/mechanics_test.py` | 自动抽牌、CUT 费用、WEAK、LINK、ECC | ✅ |
| `tools/rooms_test.py` | 22 房逐房加载/清场 | ✅ |
| `tools/flow_test.py` | 教程→18 关完整流程 | ✅ |
| `tools/tutorial_test.py` | 4 节教程真实操作 | ✅ |
| `tools/screens_test.py` | 全界面渲染并生成 `ui_*.png` | ✅ |
| `tools/drag_test.py` | 拖卡入格/手牌拖边 | ✅ |
| `tools/audio_test.py` | 音频初始化、音效 busy、设备列表 | ✅ |
| `tools/tool_test.py` | 边列表目标的回归（STEAL/REFLECT/WEAKEN/DELAY） | ❌ 手动 |
| `tools/run_all.py` | 串行跑上面所有 ✅，失败返回非零 | 入口 |

### 怎么用

```powershell
python tools/run_all.py
```

单独跑：

```powershell
python tools/mechanics_test.py
python tools/rooms_test.py
python tools/tool_test.py
```

---

## 6. `screenshots/`

这些是自动/手动截图，README 只引用了 `03_battle.png`。

| 文件 | 内容 |
|---|---|
| `01_title.png` / `ui_title.png` | 标题 |
| `02_deck.png` / `ui_deck.png` | 整备 |
| `03_battle.png` / `ui_battle.png` | 战斗 |
| `04_reward.png` / `ui_reward.png` | 奖励 |
| `05_end.png` / `ui_victory.png` | 结算 |
| `06_window_title.png` | 窗口模式标题（旧） |
| `07_window_deck.png` | 窗口模式整备（旧） |
| `08_window_battle.png` | 窗口模式战斗（旧） |
| `09_drag.png` | 拖拽测试截图 |
| `13_alias.png` | ALIAS 效果截图 |
| `ui_defeat.png` | 失败 |
| `ui_help.png` | 帮助 |
| `ui_module.png` | 模块三选一 |
| `ui_pause.png` | 暂停 |
| `ui_quality3.png` | 最低画质/像素化 |
| `ui_retry.png` | 重试 |
| `ui_rule.png` | Boss 规则三选一 |
| `ui_shop.png` | 商店 |
| `ui_tutorial_clear.png` | 教程完成 |
| `ui_tutorial_end.png` | 教程结束 |
| `ui_victory.png` | 胜利 |

注意：

- `.gitignore` 忽略 `screenshots/`。
- 旧截图已经被 Git 跟踪，所以仍会出现在仓库。
- 新截图默认不会进 Git；要提交必须 `git add -f`，或者改 `.gitignore`。
- 如果要清理，先确认 README 和文档引用的图。

---

## 7. 你最容易弄混的几个点

### `memory_run/app.py` vs `memory_run/ui/app.py`

- `app.py` 是 1 行 shim。
- 真正的 App 在 `ui/app.py`。
- 改功能去 `ui/app.py`。

### `memory_run/render.py` vs `ui/render*.py`

- `render.py` 是 shim。
- 真正渲染在 `ui/render_core/world/hud/hand/common`。
- 不要改 shim。

### `content` 与 `core/cards.py`

- `content/card_defs.py` 是卡牌数据。
- `core/cards.py` 是卡牌/网格逻辑。
- 加卡改前者；改规则改后者。

### `battle/actions.py` 与 `content/card_defs.py`

- 数据：费用、形状、描述、稀有度。
- 行为：`apply_card` / `do_*`。
- 一张新卡通常两边都要动。

### `docs/CONTENT.md` 与 `docs/DESIGN.md`

- `CONTENT.md`：现在实际有什么。
- `DESIGN.md`：原始设计稿，可能包含未实现内容。
- 验收看代码 + CONTENT，不看设计稿。

---

## 8. 当前已知问题（维护时优先处理）

| 问题 | 位置 | 影响 | 建议 Owner |
|---|---|---|---|
| `RoomDef.zone` 仍是旧 1–12 编号 | `content/rooms.py` | 区域名/奖励池错位 | A |
| `discount` Boss 规则无效果 | `content/boss_rules.py` | 选了没用 | A/B |
| `perfect` 描述“翻倍”但只 +1 | `run/runstate.py` | 规则与描述不符 | A/B |
| `ZOMBIE` 未使用 | `battle/constants.py` | 死数据 | A/B |
| ECC 描述提到“清除泄漏” | `content/card_defs.py` | 实际只修坏死格 | A/B |
| `register` 数据残留 | `core/cards.py`、`run/runstate.py` | UI 已改 BENCH，旧概念 | A |
| `__version__ = 0.1.0` | `memory_run/__init__.py` | 与路线图版本不一致 | Lead |
| `tool_test.py` 不在 run_all | `tools/` | 容易漏跑 | D |

---

## 9. 你的检查清单

### 每天开始

```text
git status
git pull --ff-only
python tools/run_all.py   # 或至少 architecture + mechanics
```

### 合并 PR 前

- [ ] 只改自己负责的目录
- [ ] `run_all.py` 通过
- [ ] 无新增 `crash.log`
- [ ] 22 房仍能加载
- [ ] 4 教程仍能完成
- [ ] UI 改动有截图
- [ ] 内容改动同步 `docs/CONTENT.md`
- [ ] 结构改动同步 `docs/DEVELOPMENT.md`

### 发布前

- [ ] `CHANGELOG.md` 更新
- [ ] `README` 截图/说明更新
- [ ] 干净目录能启动
- [ ] 音频设备缺失能降级
- [ ] 打包/启动器可用

---

## 10. 一句话

> `ui/app.py` 和 `const.py` 是你的；`content/` 是 A 的；`battle/` 是 B 的；`ui/render*` 是 C 的；`platform/` + `tools/` 是 D 的；根目录文档是项目门面，`docs/DESIGN.md` 只是历史。
