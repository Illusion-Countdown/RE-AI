# Tutorial Battle：第一关 3 人 × 3 Wave 教学战斗

> task-11 交付。文件：`RE-AI-AutoChess/tutorial_battle.py`（独立运行，不修改 `character_lab.py` / `main.py` / `battle_demo.py` / `assets`）。
> 只做第一关教学战斗：**3 个固定角色、3 波敌人、引用网络与一次断连**；无第二关内容。
> 截图：`shots/tutorial_*.png`（窗口物理分辨率，默认 2K 下 2560×1440）。

---

## 1. 快速开始

工作目录 `D:\Pygame\RE-AI-AutoChess`，使用项目 venv：

```powershell
D:\Pygame\.venv\Scripts\python.exe tutorial_battle.py                       # 默认全屏（2560×1440 物理直绘）
D:\Pygame\.venv\Scripts\python.exe tutorial_battle.py --windowed
D:\Pygame\.venv\Scripts\python.exe tutorial_battle.py --windowed --size 1920x1080
D:\Pygame\.venv\Scripts\python.exe tutorial_battle.py --shot shots\tutorial_wave1.png --time 7
D:\Pygame\.venv\Scripts\python.exe tutorial_battle.py --shot shots\tutorial_wave2.png --start-wave 2 --time 6
D:\Pygame\.venv\Scripts\python.exe tutorial_battle.py --shot shots\tutorial_wave3_network.png --start-wave 3 --time 4
D:\Pygame\.venv\Scripts\python.exe tutorial_battle.py --shot shots\tutorial_wave3_cut.png --start-wave 3 --auto-cut --time 6
```

无窗口 smoke（自动跑完选角、3 波、弹窗、剪线、结算并截图）：

```powershell
$env:SDL_VIDEODRIVER='dummy'; $env:SDL_AUDIODRIVER='dummy'
D:\Pygame\.venv\Scripts\python.exe tutorial_battle.py --smoke
# → TUTORIAL BATTLE SMOKE OK
```

---

## 2. 固定队伍与范围圈

**固定 Qwen / DeepSeek / Claude，不替换、不拖拽部署、不消耗资源。**

| 角色 | 定位 / 技能类型 | 移动内圈（蓝） | 攻击/支援外圈 | 自动行为 |
| --- | --- | --- | --- | --- |
| Qwen | 先锋 / SHIELD | 140 | 180（黄） | 自动给附近友军护盾（辅助判定范围 180） |
| DeepSeek | 输出 / ATTACK | 170 | 260（黄） | 远程持续输出 |
| Claude | 支援 / HEAL | 150 | 250（绿） | 自动治疗生命最低角色 |

- DeepSeek 复用 manifest 的 dsh（蓝毛小女仆）资源；3 角色全部来自 `assets/pets/lab_manifest.json`，无 fallback。
- **选角介绍界面（战前）**：3 张固定角色卡，显示定位/技能类型/两圈示意（蓝内圈锚定部署点固定，黄/绿外圈跟随角色）；
  Qwen 卡显示「移动内圈 140 · 护盾/攻击外圈 180」，三人都保证蓝内圈在外圈之内；悬停/点击卡片看说明；
  不会真正选择/替换；点击「进入第一关」开始教程。选角页标题同为「内存远征 · 第一关」+ `TUTORIAL // 选角`。
- 战斗中选中左侧角色小框或悬停战场角色时，显示该角色范围圈（同一时间只显示一个）：
  - 蓝内圈：移动范围，锚定部署点固定不动；
  - 黄/绿外圈：攻击/支援范围，跟随角色当前位置；
  - 低透明填充 + 虚线描边；选中时轻微脉动。
- 角色自动移动限制在**各自的活动带**内（三人分带、不互相叠、带内软分离），敌人主动靠近。

---

## 3. 分辨率 / 内存策略

- 1920×1080 逻辑坐标，**按窗口物理像素直绘**（复用 `character_lab.Painter` 的坐标映射，不整幅 scale）；
  默认窗口 2560×1440，s=4/3。
