# AGENTS.md

本文件适用于在本仓库工作的 AI / 自动化代理（DSH、Codex、Claude Code 等）。
用户当次明确指令优先；没有明确授权时，按下面的默认边界执行。

## 1. 先读什么

开始改代码或操作 GitHub 前，先读：

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
- [`docs/COLLABORATION.md`](docs/COLLABORATION.md)（创建/修改 Issue、父子任务、@ 通知时必读）
- [`docs/EVENT_NAMING.md`](docs/EVENT_NAMING.md)（涉及事件名时必读）
- [`docs/BATTLE_EVENTS.md`](docs/BATTLE_EVENTS.md)（修改战斗事件 payload 时必读）
- [`docs/LABELS.md`](docs/LABELS.md)（涉及 Issue / PR 标签时必读）

不要凭记忆猜仓库结构、测试命令或标签含义。

## 2. GitHub 仓库与认证

- 仓库：`Illusion-Countdown/RE-AI`
- 默认分支：`main`
- `main` 当前规则：禁止删除、禁止 non-fast-forward；普通 push 可用
- 不使用 `--admin` 绕过规则，不 force push，不删除 `main`

`gh` 可能不在当前 shell 的 `PATH` 中。先检查：

```powershell
Get-Command gh
```

找不到时使用：

```powershell
& 'C:\Program Files\GitHub CLI\gh.exe'
```

认证由 `gh` keyring 管理。禁止：

- 输出、提交、粘贴 token
- 使用 `gh auth token` / `--show-token` 展示凭据
- 把 token 写进 Issue、PR、日志或代码

### 2.1 GitHub API 使用约束

限流不是封号，但**被限流后继续硬刷、并发轰炸或开小号/多 token 绕限**，可能升级为账号处罚。

执行 GitHub API 操作时：

- 批量操作前先看额度：

  ```powershell
  gh api rate_limit --jq '.resources.core, .resources.search, .resources.graphql'
  ```

- 不要秒级轮询 PR / CI / Issue；CI 轮询间隔保持 30–60 秒。
- 优先批量取数据，不要“列表 + 逐条 view”的 N+1 调用。
- 分页优先 `per_page=100`；不要无边界 `--paginate` 拉全仓库。
- 只读 GET 可缓存：

  ```powershell
  gh api repos/Illusion-Countdown/RE-AI/issues/27 --cache 10m
  ```

- 少用搜索 API（认证后约 30 次/分钟）；能用 `gh issue list` + 本地过滤就不要反复 `--search`。
- Project / GraphQL 查询较重；不要每次改完都重拉整个 Project。
- 遇到 `403` / `429` / 二级限流：
  - 立刻停止；
  - 读 `Retry-After`、`X-RateLimit-Reset`；
  - 指数退避；
  - **不要换 IP、换 token、开小号继续刷**。
- 网络 reset / 连接失败可以重试；限流和 abuse 提示不要硬重试。
- Actions 里优先用 `GITHUB_TOKEN`，不要在多个 job 里重复使用个人 PAT。
- 额度低时，优先改用本地 git / 文件操作，非必要 API 调用延后。

## 3. 默认操作边界

| 操作 | 默认 |
|---|---|
| 读取 Issue / PR / CI / 仓库信息 | 允许 |
| 创建分支、提交代码 | 允许，限当前任务范围 |
| push 功能分支 | 允许 |
| 创建 Issue / 评论 | 用户明确要求，或正在做 triage 时允许 |
| 创建 PR | 用户明确要求交付 PR，或任务本身要求时允许 |
| push `main` | 仅当用户明确要求；默认走功能分支 + PR |
| 合并 PR | 仅当用户明确要求 |
| 关闭 / 重开 / 删除他人的 Issue 或 PR | 先问 |
| 修改标签 | 遵守 `docs/LABELS.md`；只在明确要求或 triage 时做 |
| 新建 / 删除标签 | 先问 |
| 修改仓库设置、分支保护、Secrets | 先问 |
| force push / 删除分支 | 先问；永远不要对 `main` 做 |

## 4. Issue 与子 Issue

