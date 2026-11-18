# Character Lab：8 角色动画 / 移动 / 状态机验证原型

> task-9 交付。文件：`RE-AI-AutoChess/character_lab.py`（独立运行，不 import `main.py` / `battle_demo.py`，不修改 `assets/`）。
> 只做「角色动画 + 移动 + 状态机 + 特效文字」验证：**无敌人、无战斗数值**。
> 阅读顺序：`character_lab.py` → 本文 → `docs/resolution_plan.md`（2K 审计）→ `docs/pet_action_map.md`（动作映射）。

---

## 1. 快速开始

工作目录 `D:\Pygame\RE-AI-AutoChess`，使用项目 venv：

```powershell
D:\Pygame\.venv\Scripts\python.exe character_lab.py                       # 默认全屏（桌面 2560×1440 → 物理 2560×1440）
D:\Pygame\.venv\Scripts\python.exe character_lab.py --windowed            # 2560×1440 窗口
D:\Pygame\.venv\Scripts\python.exe character_lab.py --windowed --size 1920x1080
D:\Pygame\.venv\Scripts\python.exe character_lab.py --shot shots\character_lab_page1.png --time 1.8
D:\Pygame\.venv\Scripts\python.exe character_lab.py --native-timing      # 一遍性动作按源时序（≈10s）播放
```

无窗口 smoke / 截图（dummy SDL）：

```powershell
$env:SDL_VIDEODRIVER='dummy'; $env:SDL_AUDIODRIVER='dummy'
D:\Pygame\.venv\Scripts\python.exe character_lab.py --smoke
D:\Pygame\.venv\Scripts\python.exe character_lab.py --shot shots\character_lab_skills.png --time 0.9 --force-skills
D:\Pygame\.venv\Scripts\python.exe character_lab.py --shot shots\character_lab_skills_page2.png --page 2 --time 0.62 --force-skills
D:\Pygame\.venv\Scripts\python.exe character_lab.py --shot shots\character_lab_ult.png --time 0.9 --force-ults --ult-slot 1
D:\Pygame\.venv\Scripts\python.exe character_lab.py --shot shots\character_lab_page2.png --page 2 --time 1.8
D:\Pygame\.venv\Scripts\python.exe character_lab.py --shot shots\character_lab_1080p.png --size 1920x1080 --time 1.8
```

---

## 2. 分辨率策略（按 2K 审计结论：**直绘、不上采样**）

结论来自 `docs/resolution_plan.md` §4：**1920×1080 逻辑档 + 按窗口物理像素直绘，默认窗口 2560×1440（s=4/3）**。
本实现**没有**「1920 canvas 再整体 `transform.scale`」的路径。

| 项目 | 实现 |
| --- | --- |
| 逻辑坐标系 | 1920×1080（布局/坐标/字号全部写逻辑值） |
| 窗口 | 默认全屏（本机桌面 2560×1440）；`--windowed` / `--size WxH` 指定窗口物理尺寸 |
| 绘制目标 | **窗口 surface 本身**；`Painter` 把逻辑坐标映射为物理像素：`phys = round(logical × s) + offset`，非 16:9 窗口 letterbox 居中 |
| 缩放系数 | `s = min(win_w/1920, win_h/1080)`；2K 窗口 s=4/3，1080P 窗口 s=1 |
| 文字 | 按物理字号 `round(size × s)` 现场 `font.render(...)`；2K 下更大更清晰，**不做位图放大** |
| 每角色区域 | 480×270 逻辑 → **2K：640×360 物理 = 源帧 1:1（零重采样）**；1080P：480×270 物理（0.75× smooth 下采样） |
| 精灵帧缓存 | 按**最终物理尺寸**建；2K 下直接 `copy` 源像素，1080P 下 `smoothscale` 一次；**永不放大** |
| 上采样保护 | `sprite_scale = min(1.0, 480·s/640, 270·s/360)`，上限 1:1；窗口 >2K 时精灵 1:1 封顶并在 HUD/控制台提示「降级、不上采样」 |
| 截图 | `--shot` 输出**窗口物理分辨率**（默认 2560×1440），真实反映 2K 观感；`--size 1920x1080` 输出 1080P 基线 |
| 禁止项 | ❌ 整幅 canvas 放大；❌ 源帧上采样；❌ 先缩 160×90 再放大 |

