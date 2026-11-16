# 更新记录 / CHANGELOG

本项目使用类似 [Semantic Versioning](https://semver.org/) 的版本号。
Alpha 阶段不保证存档/接口兼容。

## [Unreleased]

### Planned

- 修复 `RoomDef.zone` 旧编号
- 修复 `discount` / `perfect` 规则与描述不一致
- 内容校验与种子回归
- 可选：图鉴、程序化遭遇

---

## [0.5.1-alpha] - 2026-11-16

### Added

- 5 区 18 战与 5 Boss 的完整单局
- 商店、整备、卖卡、免费 `++`、碎片经济
- CUT 划线剪断、WEAK 增伤/减攻、LINK 承伤
- 协同敌人：WARD 护盾、PYLON 支援、SENTINEL 精英波
- 4 节教程：CUT / WEAK / LINK / CAST
- 27 个程序化音效，F2 测试、F3 切设备
- `crash.log` 崩溃记录
- 分层依赖检查与一键回归

### Changed

- 代码按 `core/content/run/battle/ui/platform` 分层
- 战斗拆成 core/input/actions/gc/player/enemies
- 渲染拆成 common/core/world/hud/hand
- 抽牌改为整个卡组；寄存器改为 BENCH 展示
- 升级改为拖拽免费

### Fixed

- 支援节点缺少 `atk`/`special` 计时器导致的异常退出
- ECC 调用不存在的 `Deck.all_cards()` 导致无法使用
- CUT 单剪误剪多条（恢复为基础 1 条、++ 2 条）
- PvP 相关代码归档，不再维护

---

## [0.5.0-alpha] - 2026-11-15

### Added

- 初始可玩版本
- 引用图/GC、卡牌网格、画质降级
- 基础房间、敌人、Boss
- 程序化美术与音频

---

## 版本说明

- `0.x`：Alpha，允许 breaking change
- `1.0`：第一个面向公众的 Demo
- 每次 release 必须包含：
  - 新增内容
  - 修复问题
  - 已知问题
  - 升级/兼容说明（如有）
