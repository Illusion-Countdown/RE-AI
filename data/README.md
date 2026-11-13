# data/ 数据表说明（RE-AI demo）

本目录是 `D:\Pygame\RE-AI-demo` 的唯一内容数据源。只放 JSON 与本文档，不含代码。
设计来源：`D:\Pygame\RE-AI` 的 `01/02/03/06/07`，以及本工程 `SCOPE.md`。

> **数值优先级：`06-数值主表.md` > `03-算法图鉴.md` > 其他文档。**
> 本文里标了「demo」的数字，是文档没给、为了先跑通流程补的合理值，后续可调。

---

## 0. 文件与数量

| 文件 | 顶层类型 | 数量 | 说明 |
|---|---|---|---|
| `pieces.json` | `array` | **26** | 全部算法棋子 |
| `cards.json` | `array` | **32** | 26 通用 + C 2 + Rust 2 + DeepSeek 2 |
| `enemies.json` | `array` | **6** | Bug / 空指针 / 竞态 / 死循环 / 内存泄漏 / 缓存击穿 |
| `languages.json` | `array` | **2** | C / Rust |
| `ai.json` | `object` | **1** | DeepSeek-V4 |
| `map.json` | `object` | **4 层 / 6 节点** | 4 层提交图 |
| `boss.json` | `object` | **3 阶段** | Canary / Rollout / Circuit Breaker |

`python -c "import json; json.load(open(..., encoding='utf-8'))"` 全部通过；UTF-8 无 BOM、无注释。
当前 `core/content.py` 用 `json.loads(path.read_text(encoding="utf-8"))` 读取，顶层 `array` 与 `{pieces:[...]}` 两种写法都兼容。

### 0.1 节点图

```text
l1a (C)  ─┐
          ├─→ l2a (Rust) ─┐
l1b (Rust)┘                ├─→ l3 (elite/shop) ─→ l4 (boss)
          ┌─→ l2b (C)  ───┘
l1a/l1b ──┘
```

- 第 1 层硬件层：`l1a / l1b` 二选一；
- 第 2 层内核层：`l2a / l2b` 二选一；
- 第 3 层运行时层：单节点 `l3`，`type="elite"`，奖励里带 `shop`，表示「精英战后开商店」；
- 第 4 层：`l4`，`type="boss"`。

> `l3` 是 demo 的合并节点：文档里精英和商店是两种节点，这里用 `rewards` 里的 `"shop"` 同时表达。
> 如果实现上想拆开，在 `map.json` 第 3 层加一个 `type="shop"` 的节点即可，不需要改数值。

---

## 1. pieces.json（26 棋子）

### 1.1 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 内部唯一 id；开局固定棋子使用 `greedy` / `bubble` / `monte_carlo`，与 `core/content.py` 对齐 |
| `name` | string | 中文名 |
| `en` | string | 英文名 |
| `time_complexity` | string | 必须是 `O(1)` / `O(log n)` / `O(n)` / `O(n log n)` / `O(n²)` / `O(2ⁿ)` 或 `O(α(n))` |
| `space_complexity` | string | 文档原文；不参与占格计算，占格看 `shape` |
| `shape` | `[[q,r], ...]` | 轴向六边形偏移；`[0,0]` 为锚点。1/2/3/4/6 格 |
| `hp` | int | 基础 HP（n=4、无加成） |
| `damage` | int | 基础单次伤害；`0` 表示不靠直伤（机制/辅助） |
| `interval` | float | 基础攻击间隔（秒）。`0.0` 是「无主动攻击时间片」的哨兵，见 §1.3 |
| `range` | int | 射程（格） |
| `method` | string | `校验 / 重试 / 剪枝 / 编译 / 中断 / 回收` |
| `tags` | string[] | 构筑/筛选标签 |
| `role` | string | 职能，取自 `03` 速查表 |
| `desc` | string | 一句话真实机制 |
| `special` | string | **实现 id**，`core/battle.py` 直接按字符串分发 |
| `special_params` | object | 该机制的参数（文档值/demo 值） |
| `star3` | string | ★3 换算法描述 |