取整约定：几何坐标统一 `round`；线宽 `max(1, round(width×s))`，避免 0.5 物理像素。
2K 下 s=4/3 为非整数，但精灵 1:1、文字按物理字号渲染，整体清晰；1px 边框按物理像素取整后视觉均匀。

---

## 3. 内存策略（只缓存可见角色，**禁止 8×4 全预载**）

审计测算：8 角色 × 4 动作 × 120 帧全预载约 **3.4GB**，不可行。本实现：

1. **启动只加载当前页 4 个可见角色的 `idle + move`**；`skill` / `ult` 第一次触发时才懒加载。
2. **翻页时**先释放隐藏角色引用、清空旧页 clip 缓存，再加载新页 idle+move（真正 lazy）。
3. **LRU 软上限 512MB**（`OrderedDict`，`CLIP_CACHE_CAP_BYTES`）：可见角色当前/交叉淡化中的 clip 受保护，超出时淘汰最久未用的非保护 clip。
4. 帧缓存尺寸 = 最终物理绘制尺寸；预计算 pivot（脚底锚点）与逐帧 alpha bbox，绘制时不做缩放。
5. 交叉淡化结束后立即释放上一 clip 引用，让缓存可回收。

实测（dummy SDL、默认 2K 窗口、真实 manifest）：

| 场景 | clip 加载数 | 缓存 |
| --- | --- | --- |
| 启动（page1 idle+move，4 角色 × 2 动作，各 120 帧 1:1） | 8 | **336.6MB** |
| 1080P 窗口启动（0.75× 下采样，idle+move） | 8 | **189.7MB** |
| skills 截图（强制 4 角色技能，含 skill clip） | 12 | **533.3MB** |
| smoke 全流程（两页 + 技能 + 大招 + 输入 + 移动验证） | 75（含翻页重载） | **峰值 536.7MB**，淘汰 28 次 |
| fallback 模式（8 角色共用 dsh 动作） | 6 | 143.0MB |

> 峰值略高于 512MB 是因为活动 clip 受保护、不可立即淘汰（瞬时多一个 clip）；属于软上限。缓存从未接近全预载量级。

HUD 底部实时显示 `clip cache xxMB / 512MB · loads · evict · sprite 模式 · one-shot 策略`，便于观察。

---

## 4. 资源：lab_manifest.json（已接入，正式路径）

### 4.1 manifest 状态（2026-11-18 21:28 落盘）
- 路径：`assets/pets/lab_manifest.json`（136,667 B，UTF-8，task-8 pet-assets 生成）。
- 本实现启动即加载；HUD 显示 `manifest OK · 8 roles [...] · assets/pets/lab_manifest.json`。
- 控制台输出（每次启动）：

```
[manifest] OK · 8/8 roles from D:\Pygame\RE-AI-AutoChess\assets\pets\lab_manifest.json
[manifest] loaded: dsh「蓝毛小女仆」 gpt「GPT」 claude「Claude」 gemini「Gemini」 qwen「Qwen」 glm「GLM」 grok「Grok」 kimi「Kimi」
[manifest] actions complete: 32/32 (idle/move/skill/ult × 8 roles)
```

### 4.2 实际加载的 8 个角色（全部来自 manifest，无角色级 fallback）

| id | 名字 | 颜色 | skill 类型 | skill 动作 | ult 类型 | ult 动作 |
| --- | --- | --- | --- | --- | --- | --- |
| dsh | 蓝毛小女仆 | `#5676D2` | attack 攻击 | 鲸鱼吐泡泡特效 | summon | 蓝鲸现世 |
| gpt | GPT | `#C4D8F6` | attack 攻击 | 用龙尾拍打地面 | summon | 白龙现世 |
| claude | Claude | `#E88848` | heal 治疗 | 凭空生花 | summon | 书灵现世 |
| gemini | Gemini | `#9688E8` | attack 攻击 | 嘟嘴吹泡泡特效 | summon | 星星精灵现世 |
| qwen | Qwen | `#8898D8` | shield 护盾 | 优雅折扇舞 | summon | 徽章灵雀现世 |
| glm | GLM | `#4C60A0` | attack 攻击 | 用蓬松狐尾拍打地面 | summon | 小蓝狐现世 |
| grok | Grok | `#F8D8A8` | shield 护盾 | 小魔女吐泡泡特效 | summon | 小金蝠现世 |
| kimi | Kimi | `#E8CCF0` | heal 治疗 | 写星月图 | summon | 小星灵现世 |