- 战场角色统一等比缩小：源帧先按约 0.75× 再乘 **0.55×**（2K 下约 **0.413× 源帧**，1080P 约 0.28×），脚底锚点不变。
  在此基础上按**统一目标视觉身高**归一化：读取每个角色源帧 bbox 高度，以三人平均身高为目标，分别计算各角色绘制缩放
  （源图高矮不同 → 绘制系数不同），战场渲染高度保持一致；左栏小框/选角头像仍从高分辨率源帧生成。
- 三人各有独立活动带（三行条带，互不重叠），带内软分离；敌人绘制比例同步缩到约 0.72×，血量条/位置协调。
- 3 个角色只 lazy load `idle + move`（启动 6 clips，约 43.5MB），`skill` 首次释放时加载；无大招资源。
- 实测缓存：启动约 43.5MB，整场 smoke（3 角色 idle/move/skill）峰值约 71.4MB，远低于 512MB 上限。

---

## 4. 流程

```
选角介绍界面（3 固定角色，点击进入）
  → 开场弹窗：三固定角色
  → W1 弹窗：自动战斗说明
  → W1 弹窗：新敌人「游标」
  → WAVE 1：2× 游标
  → W2 弹窗：新敌人「哨兵」→ 新敌人「析构炸弹」（分别弹，不合并）
  → WAVE 2：游标 + 哨兵 + 析构炸弹
  → W3 弹窗：新敌人「护盾守卫」→ SHARE/BUFF 引用网络 → 断连操作
  → WAVE 3：哨兵 + 护盾守卫（SHARE 青 + BUFF 金，只允许剪一次）
  → 结算界面：两张被动协议卡（只展示）→ 结束本关
```

所有首次出现的新机制/敌人/操作都是**时停模态弹窗**，点击继续才恢复战斗；全灭时弹「重试当前波」，不会重复机制说明。

---

## 5. 敌人（玩家界面统一中文名，内部 key 不变）

| 内部 key | 中文名 | HP | 移动 | AI |
| --- | --- | --- | --- | --- |
| MINION | 游标 | 72 | 快（64） | 主动接近最近角色，进入近战距离停下攻击 |
| SENTINEL | 哨兵 | 230 | 慢（40） | **远程**：移动到射程（190）后停下，发射投射物 |
| BOMB | 析构炸弹 | 46 | 很快（104） | 快速接近角色；**死亡时爆炸**，150 范围内角色受大量伤害 |
| WARD | 护盾守卫 | 170 | 很慢（26） | 不攻击，缓慢靠近；通过引用给哨兵提供 BUFF/护盾 |

- **所有敌人每帧选最近存活角色**，距离 > 攻击距离就持续移动，<= 攻击距离才停下攻击；
  SENTINEL/WARD 也会移动（只是慢），BOMB/MINION 更快；移动限制在战场内，敌人之间软分离。
- 防卡关检测：若场上仍有敌人、但所有敌人都没移动且没有任何敌人靠近角色超过 2.5s，记为 stalemate（smoke 断言必须为 0）。

### W3 引用网络与断连
- **SHARE（青，哨兵 ↔ 护盾守卫）**：哨兵受到的伤害 40% 转移给护盾守卫（伤害数字会显示 SHARE）。
- **BUFF（金，护盾守卫 → 哨兵）**：哨兵攻击 +50%、攻击间隔 -25%、受到伤害 -25%（护盾）。
- 底部唯一主动 **「断连」**：W1/W2 锁定；W3 首次出现弹窗后解锁；按住左键拖拽划过连线剪断；
  **只允许一次**。剪断 SHARE → 隔离，哨兵暴露（受到伤害 +40%）；剪断 BUFF → 哨兵失去增益/护盾。
- 若哨兵/护盾守卫任一被击破，引用网络自动中断。
- 引用连线与 SHARE/BUFF 视觉跟随节点实时位置。

---

## 6. 结算奖励（只展示）

W3 清空后进入结算界面，固定展示两张被动协议卡（**不进入 5×5，第二关再接入**）：

| 卡 | 效果 | 形状 | 颜色 |
| --- | --- | --- | --- |
| 攻击协议 | 全体攻击力 +10 | L 三格 `[(0,0),(0,1),(1,0)]` | 琥珀 |
| 防御协议 | 全体防御力 +10 | 2×2 四格 `[(0,0),(0,1),(1,0),(1,1)]` | 蓝色 |