### 1.2 形状

- 1 格：`[[0,0]]`
- 2 格：`[[0,0],[1,0]]`
- 3 格：`[[0,0],[1,0],[1,1]]`
- 4 格：`[[0,0],[1,0],[0,1],[1,1]]`
- 6 格：`[[0,0],[1,0],[2,0],[0,1],[1,1],[0,2]]`（边长 3 的实心三角形蜂巢，6 格连通、无洞）

三个 6 格棋子共用同一形状。旋转/镜像由实现层处理，数据层不预置多套。

### 1.3 特殊字段约定（重要）

1. **`special` 只放实现 id**，例如 `binary_search`、`hash`、`bubble`、`monte_carlo`、`quicksort`、`union_find`、`backprop` 等。这样现有 `core/content.py`（把 `special` 读成 `str`）和 `core/battle.py`（`special == "..."` 分发）可以直接工作。
2. **参数放 `special_params`**。这是为了同时满足「id + 参数」与现有字符串 schema；当前 `content.py` 还没读这个字段，属于已知技术债（见 §7）。
3. **`interval: 0.0`** 用于剪枝 / 并查集 / LRU 缓存这类 06 表里写「—」的棋子。不能写 `null`：`content.py` 会 `float(None)` 崩溃。实现层应把 `0.0` 解释为「不进入普攻时间片」。
4. **二分查找 / 剪枝 / 并查集 / LRU 的 `damage` 为 0**：06 里二分写「机制」、其余写「0」。二分实际伤害由 `special` 结算。
5. 06 的升星只写「★2 ×1.6，★3 ×2.6，★3 换算法」；`star3` 字段只负责描述换算法后的行为，不带数值。

### 1.4 数值来源

- HP / damage / interval / range / method / 占格：**逐行取自 06 §3**。
- 机制参数：03 各棋子小节；03 没写的补 demo 值并已在 `special_params` 标注。
- 形状：按 06 的格数自行拼合法蜂巢。

### 1.5 已知文档冲突

| 冲突 | 处理 |
|---|---|
| 03 §2 标题写「一格棋子（8 个）」，但哈希的小节和速查表都写 2 格；06 也写 2 格 | **按 06：哈希 2 格**。因此实际是 1 格 7 个、2 格 8 个、3 格 4 个、4 格 4 个、6 格 3 个 |
| 01 §4 写「25 个棋子」，06 / SCOPE 写 26 | 按 06 / SCOPE：**26 个** |
| 03 §7 的 ★3 总表与各棋子小节有冲突（如信号量：总表 RCU，小节读写锁；DFS：总表双向 DFS，小节迭代加深；拓扑：总表强连通分量，小节关键路径；DP：总表斜率优化，小节状态压缩；分治：总表 MapReduce 式分治，小节减治；递归：总表蹦床，小节尾递归） | **`star3` 取各棋子小节的详细效果**；总表只作为命名参考，后续需统一 |
| 03 的量级因子是 n=8 基准，06 已改成 n=4 / 下限 0.7 | 数据不存公式；实现按 06 |

---

## 2. cards.json（32 张）

### 2.1 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 与 `languages.json.special_cards` 对应 |
| `name` | string | 展示名（含系统调用） |
| `system_call` | string | 真实系统调用 / 编译选项 |
| `cost` | int | 算力消耗（02 §8.2） |
| `kind` | `single/area/global` | 拖拽类型 |
| `target` | `piece/sector/board` | 目标选择器 |
| `effect` | string | 可实现的效果 id |
| `value` | number / object | 参数；简单效果用标量，复杂效果用对象 |
| `desc` | string | 规则文本 |
| `unlock` | `common/C/Rust/DeepSeek` | 解锁来源 |

### 2.2 26 张通用卡

