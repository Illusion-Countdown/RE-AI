# 悬垂：内存远征 / DANGLING RUN

单人实时肉鸽 · pygame-ce · 1600×900 · 固定 3 区 9 房 + 3 Boss

> 把卡组塞进一块 5×5 的内存，留白就是工作内存。剪断引用，让整片对象归零。

![战斗](screenshots/03_battle.png)

## 运行

```bat
双击 开始游戏.bat
或 python run.py
```

- `python run.py --windowed` 窗口模式
- `python run.py --shots` 无头生成截图

需要 Python 3.9+ 与 `pygame-ce`（`pip install pygame-ce`）。

## 操作

| 输入 | 作用 |
|---|---|
| WASD / 方向键 | 移动 |
| SHIFT | 向鼠标方向冲刺 |
| 1–5 | 使用执行槽；也可以直接按住卡拖到目标 |
| 左键拖拽 | 按住手牌拖到边/对象/区域，松手使用；整备界面按住卡拖进格子，松开放下 |
| 右键 | WRITE：朝鼠标方向打一发，不耗卡；拖拽时取消 |
| Q | 每房一次重抽 |
| SPACE | 规划减速，消耗 FOCUS |
| G / R / T | 免费 GC（Boss 规则）/ 坏死引爆 / 死代码消除 |
| ESC | 暂停 |

## 核心规则

- 世界只有对象和指向对象的引用；`refcount` 只数 STRONG 入边。
- 引用归零 → 立刻被 GC 擦除；剪枢纽会级联。
- 战斗从**整个卡组**（网格内所有卡）抽牌；未入网格的卡在 BENCH 说明区，不参与战斗。
- CUT 按住左键划过引用线，松手结算；基础只剪划到的第一条边（++ 前两条），消耗 1 工作内存。
- 手牌每 2.4s 自动抽 1 张；用牌后 0.65s 内补牌。牌堆抽空会反复洗回，每次洗回本房画质上限 -6%（最高 -42%）。
- WEAK 不计入 refcount；被标记目标受到伤害 +35%、对玩家造成伤害 -35%。
- LINK 敌人 = 争夺：它停火，并替你分摊 15% 伤害（每多一条 +15%，上限 45%）；玩家自己的 HOLD 边不计入 refcount，不会把敌人锁在内存里。
- CAST 剥掉析构器/类型免疫，再 CUT 才安全。
- 网格里的卡 = 内存占用；空闲格 = 工作内存。负载越高，画质越低。
- 画质是实时值：`100 − 50×负载/总 − 50×工作/空闲`，修格/删卡会回升。
- 画质四档：100–75 清晰 / 74–50 轻微降采样 / 49–25 低分辨率 / 24–0 像素块 + 扫描线；最低档世界只保留原像素量约 11%，HUD 保持清晰。
- 敌人以**编队**出现：WARD 给最近友军套盾；危险度 ≥5 补 WARD 支援，≥8 补 PYLON 支援；危险度 ≥8 会空投 1 个 SENTINEL 精英，不再堆小怪。
- 弹幕密度：危险度 ≥3/6/9 时齐射 2/3/4 发，并缩短射击间隔；Boss 至少 2 发。
- 奖励后与 Boss 安全屋都可整备、进商店；同名基础卡互相拖动免费升级 ++。
- 碎片：普通房 +1，Boss +3，完美 +2；修 1 格 2 碎片；商店 2–5 碎片；不要的卡拖到整备界面 SELL 区卖出。
- 完美清房：无伤 + 画质 ≥75 + 无新增坏死。

## 内容

- 4 个教学房：CUT / WEAK / LINK / CAST。
- 18 个固定战斗：引用荒原、并发回廊、类型深渊、碎片浅滩、内核深渊各 3 战 + 1 Boss。
- 16 张卡、3 种身体、14 个模块、6 条 Boss 规则、++ 免费升级、商店。
- 每次奖励后整备；Boss 后额外安全屋与 Boss 规则。

## 代码

```text
run.py                 启动
memory_run/
  const.py             布局、调色、字体、绘制工具
  core/                Node / Edge / Graph / Card / Grid / Hand
  content/             身体、AI 娘、模块、Boss 规则、卡牌定义、房间、奖励池
  run/                 一局远征状态、商店、碎片
  battle/              core / input / actions / gc / player / enemies
  ui/                  app / render / screens / deckui / fx
  platform/            程序化音频
tools/                 无头测试、音频自检与截图
```

实际目录、文件所有权和兼容 shim 见 `STRUCTURE.md`；四人分工见 `TEAM_PLAN.md`。

全部美术由代码绘制，音效启动时合成，无外部素材。
视觉/音频复用：`DANGLING` 的引用图/标题/结局图/模块符印，`asymptote` 的程序化合成音频层。
玩家 SELF、敌人几何模型与 refcount 环直接复用 `DANGLING` 的 `draw_player` / `shape_*` / `draw_refcount`。

音频故障排查：F2 播放测试和弦；F3 循环切换 Windows 输出设备（FxSound / Realtek / 蓝牙等）。
如果异常退出，根目录会写入 `crash.log`（含 traceback）。

## 测试

```bat
python tools/run_all.py          # 一键跑全部无头回归
python tools/flow_test.py        # 教程 → 18 战流程
python tools/tutorial_test.py    # 四节教程真实卡牌操作
python tools/rooms_test.py       # 逐房清场
python tools/screens_test.py     # 全界面渲染
python tools/drag_test.py        # 拖卡入格 / 手牌拖边
```

更多设计：`../内存远征_架构与代码说明.md`
当前目录与所有权：`STRUCTURE.md`
四人分工：`TEAM_PLAN.md`
