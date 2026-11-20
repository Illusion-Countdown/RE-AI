# 协作 Issue 与通知规范

> 适用：A / B / C / D、Lead，以及替他们工作的 AI agent。
> 目标：需求直接找 Owner，不经过 Lead 传话；父 Issue 管契约，子 Issue 管执行和通知。

---

## 0. 三条硬规则

1. **父 Issue 不 @A/B/C/D**。父 Issue 只放子 Issue 链接和 Owner 名字；队友的通知下沉到子 Issue。
2. **只有公共接口、事件总线、跨 Owner 决策才 @lead**。事件名按 [`EVENT_NAMING.md`](EVENT_NAMING.md) 自己定，不需要 Lead 审批。
3. **一个子 Issue = 一个 Owner + 一个目录 + 一个 PR**。需要别人配合时，再开一个子 Issue，不要在一个 Issue 里扩权。

---

## 1. 角色

| 标记 | 负责 | 典型目录 |
|---|---|---|
| **A 内容与数值** | 卡牌、敌人、房间、模块、Boss 规则、商店、平衡 | `content/` |
| **B 战斗与逻辑** | 引用图、GC、卡牌动作、敌人、Boss、事件发送 | `battle/`、`core/` |
| **C UI 与表现** | 渲染、HUD、整备、商店、拖拽、特效 | `ui/` |
| **D 测试、音频与文档** | 测试、回归、性能、音频、文档整理 | `tools/`、`platform/audio.py`、`docs/` |
| **Lead 接口与验收** | 公共接口、事件总线、架构、合并顺序、最终验收 | `app.py`、`const.py`、跨层接口 |

实际 GitHub 用户名以仓库协作者为准；正文写 `Owner: B`，通知用 GitHub 右侧的 **Assignees** 指派，不要靠正文 @。**父 Issue 里不要 @ 队友，也不要 Assign 队友**。

---

## 2. 先判断用哪种 Issue

```text
只动一个角色（A/B/C/D 之一）
  → 直接开一个子 Issue，Assign 给 Owner
  → 不需要父 Issue

动两个以上角色
  → 先开父 Issue
  → 再给每个角色开一个子 Issue
  → 父 Issue 只放链接和验收，不 @队友
```

单点需求没有父 Issue 时，子 Issue 写：

```text
Parent: 无（单点需求）
```

---

## 3. 父 Issue 模板

```text
标题：新敌人：<名字>

## 目标
敌人死亡时 20% 分裂成 2 个最大生命 30% 的小怪；被击中不分裂。

## 非目标
不做 Boss 分裂；不做小怪连锁分裂。

## 事件契约
事件名：ENEMY_SPLIT_ON_DEATH
发送方：B
监听方：C（特效）/ D（音效）
payload：source_id, x, y, child_count
注册人：B，只改 memory_run/events.py

事件总线未落地，需要引入时 @lead；
事件叫什么名字，B 按 docs/EVENT_NAMING.md 自己定，不用问 Lead。

## 子任务
只写编号和 Owner，不写 @：
- [ ] #子1 [A] 数值与内容（Owner: A）
- [ ] #子2 [B] 逻辑与事件（Owner: B）
- [ ] #子3 [C] 粒子与飘字（Owner: C）
- [ ] #子4 [D] 测试与音频（Owner: D）

## 验收
- [ ] 死亡触发，击中不触发
- [ ] 小怪可攻击、可死亡、不连锁
- [ ] 事件只发一次；没有监听方时不报错
- [ ] python tools/run_all.py 通过

## 需要 Lead 决策
没有就删掉本节；有才写：
@lead 本次是否引入事件总线？不引入的话 B 先用直接回调。
```

父 Issue 由提需求的人或协调者持有，**不要指派给 Lead 当实现者，也不要 Assign 给 A/B/C/D**；队友只在子 Issue 被 Assign。

---

## 4. 子 Issue 模板