| kind | id | 耗 | effect |
|---|---|---|---|
| single | `fork` | 2 | `copy` |
| single | `mmap` | 1 | `cooldown_reset` |
| single | `mprotect` | 1 | `control_immunity` |
| single | `O2` | 2 | `complexity_down` |
| single | `SIMD` | 2 | `damage_buff`（value 1.4） |
| single | `checkpoint` | 2 | `heal`（value 40） |
| single | `swap` | 1 | `banish` |
| area | `gc` | 1 | `cleanse` |
| area | `flush` | 1 | `cleanse` |
| area | `SIGUSR1` | 2 | `force_action` |
| area | `iptables` | 2 | `block_area` |
| area | `stack_overflow` | 3 | `aoe`（value 30） |
| area | `copy_on_write` | 2 | `copy` |
| global | `SIGSTOP` | 3 | `freeze`（value 2） |
| global | `nice` | 2 | `slow`（value 0.5） |
| global | `reboot` | 2 | `balance_hp` |
| global | `kill9` | 3 | `kill` |
| global | `OOMKiller` | 3 | `max_hp_shred` |
| global | `hot_patch` | 3 | `draw` |
| global | `drop_cache` | 2 | `cooldown_delay` |
| global | `ulimit` | 3 | `vram_cost_down` |
| global | `strace` | 2 | `reveal` |
| global | `throttle` | 2 | `action_delay` |
| global | `branch_bound` | 2 | `damage_down` |
| single | `parallel` | 2 | `cooldown_reset` |
| global | `leak` | 2 | `enemy_space` |

### 2.3 6 张专属卡

| unlock | id | 耗 | effect | 说明 |
|---|---|---|---|---|
| C | `void_ptr` | 2 | `damage_buff`（1.8） | 伤害 +80%，10% 打自己人 |
| C | `template` | 3 | `merge` | 编译期与相邻棋子合并，属性相加、不可拆 |
| Rust | `mut_borrow` | 2 | `control_immunity` | 免控/免位移，但吃不到 buff |
| Rust | `unsafe_block` | 2 | `unsafe_power` | 伤害 +50%、技能免显存，但受伤 +30% |
| DeepSeek | `cot` | 2 | `no_stall` | 目标本波不卡顿 |
| DeepSeek | `long_context` | 3 | `range_buff` | 射程 +2（本波） |

> `template` 是 C++ 卡，SCOPE 把它归入「C 系」，所以 `unlock: "C"`。

### 2.4 与现有 battle.py 的兼容

`core/battle.py` 目前只实现了 `aoe / freeze / slow / heal / damage_buff / attack_speed / cooldown_reset / interrupt / reclaim / kill / resource / draw / cleanse / shield / stun`。
数据里：

- 这 15 个分支会用到的 `value` **全部用标量**，避免 `float(dict)` 崩溃；
- 其余卡使用更准确的机制 id（如 `copy` / `merge` / `max_hp_shred` / `no_stall`），当前会走「记录 desc」分支，属于待实现的卡，不是数据错误。

---

## 3. enemies.json（6 种）

| id | 名称 | fault | HP | damage | speed | size | special | handling |
|---|---|---|---|---|---|---|---|---|
| `bug` | Bug | 数据 | 32 | 5 | 1.0 | 1 | `basic` | `damage` |
| `null_pointer` | 空指针 | 数据 | 24 | 5 | 1.0 | 1 | `null_pointer` | `damage` |
| `race` | 竞态 | 并发 | 40 | 5 | 1.0 | 1 | `race` | `interrupt` |
| `deadloop` | 死循环 | 并发 | 999999 | 12 | 0.7 | 2 | `deadloop` | `interrupt` |
| `leak` | 内存泄漏 | 内存 | 96 | 12 | 0.7 | 2 | `leak` | `reclaim` |
| `cache_miss` | 缓存击穿 | 数据 | 112 | 12 | 0.7 | 2 | `cache_miss` | `damage` |

