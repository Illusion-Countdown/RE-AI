# Character Lab 动作资源映射（task-8）

> 本文档由 task-8 资产子代理生成，与 `assets/pets/lab_manifest.json` 同步。
> 数据源仓库：[hunmer/aboutme-pets](https://github.com/hunmer/aboutme-pets) @ `ee29ca4abb489e9257f41ab889a1db115323a267`（main）。

## 1. 交付概览

- **唯一角色 8 个**：`dsh`（`dsh` + `dsh1` 合并为一个角色）、`gpt`、`claude`、`gemini`、`qwen`、`glm`、`grok`、`kimi`。
- **每角色 4 个动作**：`idle` / `move` / `skill` / `ult`，合计 **32 个动作 = 32 个 webp + 32 个动作 json**。
- **素材总量**：58,996,706 字节 ≈ 56.26 MiB（webp 58,975,518 字节，json 21,188 字节）。
- **Manifest**：`assets/pets/lab_manifest.json`（同时提供 `pets` 与 `characters` 两个等价视图，供 Character Lab 直接消费）。
- **自检脚本**：`assets/pets/verify_manifest.py`（pygame 实际解码 + 切帧，重跑可复核 8 角色 × 4 动作）。
- **动作来源**：
  - `dsh`：本地 `D:\Pygame\aboutme-pets\pets\dsh\spritesheet`（优先本地，未联网）。
  - 其余 7 角色：GitHub raw 镜像下载（`ghfast.top` / `cdn.jsdelivr.net` / `gh-proxy.com`），**每个文件均与源仓库 git blob SHA-1 逐一比对通过**。
  - 所有动作名都可在角色包 `actions.json`（本地已下载到 `meta/<id>-actions.json`）中核实，无编造动作。

### 每角色素材大小

| 角色 | 动作数 | webp 字节 | 该角色合计 |
| --- | ---: | ---: | ---: |
| 蓝毛小女仆 (`dsh`) | 4 | 3,976,364 | 3.79 MiB |
| GPT (`gpt`) | 4 | 5,968,210 | 5.69 MiB |
| Claude (`claude`) | 4 | 7,941,144 | 7.58 MiB |
| Gemini (`gemini`) | 4 | 7,956,426 | 7.59 MiB |
| Qwen (`qwen`) | 4 | 8,240,038 | 7.86 MiB |
| GLM (`glm`) | 4 | 8,323,376 | 7.94 MiB |
| Grok (`grok`) | 4 | 8,350,556 | 7.97 MiB |
| Kimi (`kimi`) | 4 | 8,219,404 | 7.84 MiB |
| **合计** | **32** | **58,975,518** | **56.26 MiB** |

## 2. 资源规格与目录约定

- 精灵图：单个 webp 为 RGBA 透明拼贴图，**8 列 × 15 行 = 120 帧**，单帧 **640×360**，`SampleFps = 12`，整图 5120×5400。
- 动作 json：与 webp 同目录同名，字段 `Source / FrameWidth / FrameHeight / Columns / Rows / FrameCount / SampleFps / ImageFormat / License` 等。
- 目录结构：

```
assets/pets/
├── lab_manifest.json
├── dsh/idle/idle.webp + idle.json      # 每角色 4 个动作目录：idle/ move/ skill/ ult/
│   ├── move/move.webp + move.json
│   ├── skill/skill.webp + skill.json
│   └── ult/ult.webp + ult.json
├── gpt/… claude/… gemini/… qwen/… glm/… grok/… kimi/…
```

- manifest 内路径均相对项目根目录 `D:\Pygame\RE-AI-AutoChess`。
- 循环约定：`idle`、`move` 为循环（`loop: true`）；`skill`、`ult` 播放一次后回 idle（`loop: false`）。

## 3. 角色动作映射总表

| 角色 | id | 槽位 | 原始动作名（actions.json 可核实） | 原分类 | 帧数 / FPS | 文件 |
| --- | --- | --- | --- | --- | ---: | --- |
| 蓝毛小女仆 | `dsh` | `idle` | 待机呼吸休闲 | 待机 | 120 / 12 | `assets/pets/dsh/idle/idle.webp` |
| 蓝毛小女仆 | `dsh` | `move` | 螃蟹走路 | 移动 | 120 / 12 | `assets/pets/dsh/move/move.webp` |
| 蓝毛小女仆 | `dsh` | `skill` | 鲸鱼吐泡泡特效 | 玩耍 | 120 / 12 | `assets/pets/dsh/skill/skill.webp` |
| 蓝毛小女仆 | `dsh` | `ult` | 蓝鲸现世 | 玩耍 | 120 / 12 | `assets/pets/dsh/ult/ult.webp` |
| GPT | `gpt` | `idle` | 待机呼吸休闲 | 待机 | 120 / 12 | `assets/pets/gpt/idle/idle.webp` |
| GPT | `gpt` | `move` | 原地漂浮踏步 | 移动 | 120 / 12 | `assets/pets/gpt/move/move.webp` |
| GPT | `gpt` | `skill` | 用龙尾拍打地面 | 龙族特性 | 120 / 12 | `assets/pets/gpt/skill/skill.webp` |
| GPT | `gpt` | `ult` | 白龙现世 | 龙族特性 | 120 / 12 | `assets/pets/gpt/ult/ult.webp` |
| Claude | `claude` | `idle` | 待机呼吸休闲 | 待机 | 120 / 12 | `assets/pets/claude/idle/idle.webp` |
| Claude | `claude` | `move` | 原地漂浮踏步 | 移动 | 120 / 12 | `assets/pets/claude/move/move.webp` |
| Claude | `claude` | `skill` | 凭空生花 | 才艺表演 | 120 / 12 | `assets/pets/claude/skill/skill.webp` |
| Claude | `claude` | `ult` | 书灵现世 | 魔法特效 | 120 / 12 | `assets/pets/claude/ult/ult.webp` |
| Gemini | `gemini` | `idle` | 待机呼吸休闲 | 待机 | 120 / 12 | `assets/pets/gemini/idle/idle.webp` |
| Gemini | `gemini` | `move` | 原地漂浮踏步 | 移动 | 120 / 12 | `assets/pets/gemini/move/move.webp` |
| Gemini | `gemini` | `skill` | 嘟嘴吹泡泡特效 | 娱乐休闲 | 120 / 12 | `assets/pets/gemini/skill/skill.webp` |
| Gemini | `gemini` | `ult` | 星星精灵现世 | 魔法特效 | 120 / 12 | `assets/pets/gemini/ult/ult.webp` |
| Qwen | `qwen` | `idle` | 待机呼吸休闲 | 待机 | 120 / 12 | `assets/pets/qwen/idle/idle.webp` |
| Qwen | `qwen` | `move` | 原地左转奔跑 | 移动 | 120 / 12 | `assets/pets/qwen/move/move.webp` |
| Qwen | `qwen` | `skill` | 优雅折扇舞 | 玩耍 | 120 / 12 | `assets/pets/qwen/skill/skill.webp` |
| Qwen | `qwen` | `ult` | 徽章灵雀现世 | 玩耍 | 120 / 12 | `assets/pets/qwen/ult/ult.webp` |
| GLM | `glm` | `idle` | 待机呼吸休闲 | 待机 | 120 / 12 | `assets/pets/glm/idle/idle.webp` |
| GLM | `glm` | `move` | 原地漂浮踏步 | 移动 | 120 / 12 | `assets/pets/glm/move/move.webp` |
| GLM | `glm` | `skill` | 用蓬松狐尾拍打地面 | 情绪 | 120 / 12 | `assets/pets/glm/skill/skill.webp` |
| GLM | `glm` | `ult` | 小蓝狐现世 | 特效 | 120 / 12 | `assets/pets/glm/ult/ult.webp` |
| Grok | `grok` | `idle` | 待机呼吸休闲 | 待机 | 120 / 12 | `assets/pets/grok/idle/idle.webp` |
| Grok | `grok` | `move` | 原地漂浮踏步 | 移动 | 120 / 12 | `assets/pets/grok/move/move.webp` |
| Grok | `grok` | `skill` | 小魔女吐泡泡特效 | 特效 | 120 / 12 | `assets/pets/grok/skill/skill.webp` |
| Grok | `grok` | `ult` | 小金蝠现世 | 特效 | 120 / 12 | `assets/pets/grok/ult/ult.webp` |
| Kimi | `kimi` | `idle` | 待机呼吸休闲 | 待机 | 120 / 12 | `assets/pets/kimi/idle/idle.webp` |
| Kimi | `kimi` | `move` | 原地漂浮踏步 | 移动 | 120 / 12 | `assets/pets/kimi/move/move.webp` |
| Kimi | `kimi` | `skill` | 写星月图 | 才艺 | 120 / 12 | `assets/pets/kimi/skill/skill.webp` |
| Kimi | `kimi` | `ult` | 小星灵现世 | 特效 | 120 / 12 | `assets/pets/kimi/ult/ult.webp` |

## 4. 技能类型与大招分配

> 说明：源 `actions.json` **没有战斗技能/大招分类**，`skill`/`ult` 是按动作语义替代选出的（小技能取“特效/才艺/玩耍/龙族特性/情绪”类动作，大招统一取各角色「…现世」召唤动作）。技能类型由本任务按角色气质指定。

| 角色 | skill 类型 | skill 动作 | ult 类型 | ult 动作 | ult 说明 |
| --- | --- | --- | --- | --- | --- |
| 蓝毛小女仆 (`dsh`) | 攻击 attack | 鲸鱼吐泡泡特效（`assets/pets/dsh/skill/skill.webp`） | 召唤 summon | 蓝鲸现世（`assets/pets/dsh/ult/ult.webp`） | 召唤蓝鲸（水泡/鲸鱼主题） |
| GPT (`gpt`) | 攻击 attack | 用龙尾拍打地面（`assets/pets/gpt/skill/skill.webp`） | 召唤 summon | 白龙现世（`assets/pets/gpt/ult/ult.webp`） | 召唤白龙（龙族主题） |
| Claude (`claude`) | 治疗 heal | 凭空生花（`assets/pets/claude/skill/skill.webp`） | 召唤 summon | 书灵现世（`assets/pets/claude/ult/ult.webp`） | 召唤书灵（书本/书页主题） |
| Gemini (`gemini`) | 攻击 attack | 嘟嘴吹泡泡特效（`assets/pets/gemini/skill/skill.webp`） | 召唤 summon | 星星精灵现世（`assets/pets/gemini/ult/ult.webp`） | 召唤星星精灵（猫耳/星星主题） |
| Qwen (`qwen`) | 护盾 shield | 优雅折扇舞（`assets/pets/qwen/skill/skill.webp`） | 召唤 summon | 徽章灵雀现世（`assets/pets/qwen/ult/ult.webp`） | 召唤徽章灵雀（折扇/徽章主题） |
| GLM (`glm`) | 攻击 attack | 用蓬松狐尾拍打地面（`assets/pets/glm/skill/skill.webp`） | 召唤 summon | 小蓝狐现世（`assets/pets/glm/ult/ult.webp`） | 召唤小蓝狐（蓝狐耳娘主题） |
| Grok (`grok`) | 护盾 shield | 小魔女吐泡泡特效（`assets/pets/grok/skill/skill.webp`） | 召唤 summon | 小金蝠现世（`assets/pets/grok/ult/ult.webp`） | 召唤小金蝠（小魔女主题） |
| Kimi (`kimi`) | 治疗 heal | 写星月图（`assets/pets/kimi/skill/skill.webp`） | 召唤 summon | 小星灵现世（`assets/pets/kimi/ult/ult.webp`） | 召唤小星灵（星芒主题） |

## 5. 角色配色

`color` 取 idle 首帧头部区域的主色聚类，再为深色背景 UI 提亮/去灰校准（同一表也写入 manifest 的 `color` / `colorHex`）。

| 角色 | manifest color (RGB) | HEX | 首帧主色聚类 | 备注 |
| --- | --- | --- | --- | --- |
| 蓝毛小女仆 (`dsh`) | `[86, 118, 210]` | `#5676D2` | `#485898` | 深蓝长发 → 提亮 |
| GPT (`gpt`) | `[196, 216, 246]` | `#C4D8F6` | `#E8E8E8` | 银白长发 + 白龙主题 → 冷白 |
| Claude (`claude`) | `[232, 136, 72]` | `#E88848` | `#E88848` | 橙色长发（接近原色） |
| Gemini (`gemini`) | `[150, 136, 232]` | `#9688E8` | `#8888E8` | 薰衣草紫猫耳娘（接近原色） |
| Qwen (`qwen`) | `[136, 152, 216]` | `#8898D8` | `#8898D8` | 浅蓝紫发（接近原色） |
| GLM (`glm`) | `[76, 96, 160]` | `#4C60A0` | `#282838` | 深藏青发色 + 蓝狐耳 → 深蓝灰 |
| Grok (`grok`) | `[248, 216, 168]` | `#F8D8A8` | `#F8D8A8` | 奶油金双马尾（接近原色） |
| Kimi (`kimi`) | `[232, 204, 240]` | `#E8CCF0` | `#F8E8F8` | 银白发 + 星芒 → 粉紫白 |

## 6. 素材来源与许可

| 角色 | 角色包 / 上游 | 素材许可 | 依据 |
| --- | --- | --- | --- |
| dsh | `dsh-pet`（+ `dsh1-pet` 合并展示）· 上游 [PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet) commit `b78e3fcf` | 素材禁止商用；二创公开渠道须署名上游仓库（代码 MIT） | `pets/dsh/NOTICE.txt`、`SOURCE-upstream.txt`、`LICENSE-code.txt`、动作 JSON `License` 字段 |
| gpt | `gpt-pet` · 由 hunmer/aboutme-pets 生成 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)：署名 + 非商业 + 相同方式共享（基础立绘 © lokicorvus/crosspet） | `README.md`「来源与许可」、动作 JSON `License` 字段 |
| claude | `claude-pet` · 由 hunmer/aboutme-pets 生成 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)：署名 + 非商业 + 相同方式共享（基础立绘 © lokicorvus/crosspet） | `README.md`「来源与许可」、动作 JSON `License` 字段 |
| gemini | `gemini-pet` · 由 hunmer/aboutme-pets 生成 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)：署名 + 非商业 + 相同方式共享（基础立绘 © lokicorvus/crosspet） | `README.md`「来源与许可」、动作 JSON `License` 字段 |
| qwen | `qwen-pet` · 由 hunmer/aboutme-pets 生成 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)：署名 + 非商业 + 相同方式共享（基础立绘 © lokicorvus/crosspet） | `README.md`「来源与许可」、动作 JSON `License` 字段 |
| glm | `glm-pet` · 由 hunmer/aboutme-pets 生成 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)：署名 + 非商业 + 相同方式共享（基础立绘 © lokicorvus/crosspet） | `README.md`「来源与许可」、动作 JSON `License` 字段 |
| grok | `grok-pet` · 由 hunmer/aboutme-pets 生成 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)：署名 + 非商业 + 相同方式共享（基础立绘 © lokicorvus/crosspet） | `README.md`「来源与许可」、动作 JSON `License` 字段 |
| kimi | `kimi-pet` · 由 hunmer/aboutme-pets 生成 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)：署名 + 非商业 + 相同方式共享（基础立绘 © lokicorvus/crosspet） | `README.md`「来源与许可」、动作 JSON `License` 字段 |