界面文字：**「内存系统解锁 · 第二关开始装配」**；点击「结束本关」后显示完成页。
第一关仍无内存板、无升星、无大招；只有选角介绍与结算奖励。

---

## 7. UI / 操作

- **顶部**：左边标题为 **「内存远征 · 第一关」** + 小字 **`TUTORIAL // WAVE n/3`**；中间保留 WAVE 状态与
  **顶部目标条**（本波目标，W3 时显示 SHARE/BUFF 图例与断连拖拽提示）；右侧 FPS/自动战斗提示。
- **左侧 3 个角色小框**：高分辨率头像、名字、定位/技能类型、HP/护盾、当前状态、小技能冷却；
  点击小框或悬停战场角色显示该角色范围圈（蓝内圈固定 + 黄/绿外圈跟随，同一时间只显示一个）。
- **中间战场**：深蓝黑底 + 网格；不再有右侧暗红色大色块，敌方仅保留很淡的虚线边界与灰色「敌方区域」标签；
  小比例角色（统一视觉身高）自动移动/普攻/小技能；敌人 AI/HP/血条；投射物、伤害数字、
  爆炸/斩击/治疗特效；W3 引用网络（青/金箭头、SHARE/BUFF 标签、断线虚线×）。
- **右侧战斗面板**（沿用上一版面板/字体/边框/青金红语义）：
  - 顶部 **内存板**：5×5 mini board，第一关全部锁定（锁图标 + 「第一关未解锁」）；
  - **主动 / ACTIVE**：只列出「断连」；W1/W2 显示 `LOCKED`，W3 解锁后显示 `CD 0.0s`，使用后显示「已使用」；
  - **被动 / PASSIVE**：第一关显示「未装载」。
- **底部**：只放一个主动「断连」槽（锁定/就绪/已使用三态），无大招环、无其他主动；左侧波次进度，右侧提示。

| 操作 | 作用 |
| --- | --- |
| 点击左侧角色小框 / 悬停战场角色 | 显示该角色范围圈（蓝内圈固定 + 黄/绿外圈跟随） |
| 鼠标按住拖拽划过青色/金色连线（W3） | 断连，只允许一次 |
| 点击弹窗任意位置 | 继续（解除时停） |
| 全灭后点击弹窗按钮 | 重试当前波 |
| Esc | 退出 |
| F11 | 全屏/窗口切换 |

---

## 8. 测试与验证

```powershell
$env:SDL_VIDEODRIVER='dummy'; $env:SDL_AUDIODRIVER='dummy'
D:\Pygame\.venv\Scripts\python.exe tutorial_battle.py --smoke
# → TUTORIAL BATTLE SMOKE OK
```

smoke 自动：跳过所有弹窗 → 跑 3 波 → 执行一次拖拽剪线 → 点击结算按钮 → 截图并断言。覆盖：

- 3 角色均来自 manifest（无 fallback）；启动只 lazy load 6 clips；
- 直绘 s=4/3、战场角色 0.75×0.55=**0.413×** 源帧；三人各自在独立活动带内且最小间距 ≥ 40（smoke 实测 79.2）；
- 范围圈：Qwen 140/180、DeepSeek 170/260、Claude 150/250，三人都满足蓝内圈 < 黄/绿外圈（内蓝外黄）；Qwen 护盾/辅助判定范围 180；
- 战场角色按统一目标身高归一化：每角色源身高不同、绘制缩放不同，但渲染高度一致（smoke 断言误差 ≤1.5px）；
- 选角界面出现，悬停/点击角色卡显示说明；
- 右侧战斗面板：W1 时内存板锁定 / 被动未装载 / 断连 LOCKED，W3 解锁后主动栏显示 `CD 0.0s`，使用后「已使用」；
- 弹窗顺序与次数：`opening, w1, enemy_MINION, enemy_SENTINEL, enemy_BOMB, enemy_WARD, w3, cut`（共 8 个，每种新敌人只弹一次）；
- **弹窗期间战斗完全冻结**（time / wave_time / 角色与敌人位置不变），点击继续后恢复更新；
- 3 波全部清空、击破 7 个敌人、角色有自动普攻与小技能；
- W2/W3 敌人均主动进入射程并攻击、三波敌人都有移动、`stalemate_events == 0`；
- 范围圈：点击 Qwen 小框选中、悬停 DeepSeek 显示、点击 Claude 切绿色外圈、再次点击取消（同一时间只显示一个角色）；
- 断连只允许一次：第一次拖拽剪断 SHARE 成功，第二次尝试被拒绝；
- 结算界面两张被动卡（名称/效果/形状/颜色）与 `内存系统解锁` 文案；
- clip 缓存数量/字节在合理范围。

