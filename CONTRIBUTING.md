# 贡献指南 / CONTRIBUTING

感谢你愿意参与《悬垂：内存远征》。

这是一个单人实时卡牌肉鸽原型，当前目标是把“引用图 + 卡牌 + 资源”的核心循环做稳、做可玩、做可维护。请在提交代码前先读这份指南。

---

## 1. 先确认范围

当前**会做**：

- 单人模式
- PC / Windows 优先
- 新卡、新敌人、新房间、新 Boss
- 战斗规则、UI、音频、程序化内容
- 性能、测试、文档、打包

当前**不做**：

- 联机 / 匹配 / 服务器
- 移动端 / Web 端
- 账号 / 支付 / 商业化系统
- 外部商业素材
- 大型 Mod / 创意工坊

如果想法超出范围，请先开 Discussion/Issue 讨论，不要直接写大 PR。

---

## 2. 环境

- Python 3.10+
- pygame-ce
- Windows 10/11 是主要测试平台

```powershell
python -m pip install -r requirements.txt
python run.py --windowed
```

---

## 3. 提交前必做

```powershell
python tools/run_all.py
```

要求：

- 架构检查通过
- 机制/房间/流程/教程/界面/拖拽/音频测试通过
- 不新增 `crash.log`
- 不破坏 22 个房间的加载
- 不破坏 4 节教程

如果只改文档，可以只跑相关检查，但仍建议跑一次 `run_all.py`。

---

## 4. 新功能流程

1. **先开 Issue**，写清楚：
   - 玩家在什么情况下使用
   - 触发条件、费用、目标
   - 成功/失败分别发生什么
   - 与 WEAK / LINK / GC / 护盾 / 画质等机制的交互
   - 验收标准
2. 维护者确认范围和优先级。
3. 需要跨层时拆成 A/B/C/D 小任务（内容、战斗、UI、测试）。
4. 需要改公共接口时，先由维护者冻结接口。
5. 再提交 PR。

详细模板见 [`docs/guides/FEATURE_REQUEST_GUIDE.md`](docs/guides/FEATURE_REQUEST_GUIDE.md)。

不要：

- 先写几千行再问“能不能加”
- 一张 PR 同时改内容、战斗、UI、测试
- 为了过测试删除断言或跳过测试

---

## 5. Bug 报告

请提供：

- 版本 / commit
- 操作系统、Python、pygame-ce 版本
- 复现步骤
- 期望结果 / 实际结果
- `crash.log`（如果有）
- 截图或录屏
- 是否可稳定复现

使用 Issue 模板中的 **Bug report**。

---

## 6. 分支与提交

分支：

```text
main                 稳定可运行
feat/<short-name>    新功能
fix/<short-name>     修复
docs/<short-name>    文档
refactor/<short-name> 重构
```

提交信息建议：

```text
feat: 新增回滚卡
fix: 修复 WARD 支援节点计时器
docs: 补充内容清单
refactor: 拆分 battle 模块
test: 增加 ECC 回归
chore: 更新依赖
```

要求：

- 一个 PR 只做一件事
- 不直接 push `main`
- 不 force push
- 不提交 `crash.log`、`__pycache__`、临时截图
- 不提交未授权的图片/音频/字体

---

## 7. 代码结构

```text
memory_run/core/       引用图、卡牌、网格
memory_run/content/    内容数据
memory_run/run/        远征状态、经济
memory_run/battle/     战斗规则
memory_run/ui/         界面、渲染、整备
memory_run/platform/   音频、平台
tools/                 测试工具
```

分层约束：

- `battle` 不 import `ui`
- `content` 不 import `battle` / `ui`
- `ui` 只读 `battle` / `run` 状态
- `platform` 不 import 游戏逻辑
- `const.py` 只由维护者改

检查：

```powershell
python tools/architecture_test.py
```

---

## 8. 代码风格

- 4 空格缩进
- 文件名小写 + 下划线
- 公共函数写 docstring
- 不引入 numpy / 外部素材 / 网络依赖
- 不在 UI 的 `draw()` 里改状态
- 不在内容数据里写 `if room.code == ...` 战斗分支
- 能进内容表的数值不要散落在逻辑里
- 新公开字段写进接口文档
- 保持 1600×900 布局兼容

---

## 9. PR 要求

PR 描述必须包含：

```text
## 改了什么
## 为什么
## 怎么测
## 影响范围
## 截图 / 录屏（UI 改动必须）
```

合并前：

- [ ] `python tools/run_all.py` 通过
- [ ] 没有新增 `crash.log`
- [ ] 没有跨领地大改
- [ ] 文档/注释同步
- [ ] UI 改动附截图
- [ ] 数值改动附数据或理由

维护者目标：

- 48 小时内确认收到
- 7 天内给出初步反馈
- 不保证所有 PR 都合并；不符合范围/质量的会礼貌拒绝

---

## 10. 内容贡献

新增卡/敌人/房间时，请同时更新：

- 数据文件
- 奖励池/商店池
- 测试
- [`docs/content/CONTENT_CATALOG.md`](docs/content/CONTENT_CATALOG.md)

新增美术/音频：

- 优先程序化绘制/合成
- 如引入第三方素材，必须写明来源和许可证
- 不接受来源不明的商业素材

---

## 11. 社区

- 遵守 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- 技术问题用 Issue
- 设计讨论用 Discussion（如已开启）
- 安全漏洞不要公开，见 [`SECURITY.md`](SECURITY.md)
- 对事不对人；不要人身攻击、刷屏、政治/歧视内容

---

## 12. 许可证

提交代码即表示你同意以本仓库的 MIT License 发布你的贡献。

如果你不同意，请不要提交 PR。
