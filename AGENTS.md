# AGENTS.md

本文件适用于在本仓库工作的 AI / 自动化代理（DSH、Codex、Claude Code 等）。
用户当次明确指令优先；没有明确授权时，按下面的默认边界执行。

## 1. 先读什么

开始改代码或操作 GitHub 前，先读：

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
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

## 3. 默认操作边界

| 操作 | 默认 |
|---|---|
| 读取 Issue / PR / CI / 仓库信息 | 允许 |
| 创建分支、提交代码 | 允许，限当前任务范围 |
| push 功能分支 | 允许 |
| 创建 Issue / 评论 | 用户明确要求，或正在做 triage 时允许 |
| 创建 PR | 用户明确要求交付 PR，或任务本身要求时允许 |
| push `main` | 禁止；只从工作分支开 PR |
| 合并 PR | 只能由用户手动完成，代理不得合并 |
| 关闭 / 重开 / 删除他人的 Issue 或 PR | 先问 |
| 修改标签 | 遵守 `docs/LABELS.md`；只在明确要求或 triage 时做 |
| 新建 / 删除标签 | 先问 |
| 修改仓库设置、分支保护、Secrets | 先问 |
| force push / 删除 `main` | 禁止 |
| 删除已用完的功能分支 | 已获用户授权；删除前确认改动已汇总并推送 |

## 3.1 默认分支汇总

- 日常修改默认在 `Lynette世界第一可爱` 分支进行。
- 只有需要隔离风险或并行处理时，才新建临时分支。
- 多个临时分支完成后，默认把最终结果汇总到 `Lynette世界第一可爱`。
- 汇总后删除已经用完的临时分支；不确定是否还有独有提交时先问。
- 从 `Lynette世界第一可爱` 开 PR 到 `main`，由用户手动合并。
- 不自动合并分支，不自动合并 PR，不直接 push `main`。

## 4. Issue 与子 Issue

- 使用 `.github/ISSUE_TEMPLATE/` 中的表单。
- 字段虽然都可选，但已知信息要填；不要只写标题就提交。
- 优先级和类型标签按 [`docs/LABELS.md`](docs/LABELS.md) 设置。
- 一个 Issue 最多一个优先级标签。
- 创建子 Issue 时，在正文或回复中写清父 Issue 编号（如 `Parent: #12`）。
- 关联已有 Issue 为子 Issue 时，确认父子关系，不要顺带关闭父 Issue。
- 不要批量创建重复 Issue；先搜索现有 Issue 和 Roadmap。

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

- 一个 PR 只做一件事
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