- 每个角色 `idle / move / skill / ult` 各 1 段：源帧 640×360、8×15 图集、`fps=12`、`frame_count=120`、`start=0/end=120/step=1`、idle/move `loop=true`、skill/ult `loop=false`。
- **动作完整性：32/32，无缺失动作**（pet-assets 自检 `assets/pets/verify_manifest.py` + 本 lab 加载器均通过）。
- 解析器对结构容错：根 `characters`/`pets`/`roles`/数组；字段 `id/name/color/colorHex/skill_type/ult_type/actions|animations`；动作字段 `file/webp/json/fps/frame_count/frames/columns/rows/frame_width/frame_height/start/end/step/loop/name`；路径相对项目根或 manifest 目录；`dsh/dsh1` 自动合并为 dsh、顺序固定 8 个。
- 若某角色单个动作文件缺失：**该动作**逐动作用 dsh fallback，并在控制台/HUD warning 中明确列出角色与动作（不会静默全变 dsh，也不会角色级回退）；本次 manifest 无缺失，故无该降级。

### 4.3 dsh 本地 fallback（仅 manifest 不存在/单动作缺失时兜底）
`assets/chars/ds/`（项目内本地 dsh 资源）：

| 动作 | 源文件 | 切片（start,end,step） | fps | 循环 |
| --- | --- | --- | --- | --- |
| idle | 待机呼吸休闲 | 0,120,1 | 24 | ✅ |
| move | 原地漂浮踏步 | 8,112,1 | 24 | ✅ |
| attack（skill） | 原地跳跃抓碎头顶物品 | 8,96,2 | 30 | ❌ |
| heal（skill） | 鲸鱼吐泡泡特效 | 36,86,2 | 30 | ❌ |
| shield（skill） | 被鼠标拖拽悬空反馈 | 24,112,2 | 30 | ❌ |
| ult | 蓝鲸现世 | 24,104,2 | 40 | ❌ |

manifest 不存在时 8 个角色共用这套 dsh 动作（颜色/名字/技能类型不同），HUD 标注 fallback；manifest 落盘后自动切换，无需改代码。

---

## 5. 动画 / 状态机 / 动作时序

- 每角色状态：`idle → move → skill → move/idle`；`ult` 玩家主动，播完回 `idle`。
- 动作播放：循环动作（idle/move）按 fps 循环；单次动作（skill/ult）播一遍，`done` 后立即交叉淡化回 idle。
- **不会停在最后一帧、不会硬切**：切换时保留上一帧（prev surface + pivot + facing）做 0.12~0.18s alpha 交叉淡化；淡化结束释放上一 clip。
- **Lab 动作时序策略**：manifest 的 skill/ult 是完整的 120 帧 @12fps（约 10s）。为了让状态机/移动可观察，默认把一遍性动作按播放速度加速到
  **skill ≤2.4s、ult ≤3.2s**（不裁帧、不改尺寸、不改源 fps 字段；HUD 动作名旁显示 `×4.2`/`×3.1` 倍速）。
  实测 skill 状态最长 2.42s、ult 最长 3.18s。
  `--native-timing` 可关闭加速、严格按 manifest 源时序（每个动作 ≈10s）播放。
- 自动小技能：冷却 5~8.5s；触发时冻结移动、播 skill 动作、生成范围特效 + 浮动文字；播完回 idle。
- ULT：点击角色 / `1-4`（当前页槽位）/ `U`（全屏大招）触发；**冷却 12s、不消耗能量**；冷却中触发只记录日志并闪一下。
- 小技能三类（无敌人，只播动作 + 范围特效 + 文字）：
  - `attack`：面向方向的橙色斩击弧 + 火花 + `攻击 · <动作名>`；
  - `heal`：脚下绿色扩散环 + 上升十字 + `治疗 · <动作名>`；
  - `shield`：六边形护盾罩 + 内圈高光 + `护盾 · <动作名>`。
  技能类型分配来自 manifest（attack=dsh/gpt/gemini/glm，heal=claude/kimi，shield=qwen/grok）——
  两页各 4 角色都覆盖三类；`T` 还可切换 ROLE / CYCLE / RANDOM 模式。