```text
标题：[B] 分裂逻辑与事件发送

Parent: #父
Assignee: B

## 具体实现
1. 敌人死亡时掷 20% 概率。
2. 成功生成 2 个小怪，最大生命为原敌人 30%。
3. 发送 ENEMY_SPLIT_ON_DEATH。

## 事件契约
事件名：ENEMY_SPLIT_ON_DEATH
角色：发送方
payload：source_id, x, y, child_count
注册：memory_run/events.py

没有事件就写：无。

## 验证
- 概率改 100% 连续击杀，每次生成 2 只
- 概率改 0%，从不生成
- 监听方断开时不崩

## 不做
不改 UI 特效，不改音频，不做 Boss。
```

规则：

- 一个子 Issue 一个 Owner、一个目录、一个 PR。
- 在 GitHub 右侧 Assign 给 Owner；`Assignee` 本身就是通知，不要再在正文 `@B`。
- 子 Issue 需要别人 review，才在**子 Issue**里 @ 那个人。
- 需要另一个角色配合：另开子 Issue，不在当前子 Issue 里顺手改。

仓库提供了子 Issue 表单：新建 Issue 时选择 **“协作子任务”**。

---

## 5. 事件契约

每个涉及跨层通信的子 Issue 都写：

| 字段 | 写什么 |
|---|---|
| 事件名 | 按 `DOMAIN_ACTION[_STATE]`，例如 `ENEMY_SPLIT_ON_DEATH` |
| 发送方 | 谁产生这个事实，例如 B |
| 监听方 | 谁消费，例如 C / D |
| payload | 字段名和含义，例如 `source_id, x, y, child_count` |
| 注册人 | 通常就是发送方，只改 `memory_run/events.py` |

规则：

- 事件名由发送方按 [`EVENT_NAMING.md`](EVENT_NAMING.md) 自己定，**不需要 Lead 审批**。
- 监听方不要自己轮询状态；监听同一个事件。
- 事件总线还没落地时：`@lead` 决定“本次是否引入总线”，不是决定名字。
- 没有跨层通信就写 `无`，不要为了凑模板硬造事件。

---

## 6. @lead 的边界

### 应该 @lead

- 新增/修改事件总线、公共 API、跨层数据结构
- A/B/C 三个目录都要改的 schema
- 两个 Owner 对语义有冲突
- 范围、优先级、合并顺序冲突
- 子 Issue 被阻塞，且 Owner 之间无法决定

### 不应该 @lead

- 事件叫什么名字
- 子 Issue 内部怎么实现
- UI 用哪种粒子、音效音量
- 测试怎么写
- 单个 Owner 自己目录里的普通改动

`@lead` 必须写清：

```text
@lead 需要决定：<具体问题>
选项：A / B
阻塞点：<不决定的话谁做不了什么>
```

不要只写“@lead 看一下”。

---

## 7. 队友互相提 Issue 的流程

```text
1. 提需求的人先搜现有 Issue，确认不重复。

2. 判断单角色还是多角色：
   - 单角色：直接开子 Issue，Assign 给 Owner。
   - 多角色：先开父 Issue，再开子 Issue。

3. 父 Issue 写目标、非目标、事件契约、验收；
   子任务只放子 Issue 编号和 Owner，不放 @。

4. 每个子 Issue 写 Parent、具体实现、事件契约、验证、不做。
   事件名由发送方自己定。

5. Owner 在自己分支实现，PR 写 Parent: #父。
   一个 PR 只做一件事。

6. PR 合并后关子 Issue；
   所有子 Issue 关闭后，关父 Issue。

7. 代码合并后，由父 Issue Owner 或最后一个合并的子任务 Owner 给 D 开文档 Issue；
   Lead 只在没人持有父 Issue 或跨多个父任务时兜底，不默认代写。
```

互相提需求的例子：

```text
B 要 C 做分裂特效：
B 直接开 [C] 子 Issue，Assign 给 C，不需要通过 Lead。

C 发现需要 B 暴露事件：
C 直接开 [B] 子 Issue，Assign 给 B。

只有要改事件总线、公共接口、跨 Owner schema 时，才 @lead。
```