- 每个动作 json 的 `License` 字段原文：`Non-commercial; attribution required. See NOTICE.txt and SOURCE-upstream.txt.`
- **本套素材仅可用于非商业原型/演示，公开使用须署名上游仓库与 crosspet。**

## 7. 缺口与替代说明

1. actions.json 没有独立的 skill/ult 分类：skill 从 特效/才艺/玩耍/龙族特性 等动作语义替代，ult 统一选各角色「...现世」召唤动作。
2. dsh1 新动作包未单独成为角色（按要求与 dsh 合并为一个 dsh），本 manifest 只使用 dsh 本地动作。
3. 所有选中动作为 12fps、120 帧、8 列 × 15 行、单帧 640x360；Lab 若需降采样请按 fps 抽帧。
4. 未下载音频（.m4a）：Character Lab 原型不需要音轨。

补充说明：

- **没有角色缺动作**：8 个角色的 idle/move/skill/ult 全部齐全，无占位、无缺帧。
- **动作名替代而非编造**：`skill`/`ult` 使用动作包中真实存在的动作名，只是其原分类不是「技能」；映射见第 4 节。
- **dsh1 已合并**：`dsh1-pet` 的 167 个动作未单独进入 Lab，`dsh` 使用原 `dsh` 包的本地动作；后续若想给 dsh 换新动作，可从 `dsh1` 替换同槽位。
- **音频未下载**：源仓库部分动作带 AAC 音轨，Character Lab 原型不需要音轨，未包含。
- **未全量下载**：按需求只取每角色 4 个动作，未下载其余 ~1000 个动作。