- HP / damage / speed 来自 06 §4（小 5 / 中 12；小 1.0 / 中 0.7）。
- `size` 用 `1/2` 表示小/中（`content.py` 读 int）。
- `special` 是 `battle.py` 直接比较的字符串：`null_pointer` / `race` / `deadloop` / `leak`。
- **死循环 HP 用 `999999` 代表 ∞**。严格 JSON 不能写 Infinity；`-1` 会被 `battle.py` 的「hp<=0 跳过」判定成尸体，所以用大数哨兵，并在 `special_params` 标注 `hp_sentinel: "infinite"`。
- `cache_miss` 的 id 与 `battle.py` 的 Boss 小怪生成代码一致（它引用 `cache_miss`）。
- `handling` 用英文 `damage/interrupt/reclaim`，给卡牌 `kill/reclaim` 判定用。

> 注意：C 的克制是「硬件」，但 demo 保留的 6 种敌人里没有硬件型（段错误等被删）。所以 C 的 ×1.3 在本 demo 没有可触发对象，这是删减带来的已知缺口，见 §7。

---

## 4. languages.json（C / Rust）

| 字段 | 说明 |
|---|---|
| `id` / `name` | `C` / `Rust` |
| `color` | `[r,g,b]`，给 UI 用；文档没有指定语言色，这里是 demo 选色 |
| `rules` | `{id, desc}` 列表，规则文本 |
| `counters` | `{fault: 1.3}`，克制的故障类型 |
| `weak` | `{fault: 0.8}`，被压制的故障类型 |
| `special_cards` | 专属卡 id 列表 |

- C：伤害 +40%；每次技能 15% 概率打自己人；克制硬件、被内存压制；专属 `void_ptr` / `template`。
- Rust：免控/免位移/免注入；吃不到队友 buff；克制内存、被硬件压制；专属 `mut_borrow` / `unsafe_block`。

---

## 5. ai.json（DeepSeek-V4）

| 字段 | 值 / 说明 |
|---|---|
| `id` | `deepseek_v4` |
| `name` | `DeepSeek-V4` |
| `context` | 12（06 §9） |
| `color` | `[77,107,254]`，demo 选色 |
| `passive` | 辖区伤害 +20%；辖区 O(2ⁿ) 不卡顿；辖区启动 +1 秒；母语 C 时管辖 ×1.5、启动 -0.5 秒 |
| `ultimate` | 长思考 CoT：全场 6 秒不卡顿，O(n²)/O(2ⁿ) 间隔 -50%；充能 100 |

`01 §2.4` 的 AI 进阶（Flash/Pro）、多 AI、共管、对齐摩擦、羁绊都不在本 demo 数据里，见 §7。

---

## 6. map.json / boss.json

### 6.1 map 节点字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 节点 id |
| `type` | string | `battle` / `elite` / `boss`；`l3` 的商店能力放在 `rewards` 的 `shop` 标记里 |
| `title` / `desc` | string | UI 文本 |
| `language_pool` | string[] | 环境候选。当前每节点只放 1 种（l1a=C、l1b=Rust、l2a=Rust、l2b=C），保证任一路线都能看到 C 和 Rust |
| `enemy_ids` | string[] | 引用 `enemies.json` 的 id |
| `wave_count` | int | 战斗波数：普通 3 / 精英 2 / Boss 3 |
| `rewards` | string[] | `fragments:45` 这类字符串；`shop` 表示战后商店 |
| `next` | string[] | 后继节点 id |

### 6.2 奖励

- 普通战斗：45 碎片 + 1 次棋子三选一 + 2 张卡；
- 精英：80 碎片 + 1 个稀有棋子 + 1 个版本碎片 + 商店；
- Boss：`victory`。

数值来自 06 §6（战斗 45 / 精英 80）。抽卡是「3 选 1」，实现层从池子里抽 3 个。

### 6.3 boss.json