实测结果（dummy SDL，默认 2K 窗口）：

```
manifest=loaded waves=3 kills=7 basic=50 skills=20 cut=True modals=8
enemy_attacks=18 approached=[0, 1, 2] stalemate=0 cache=71.4MB shots=19
TUTORIAL BATTLE SMOKE OK
```

---

## 9. 截图（shots/tutorial_*.png）

| 文件 | 内容 |
| --- | --- |
| `tutorial_select.png` | 战前固定 3 人选角介绍界面（定位/技能类型/范围圈） |
| `tutorial_select_hover.png` | 悬停角色卡查看说明 |
| `tutorial_modal_opening.png` | 开场三固定角色弹窗 |
| `tutorial_modal_minion.png` | 新敌人「游标」弹窗 |
| `tutorial_modal_sentinel.png` | 新敌人「哨兵」弹窗 |
| `tutorial_modal_bomb.png` | 新敌人「析构炸弹」弹窗 |
| `tutorial_modal_ward.png` | 新敌人「护盾守卫」弹窗 |
| `tutorial_modal_w3_network.png` | SHARE/BUFF 引用网络弹窗 |
| `tutorial_modal_cut.png` | 断连操作弹窗 |
| `tutorial_range_qwen.png` / `_deepseek` / `_claude` | 选中/悬停范围圈（蓝内圈 + 黄/绿外圈） |
| `tutorial_wave1.png` / `_wave2` | W1 / W2 战斗（三角色分带、右侧内存板锁定/主动 LOCKED/被动未装载） |
| `tutorial_wave3.png` | W3 战斗总览（同 `tutorial_wave3_network.png`，便于按 W1/W2/W3 命名引用） |
| `tutorial_wave3_network.png` | W3 剪线前引用网络（右侧主动显示 CD 0.0s） |
| `tutorial_wave3_cut.png` | W3 剪断 SHARE 后（右侧主动已使用） |
| `tutorial_1080p.png` | 1080P 窗口（s=1.0，战场角色约 0.28× 源帧） |
| `tutorial_result_rewards.png` | W3 结算：两张被动协议卡 + 内存系统解锁 |
| `tutorial_complete.png` | 结束本关完成页 |
| `tutorial_smoke_final.png` | smoke 结束画面 |

---

## 10. 已知缺口 / 风险

1. **第二关内容不在本任务范围**：奖励卡只展示，不进入 5×5、不实际加属性；第二关再接入装配。
2. 没有音效；敌人/特效全部用 pygame 图元绘制（无外部美术）。
3. 战斗平衡是教学口径：角色自动战斗、数值偏简单，可能不是最终平衡；全灭可无限重试当前波。
4. 引用网络只有 W3 两条边；断连只支持“拖拽划过一条边”，不做多点/多边操作。
5. 交互模式 F11 全屏切换会按新物理尺寸重建 clip 缓存（dummy 下已验证不崩）；窗口自由 resize 未实现。
6. 敌人投射物/爆炸等特效为原型表现；后续可替换正式美术。
7. `--shot --start-wave 2/3` 是调试入口，会跳过选角与前置弹窗，只用于截图/调试。

---

## 11. 写范围

- 新增/修改：`tutorial_battle.py`、`docs/tutorial_battle.md`、`shots/tutorial_*.png`。
- **未修改** `character_lab.py`、`main.py`、`battle_demo.py`、`assets/` 及其他文件。
