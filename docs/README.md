# 文档索引 / Docs

> 不知道先看哪份，从这里开始。

## 项目入口

- [README](../README.md)：项目是什么、怎么运行、操作、测试
- [ROADMAP](../ROADMAP.md)：接下来做什么、不做什么
- [CONTRIBUTING](../CONTRIBUTING.md)：贡献流程、分支、PR、测试
- [CHANGELOG](../CHANGELOG.md)：版本与更新记录
- [SECURITY](../SECURITY.md)：安全漏洞报告
- [LICENSE](../LICENSE)：MIT

## 架构与协作

- [当前代码结构](architecture/STRUCTURE.md)
  - 目录树、文件所有权、依赖方向、兼容 shim
- [四人分工与依赖](team/TEAM_PLAN.md)
  - A 内容 / B 战斗 / C UI / D 平台 QA / Lead 集成
- [新功能沟通模板](guides/FEATURE_REQUEST_GUIDE.md)
  - 需求一页式模板、A/B/C/D 拆单、验收标准

## 内容

- [当前内容清单](content/CONTENT_CATALOG.md)
  - 卡牌、模块、敌人、Boss、房间、经济、音频、已知问题

## 设计

- [单人肉鸽设计稿](design/08_单人肉鸽_内存远征.md)
  - 原始设计目标与实现修订记录

## 代码入口

- `memory_run/`：游戏代码
- `tools/`：测试与回归
- `.github/`：Issue/PR 模板与 CI

## 维护约定

- 新增内容后更新 `content/CONTENT_CATALOG.md`
- 改目录/所有权后更新 `architecture/STRUCTURE.md`
- 改分工/依赖后更新 `team/TEAM_PLAN.md`
- 改范围/里程碑后更新 `../ROADMAP.md`