| 字段 | 值 |
|---|---|
| `total_hp` | 2400（06 / 02：2400 + 技术债×120 + 损坏格×40） |
| `core_damage` | 40（DPS 检查失败的核心伤害） |
| `phases` | 3 个：Canary / Rollout / Circuit Breaker |

`hp_ratio` 是「进入该阶段时的剩余 HP / 最大 HP」门槛：1.0 → 0.66 → 0.33。
`spawns` 用字符串 id 列表：`mirror` 是玩家阵容镜像的占位 id；`bug` / `cache_miss` 引用敌人表。
02 §14.2 的「阶段结束 3 秒伤害 ×2 窗口」写在 `desc` 里，当前 `Battle` 还没有实现这个窗口。

---

## 7. Demo 简化 / 自补数值 / 技术债

### 7.1 文档没给、我补的 demo 值

| 数据 | 值 | 说明 |
|---|---|---|
| 剪枝 / 并查集 / LRU 的 `interval` | `0.0` | 06 是「—」；用 0.0 表示无普攻时间片，避免 `float(null)` |
| 插入排序 `min_interval` | 0.6 秒 | 防止 -5% 叠加到 0；文档没给下限 |
| `checkpoint` 回复 | 40 HP | 02 是「40% HP」；现有 `battle.py` 的 `heal` 读固定值，demo 先给 40 |
| `stack_overflow` 伤害 | 30 | 02 只说「区域内所有单位受伤」，没给数字 |
| 空指针自爆 | 8 伤害 / 半径 1 | 01 说「死亡自爆，伤相邻」，没给数字 |
| 竞态分裂 | 15% 概率 / 40% HP | 01 说「每被攻击一次分裂」，没给概率/血量；沿用 `battle.py` 的 demo 值 |
| 内存泄漏回复 | 8/s（`special_params`） | 06 写「每秒 +8」，但现有 `battle.py` 写死 `2*dt`；数据以 06 为准，代码待改 |
| 死循环 HP | 999999 | ∞ 的 JSON 哨兵，见 §3 |
| `l3` 的 type | `elite` + rewards `shop` | 4 层压缩时把「精英/商店」合成一个节点 |
| 语言 / AI 颜色 | 见文件 | 文档没给语言/AI 色值，按 01 色板选近似色 |
| 卡牌 `value` 标量 | 见 §2.4 | 兼容现有 `battle.py` 的 `float(value)` 分支 |

### 7.2 与现有代码的已知差异（技术债）

1. `special_params` 目前不被 `core/content.py` 读取。`PieceDef` 只有 `special: str`；要实现 03 的完整参数，需要给 `PieceDef` 加 `special_params` 字段并在 `battle.py` 读取。**这是当前数据与代码之间最大的 gap。**
2. `battle.py` 里很多机制是简化近似，和 03 原文不一致，例如：哈希实际给的是 +20% 伤害而不是同桶分摊；布隆的标记/打空逻辑简化；并查集只加 `link` 标记；回溯是给友方回 4 HP 而不是回滚 3 秒；MapReduce 的池子算法是简化版；堆排序的 AOE 是每 3 次还是每次未按参数读。数据按 03 存参数，代码后续应改为读 `special_params`。
3. `battle.py` 的 `leak` 回复是 2/s，06 是 8/s。
4. 06 的规模因子是 n=4、下限 0.7；`battle.py` 目前用固定 `COMPLEXITY_INTERVAL`，没有乘 `f(n)`。数据不存公式，实现层待补。
5. C 的「克制硬件 ×1.3」在 6 种敌人里没有硬件型可触发；需要后续补一个硬件敌人，或把 C 的克制改成数据里实际存在的类型（不建议，优先补敌人）。
6. 06 §5 的波次数量是 24~28 只小怪，demo 的 `start_wave` 只生成 `2 + wave` 只；这是 demo 节奏简化，不是数据表要求。
7. 06 的敌人层缩放、Boss 技术债/损坏格公式、3 秒阶段窗口、DPS 检查惩罚，当前 `Battle` 都只实现了一部分。
8. 当前 `battle.py` 未分发的 `special` 有：`prune`、`merge_sort`、`genetic`、`lru`、`divide`。其中剪枝和 LRU 基础伤害为 0，未实现时会「站着不动」；归并/遗传/分治会退化为普通攻击。实现这 5 个是下一步的主要工作。
9. `l3` 的 `type` 是 `elite`，商店能力放在 `rewards` 的 `"shop"` 标记里；但当前 `scenes/game.py` 只在 `node.type == "shop"` 时进商店。要在 demo 里看到商店，需要二选一：给第 3 层再加一个 `type="shop"` 的节点，或在精英结算后消费 `"shop"` 标记开商店。数据侧改起来都是一行。
10. `kill9` 按 02 是全局卡，`scenes/game.py` 对全局卡传 `target=None`，所以 `effect="kill"` 目前没有可移除目标。需要改成「自动选一个召唤物/中型敌人」或用单独的目标选择流程。
11. `fork` 的 `copy` effect 当前 `battle.py` 没有分支，会走「记录 desc」；`gc` 的 `cleanse` 也只清了 `attack_speed` 状态，没有真正清召唤物/污染。都列在待实现里。
12. `boss.json.total_hp` 按 02 写的是 2400；当前 `Battle.__post_init__` 用 `max(600, total_hp * 0.25)`，demo 实际 Boss 血是 **600**。这是刻意的 demo 压缩，数据不用改；如果以后想打完整 2400，把这段缩放去掉即可。

