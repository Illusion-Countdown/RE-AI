# 更新记录 / CHANGELOG

本项目使用类似 [Semantic Versioning](https://semver.org/) 的版本号。
Alpha 阶段不保证存档/接口兼容。

## [Unreleased]

### Added

- 新增事件命名规范 `docs/EVENT_NAMING.md`、唯一注册表 `memory_run/events.py` 与自动检查 `tools/events_test.py`
- 新增协作规范 `docs/COLLABORATION.md` 与“协作子任务”Issue 模板：父子 Issue、队友互提需求、事件契约、`@lead` 边界；父 Issue Assign 提需求者并进 Project，子 Issue Assign Owner 且不进 Project

### Changed

- 自机改为 AI 娘：标题界面选择 DeepSeek / Claude / GPT / Gemini，战斗画面显示所选 AI 娘；数据结构退出自机选择，只保留为运行时层的世界内容
- 战斗表现/音频改为每场独立事件总线：`Battle` 只发语义事件，`ui/battle_fx.py` 与 `platform/audio_feedback.py` 各自监听；战斗层不再直接调用 FX/audio
- 顿帧/慢放拆到 `battle/clock.py`，`Battle` 只依赖窄时钟接口
- 新增 `tools/feedback_test.py`，检查事件订阅、监听器接线、CUT 表现和战斗层无直接 FX/audio 调用
- 新增 `docs/BATTLE_EVENTS.md`，记录 57 个战斗事件的 payload 契约
- `Battle` 必须通过 `ui/battle_factory.create_battle()` 创建；App 和测试统一走同一套总线接线
- `EventBus` 增加 strict 模式：游戏内记录监听器异常并继续，测试/开发可严格抛出
- 手牌改为 3 张：初始抽 3，用 1 抽 1，移除自动抽牌、备用/溢出和洗回
- 每张卡每房第一次使用后随机放回牌堆，第二次使用后本房耗尽；下一房重置
- 战斗界面改为全屏战场 + 透明浮层；手牌居中，选中牌高亮
- 角色头顶新增三色弧形手牌球，中间球对应选中牌
- 手牌卡面按卡牌类型着色，改为不透明底色 + 类型色条，避免三张牌看起来一样
- 手牌默认选中中间一张并自动进入瞄准
- 战斗镜头恢复固定全战场视野，不再缩放或跟随角色
- `Shift` 切换上一张，`Space` 切换下一张，按住鼠标中键减速，`E` 冲刺
- 切换手牌时增加横移、选中牌上浮和金色扫描动画
- 角色头顶增加当前选中牌的名称与图标回声
- ECC、压缩等自身/修复卡改为左键点击战场任意处直接释放
- CUT / SWEEP 等非连接卡没有目标时也可释放；连接/点对象类仍需有效目标
- WRITE 右键攻击距离从 460 缩短到 170
- 所有 GC 增加按当前子树规模缩放的冲击波；先清子节点会降低范围，命中玩家造成伤害并新增坏死格
- 新增 LUNGER / SLASHER / EXECUTOR 近战敌人与红色攻击边
- 用 CUT 剪断红色攻击边即可振刀：免伤、失衡敌人、回复 FOCUS 和工作内存
- `reg` Boss 规则改为“回收置顶”

### Fixed

- 修正 `EventBus.emit` 在监听方回调里注销时返回值按快照计数
- 修正带护盾的 Boss 被 ALIAS 伤害时丢失 `SHIELD` 文本
- 修正商店重复购买已拥有模块时仍扣碎片
- 修正 `use_card` 异常兜底因缺少 `traceback` 导入而二次崩溃
- 修正 Boss/模块奖励前整备返回时错误回到卡牌三选一导致 KeyError
- 修正整备界面首次绘制前点击、持卡时右键触发按钮、右键开战
- 修正屏障音效、ALIAS 受伤音效、GC 路径绕过异常捕获
- 修正网格扩容规则被下一次 Boss 扩容覆盖、模块奖励补入已拥有模块
- 修正 COMPRESS++ 伤害倍率、教程奖励文案、`run_all` 漏跑 `tool_test`
- 修正从手牌拖 edge 卡只结算落点一条边；CUT++ 现在一次剪两条
- 渲染不再覆盖 `battle.mouse`/悬停状态，震屏偏移纳入输入坐标换算
- 实装 `weak_net` 持续可见、`cow` 首次伤害不同步血池、`tail_rec` 三级联上限
- 实装 WEAK++ 双目标标记、`overload` 全伤害、KERNEL 可 GC 归零
- 修正 T3 教程文案与实际 15%/45% 承伤、玩家边不计 refcount 一致
- 协作规范增加“无法独立完成或需要未写明的跨人改动时，必须给对应 Owner 开子 Issue 并写清细节”的硬规则
- 房间 `zone` 统一为 0（教学）/ 1–5（正式区）
- 移除无效果的 `discount` Boss 规则
- `perfect` 规则改为真正的碎片奖励翻倍（2 → 4）
- 移除未使用的 `ZOMBIE` 定义
- ECC 描述去掉“清除泄漏”
- 移除 `Deck.register` / 付费升级死代码

### Planned

- 内容校验与种子回归
- 可选：图鉴、程序化遭遇

---

## [0.5.1-alpha] - 2026-11-16

### Added

- 5 区 18 战与 5 Boss 的完整单局
- 商店、整备、卖卡、免费 `++`、碎片经济
- CUT 划线剪断、WEAK 增伤/减攻、LINK 承伤
- 协同敌人：WARD 护盾、PYLON 支援、SENTINEL 精英波
- 4 节教程：CUT / WEAK / LINK / CAST
- 27 个程序化音效，F2 测试、F3 切设备
- `crash.log` 崩溃记录
- 分层依赖检查与一键回归

### Changed

- 代码按 `core/content/run/battle/ui/platform` 分层
- 战斗拆成 core/input/actions/gc/player/enemies
- 渲染拆成 common/core/world/hud/hand
- 抽牌改为整个卡组；寄存器改为 BENCH 展示
- 升级改为拖拽免费

### Fixed

- 支援节点缺少 `atk`/`special` 计时器导致的异常退出
- ECC 调用不存在的 `Deck.all_cards()` 导致无法使用
- CUT 单剪误剪多条（恢复为基础 1 条、++ 2 条）
- PvP 相关代码归档，不再维护

---

## [0.5.0-alpha] - 2026-11-15

### Added

- 初始可玩版本
- 引用图/GC、卡牌网格、画质降级
- 基础房间、敌人、Boss
- 程序化美术与音频

---

## 版本说明

- `0.x`：Alpha，允许 breaking change
- `1.0`：第一个面向公众的 Demo
- 每次 release 必须包含：
  - 新增内容
  - 修复问题
  - 已知问题
  - 升级/兼容说明（如有）