- 大招表现：manifest 的 ult 动画本身已含「…现世」召唤演出，Lab 只叠加地面光环/光柱/粒子/`ULT · <大招名>` 文字，避免和源动画重复。
  `ult_type` 兼容 summon/aoe/buff 三类通用表现（当前 manifest 8 个角色均为 summon）。
- 移动与软分离：
  - 每个角色在「活动区间」内左右往返（lane 中心 ±258 逻辑，相邻区间有重叠边界）；
  - 相邻角色最小间距 `MIN_GAP = 224` 逻辑，迭代 2 次对称推开并 clamp 回区间，用于演示软分离（HUD 调试线显示 `gap / min`）；
  - 左右翻转按移动方向 flip；脚底锚点用源帧最低脚底帧预计算，所有动作脚不离地。

---

## 6. 界面 / 调试显示

- **顶部角色条**：8 张卡（名字 / id / 颜色 / 技能类型 / ULT READY 或剩余 CD）；当前页 4 张高亮；
  点卡片或 `◀ ▶` / `Tab` / `Q` `E` 翻页查看全部 8 个角色。
- **角色面板**（每 lane 固定列，避免相邻压字）：名字、id、状态 `IDLE/MOVE/SKILL/ULT`、
  **当前动作名 + 帧号 n/N**（加速时附 `×倍速`）、技能类型、ULT 冷却 / 大招名、动作进度条。
- **脚底锚点 / 活动区间调试框**（默认开，`D` 切换）：
  - 每角色 480×270 逻辑 zone 框；
  - 活动区间虚线框 + 左右端点数值；
  - 脚底 anchor 十字 + 圆点；
  - 当前帧 alpha bbox 框；
  - 相邻角色 `gap / min` 距离线（绿色达标 / 琥珀不足）。
- **底部 HUD**：FPS、clock、debug/paused 状态、`energy ∞ · ULT 无消耗 · CD 12s`、
  manifest 状态与 8 角色 id、auto-skill 模式、当前页/可见角色、clip cache 用量/加载/淘汰、sprite 模式、one-shot 策略、
  warning（动作缺失降级提示）、事件日志（最近 4 条）、操作提示。
- **操作**：

| 键 | 作用 |
| --- | --- |
| `1-4` / 点击角色 | 当前页对应槽位放大招（有冷却） |
| `U` | 全屏 4 个角色一起放大招 |
| `A` | 立即触发 4 个可见角色的小技能 |
| `Tab` / `Q` `E` / `◀ ▶` | 翻页（两页各 4 个角色） |
| `T` | 技能类型模式 ROLE / CYCLE / RANDOM |
| `D` | 调试框开/关 |
| `R` | 重置位置/状态/特效 |
| `Space` | 暂停/继续 |
| `F11` | 全屏/窗口切换（切换后按新物理尺寸重建 clip 缓存） |
| `Esc` | 退出 |

---

## 7. 截图（shots/character_lab_*.png，全部为窗口物理分辨率）

| 文件 | 物理尺寸 | 内容 |
| --- | --- | --- |
| `character_lab_page1.png` | 2560×1440 | 第一页 4 个不同角色 dsh/GPT/Claude/Gemini（idle/move，manifest 正常态） |
| `character_lab_page2.png` | 2560×1440 | 第二页 4 个不同角色 Qwen/GLM/Grok/Kimi |
| `character_lab_skills.png` | 2560×1440 | 第一页 4 角色同时小技能（attack/heal 特效 + 文字） |
| `character_lab_skills_page2.png` | 2560×1440 | 第二页 4 角色同时小技能（shield 六边形 / attack 斩击 / heal 环，三类全覆盖） |
| `character_lab_ult.png` | 2560×1440 | dsh 大招「蓝鲸现世」（源动画召唤演出 + 地面光环/光柱 + ULT 文字 + CD） |
| `character_lab_1080p.png` | 1920×1080 | 1080P 窗口基线：s=1，精灵 0.75× smooth 下采样（验证不放大） |
| `character_lab_smoke_*.png` | 2560×1440 | smoke 自动抓拍：skills/ult/page2_skills/page2_ult/stage/final |