### 7.3 停用机制（07 / SCOPE）

以下机制**不要**在 demo 里实现，数据里也刻意没有对应字段：

- 环境选择「接受 / 覆写 / 隔离」：环境随机且直接对双方生效；`language_pool` 只负责随机池。
- 多 AI、共管、对齐摩擦、羁绊：整局只有 DeepSeek-V4。
- 8 家公司 / 8 种语言：只保留 C / Rust。
- 25 张棋子专属卡：★★★ 直接改算法行为，不发专属卡。
- 17 种敌人 / 6 层地图：压缩到 6 种敌人 / 4 层。
- 技术债：`SCOPE §1.3` 决定做轻量开关（revert +1；1~2 层敌人 HP +10%/层；3 层以上不再额外惩罚）。数据里没有技术债字段，留待 `RunState`。
- 环境覆写/隔离的花费、共管 70% 衰减、对齐摩擦 3/5 层：都不在数据中。

### 7.4 卡池数量

06 写卡池 75（通用 26 / 语言 8 / AI 16 / 棋子 25）；本 demo 按 SCOPE 只做 **32**：
26 通用 + C 2 + Rust 2 + DeepSeek 2。没有棋子专属卡、没有另外 6 种语言、没有另外 7 个 AI 的卡。

---

## 8. 校验记录

```text
pieces.json    26
cards.json     32  (common 26 / C 2 / Rust 2 / DeepSeek 2)
enemies.json   6
languages.json 2
ai.json        1
map.json       4 layers / 6 nodes
boss.json      3 phases
```

校验方式：`python -c` + `json.load(..., encoding="utf-8")`；另用 `core.content.Content` 做了一次加载冒烟（临时 stub `core.hex`，因为该模块由主程并行编写中）：
`pieces 26 / cards 32 / enemies 6 / langs 2 / layers 4 / nodes 6 / boss_phases 3`，开局 bench = `greedy, bubble, monte_carlo`，手牌 = `mmap, O2, SIGUSR1, SIGSTOP`。

## 9. 修改约定

- 只改 `data/` 下的 JSON 和本文档；不动 `core/`、`scenes/`、`ui/`、`settings.py`。
- 改数值先改 `06`，再同步这里；不要只改 JSON。
- 新增棋子/卡/敌人时，保持 `id` 唯一；`enemy_ids`、`special_cards`、`next` 必须引用存在的 id。
- 所有 JSON 保持 UTF-8 无 BOM、无注释、无尾逗号。