## 8. 校验与测试结果

| 项目 | 结果 |
| --- | --- |
| 文件完整性（webp+json 与源仓库 git blob SHA-1 比对） | **64/64 全部匹配** |
| 单帧尺寸 / 拼贴尺寸 | **32/32 通过**（640×360，8×15 拼贴 = 5120×5400） |
| 帧数一致性（`FrameCount` vs 拼贴可切帧数） | **32/32 通过**（各 120 帧） |
| 动作名核实（对 `meta/<id>-actions.json`） | **32/32 通过** |
| pygame 实际解码 + 切帧（首/中/尾帧 subsurface） | **96 次切帧全部成功**（pygame-ce 2.5.8，dummy 显示驱动） |

测试命令（已通过）：

```powershell
cd D:\Pygame\RE-AI-AutoChess
D:\Pygame\.venv\Scripts\python.exe assets\pets\verify_manifest.py
# 输出：LAB MANIFEST READ TEST OK: 8 characters x 4 actions, all sheets/frames/slices decoded
```

## 9. 给 Character Lab 的接入提示

- 读 `assets/pets/lab_manifest.json`，用 `characters`（或 `pets`，两者内容相同）取 8 个角色；每角色 `actions` 里有 4 个槽位。
- 每个动作可直接用：`pygame.image.load(a['file'])`，按 `a['frame_width'] / a['frame_height'] / a['columns']` 切帧；或按 `a['start'] / a['end'] / a['step']` 抽帧，帧率 `a['fps']`，循环 `a['loop']`。
- 角色主色用 `color`（[r,g,b]）或 `colorHex`；技能类型 `skill`/`skill_type`，大招类型 `ult_type`。
- 动作 json 中另有 `webm` 原始视频名与 `license`，需要溯源时使用。

_生成时间：2026-11-18T21:30:16+0800；生成者：task-8 pet-assets；素材总量 58,996,706 字节。_