---

## 8. PR 规则

PR 描述至少包含：

```text
## 改了什么
## 为什么
## 事件契约
## 怎么测
## 影响范围
## 关联 Issue

Parent: #父
```

要求：

- 一个 PR 只做一件事；子 Issue 的 PR 只改这个子 Issue 的范围。
- UI 改动附截图。
- 代码改动跑 `python tools/run_all.py`。
- 不在 PR 里顺手改别人的目录。
- 作者和 agent 都不自行合并；合并由用户决定。

---

## 9. 完成与 D 的文档 Issue

代码 PR 合并后再开 D 的文档 Issue。

**谁开：父 Issue Owner 或最后一个合并的子任务 Owner。Lead 不默认代写。**

- 写代码的人最清楚改了什么、哪些行为变了，D Issue 由他们开最准确。
- 多个子 PR 时，由父 Issue Owner 汇总成**一个** D Issue，不要每个子 PR 各开一个。
- Lead 只在两种情况下兜底：父 Issue 没人持有，或这次改动跨多个父 Issue、需要统一收口。
- 如果文档必须和代码同一个 PR 合并，就把 D 作为**合并前**的子 Issue，而不是合并后补。

```text
标题：[D] 整理分裂者相关文档

Parent/PR: #父 / #PR
Assignee: D

## 改了什么
- 新增敌人“分裂者”
- 死亡 20% 分裂，小怪最大生命 30%
- 新增事件 ENEMY_SPLIT_ON_DEATH

## 需要更新
- docs/CONTENT.md：敌人、房间、事件
- CHANGELOG.md：新增内容
- README.md：如果玩法说明受影响

## 验收
- 文档与合并后的代码一致
- 不写 CSV 之类当前仓库不存在的实现
```

---

## 10. 通知矩阵

| 对象 | 在哪通知 | 怎么通知 |
|---|---|---|
| Lead | 父 Issue 或子 Issue | 只在需要决策时 `@lead`，写清问题、选项、阻塞点 |
| A/B/C/D | 子 Issue | 用 Assignee；权限不够才在子 Issue 里 @ |
| 所有人 | 父 Issue | 不群 @；需要同步就在各子 Issue 评论 |

---

## 11. Agent 执行清单

替队友工作的 agent 在创建/修改 Issue、PR 前：

```text
[ ] 已读 AGENTS.md、docs/COLLABORATION.md、docs/EVENT_NAMING.md
[ ] 人类明确要求创建/修改 Issue 或 PR
[ ] 已搜索重复 Issue
[ ] 单角色 → 一个子 Issue；多角色 → 父 + 子
[ ] 父 Issue 没有 @A/B/C/D，只写链接和 Owner
[ ] 子 Issue 有 Parent、Owner、事件契约、验证、不做
[ ] 事件名按规范自助注册，没有为名字 @lead
[ ] 只有公共接口/事件总线/跨 Owner 决策才 @lead
[ ] 一个子 Issue 一个目录一个 PR
[ ] 代码 PR 合并后，由父 Issue Owner/代码作者创建 D 文档 Issue，不推给 Lead 代写
[ ] 不自行合并 PR
```

---

## 12. 反例

- 父 Issue 里 `@A @B @C @D` → 队友被父、子同时通知。
- 父 Issue 指派给 Lead 写代码 → Lead 又变成瓶颈。
- 子 Issue 没有 `Parent:` → 完成后无法关父任务。
- C 自己轮询敌人死亡，不监听 B 的事件 → 两边逻辑漂移。
- 为了事件名 `@lead` → 起名机器回归。
- 代码 PR 还没合并就让 D 写“已完成”文档 → 文档描述未合并行为。
- 一个 PR 同时改 A/B/C/D → 无法 review，也无法回滚。
- 需要另一个角色配合时，在原子 Issue 里顺手改 → 范围失控。

---

## 13. 一句话

> 父 Issue 定契约和验收，子 Issue 定 Owner 和通知；队友之间直接互提 Issue，Lead 只接公共接口决策。