- 使用 `.github/ISSUE_TEMPLATE/` 中的表单。
- 字段虽然都可选，但已知信息要填；不要只写标题就提交。
- Issue 标题统一为 `[A/B] 简短标题`；`[]` 表示**大致分工**，主 Owner 写在最前，实际 Assignee 仍用 GitHub 右侧；标题里不要 @ 人。
- 优先级和类型标签按 [`docs/LABELS.md`](docs/LABELS.md) 设置。
- 一个 Issue 最多一个优先级标签。
- 创建子 Issue 时，在正文或回复中写清父 Issue 编号（如 `Parent: #12`）。
- 关联已有 Issue 为子 Issue 时，确认父子关系，不要顺带关闭父 Issue。
- 不要批量创建重复 Issue；先搜索现有 Issue 和 Roadmap。
- 多角色需求：父 Issue + 每个角色一个子 Issue；父 Issue 只放子 Issue 链接和 Owner，**不 @A/B/C/D**。
- 父 Issue 的 Assignee 是**提需求的人自己**，并**加入 Project**；父 Issue 不放执行 Owner。
- 子 Issue 的 Assignee 是对应 **Owner**，**不加入 Project**；一个子 Issue 一个 Owner、一个目录、一个 PR。
- 不知道找哪个 Owner：先问 Lead 或 AI 助手路由，不要猜；功能做不做、范围、优先级由 `@lead` 决定。
- 分配给你的 Issue 如果无法单独完成，或需要别人同步改动但 Issue 没写清：不要改别人的目录，也不要默默扩大范围；必须开子 Issue 给对方 Owner，写清要改什么、为什么归对方、接口/事件契约、验收和当前阻塞点。
- 只在公共接口、事件总线、跨 Owner schema、语义/范围冲突、功能取舍时 `@lead`；事件名按 [`docs/EVENT_NAMING.md`](docs/EVENT_NAMING.md) 自助注册，不要为起名 @lead。
- 代码 PR 合并后，由父 Issue Owner 给 D 开文档 Issue；单点需求由代码作者开；父 Owner 不在时由最后一个合并的子任务 Owner 兜底。Lead 不默认代写。文档必须随代码合并时，D 作为合并前子 Issue。
- 完整流程和模板见 [`docs/COLLABORATION.md`](docs/COLLABORATION.md)。

## 5. 分支、提交与 PR

分支命名：

```text
feat/<short-name>
fix/<short-name>
docs/<short-name>
refactor/<short-name>
test/<short-name>
chore/<short-name>
```

提交信息使用 Conventional Commits，**不要带版本号**：

```text
feat: 新增回滚卡
fix: 修复 WARD 支援节点计时器
docs: 补充标签规则
```

PR 描述至少包含：

```text
## 改了什么
## 为什么
## 怎么测
## 影响范围
## 关联 Issue
```

要求：

- 一个 PR 只做一件事；多角色需求按子 Issue 拆 PR
- PR 写 `Parent: #父`（单点需求写 `Parent: 无`），并写清事件契约
- 未完成时用 Draft PR
- 推送前跑相关测试；代码改动跑 `python tools/run_all.py`
- 等 CI `CI / test` 通过再请求合并
- 不替作者批准自己的 PR，不绕过 review
- 合并方式按用户指定；未指定时先问

## 6. 标签

- 优先级只有五个：`Urgent Ultra`、`Urgent`、`High`、`Medium`、`Low`
- 一次只用一个优先级；多个时保留最高级并移除其余
- 没有优先级标签表示“尚未 triage”，不要默认补 `Medium`
- `Urgent Ultra` 只给发布阻塞：无法启动、数据丢失、安全漏洞、主线不可用
- `Urgent` 只给当前里程碑必须完成的事项
- 类型标签和优先级独立，可以组合
- 代理不得自行新建标签，不得批量刷标签
- 改标签后必须报告：Issue/PR 编号、旧值、新值、理由

完整规则见 [`docs/LABELS.md`](docs/LABELS.md)。

## 7. 交付时报告

完成任务时说明：

- 改了哪些文件
- 跑了什么测试，结果如何
- 是否创建/修改了 Issue 或 PR，附链接
- 标签变化及理由
- 没有验证到的部分