---

## 8. 测试与验证

### 8.1 无窗口 smoke（真实 manifest）

```powershell
$env:SDL_VIDEODRIVER='dummy'; $env:SDL_AUDIODRIVER='dummy'
D:\Pygame\.venv\Scripts\python.exe character_lab.py --smoke
# → CHARACTER LAB SMOKE OK
```

实测结果（dummy SDL、默认 2K 窗口、1400+ 帧 smoke，墙钟约 35s）：

```
roles=8 unique=8 manifest=loaded window=(2560,1440) s=1.333 sprite_scale=1.000
cache_now=336.6MB cache_peak=536.7MB loads=75 evictions=28 shots=6
oneshot_speeds=[3.12, 4.17]
CHARACTER LAB SMOKE OK
```

断言覆盖：

- 窗口物理尺寸 2560×1440、s=4/3、2K 下 sprite 1:1（源帧 640×360，无上采样）；
- **manifest 已加载、8 角色全部来自 manifest（无角色级 fallback）、角色 id 唯一且顺序固定、动作 32/32 完整**；
- 启动只加载当前页 idle+move 共 8 clip（不是 8×4 全预载）；帧物理尺寸 ≤640×360；
- 两页各 4 个可见角色；`Tab` 翻页、`1-4`/鼠标点击大招等输入路径；
- 8 个角色都观察到 `idle / skill / ult`，并通过显式移动阶段验证 8 个角色都会进入 `move`（两页各 150 帧无技能干扰）；
- 动作播完回 idle/move、不停在最后一帧；交叉淡化被观察到（8 角色）；
- 一遍性动作默认加速：observed speed=[3.12, 4.17]，skill 状态 ≤2.42s、ult ≤3.18s；
- 缓存当前 ≤512MB 软上限、峰值 536.7MB < 1GB（对比全预载 ≈3.4GB）；
- 1080P 下 sprite scale=0.75 公式成立（下采样，不上采样）。

### 8.2 截图命令（dummy SDL）

见 §1；每次输出形如：

```
SHOT OK shots\character_lab_page1.png  physical=2560x1440  logical=1920x1080  roles=8  page=1
manifest=yes  sprite 1:1 (2K target, zero resample)  time=1.82s  clip_cache=336.6MB
```

---

## 9. 已知缺口 / 风险

1. **动作时序是 Lab 演示口径**：manifest 的 skill/ult 是完整 10s 动作，默认加速到 ≤2.4s/≤3.2s 以便观察状态机；需要严格动画审片时用 `--native-timing`。
2. `ult_type` 当前 manifest 8 角色全是 `summon`，所以 aoe/buff 两套表现暂未在真实数据上演示（代码路径已实现）；如后续要区分，只需改 manifest 数据。
3. 无音效、无立绘/portrait 缩略图（顶部角色条用颜色+文字，不使用外部美术；资源里只有 dsh/claude portrait）。
4. 交互模式 `F11` 切换会重建 clip 缓存（代码路径已实现，dummy 下已验证切换不崩）；窗口自由 resize 未实现（与主游戏现状一致）。
5. 非 16:9 窗口 letterbox 居中；窗口物理尺寸 >2K 时精灵按 1:1 封顶（HUD/控制台降级提示，不上采样）。
6. 缓存是 512MB 软上限：活动 clip 受保护时峰值可瞬时 ~537MB（见 §3），不是硬性内存墙；若需要更保守可调小 `CLIP_CACHE_CAP_BYTES`。
7. manifest 解析器做了常见结构容错；pet-assets 后续若改 schema 需再联调一次（当前真实 manifest 已通过 8 角色/32 动作全量加载）。

---

## 10. 写范围

- 新增/修改：`character_lab.py`、`docs/character_lab.md`、`shots/character_lab_*.png`。
- **未修改** `main.py`、`battle_demo.py`、`assets/`（含 `assets/pets/`）、`docs/resolution_plan.md` 及其他文件。
