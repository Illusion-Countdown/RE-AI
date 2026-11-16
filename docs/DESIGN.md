# 设计归档

> 原始设计稿已归档到 Git 历史。
> 当前实现以代码和 [`CONTENT.md`](CONTENT.md) 为准，本文件不再维护旧版规则。

## 保留的设计核心

- 引用图 / refcount / GC 级联
- 卡牌作为网格实体，占格 = 内存占用
- 空闲格 = 工作内存
- 画质是资源，不是单纯滤镜
- CUT / WEAK / LINK / ALIAS / CAST 等拓扑动作
- 固定关卡 + 肉鸽奖励 + 整备/商店

## 不再作为当前规格的内容

- 旧的“寄存器选 3 种”设计：当前已改为整个卡组抽牌，BENCH 只展示未入网格的卡。
- 旧的 3 区 9 房结构：当前为 5 区 18 战 + 5 Boss。
- 旧的付费升级：当前为拖拽同名基础卡免费 `++`。
- 旧的碎片产出：当前普通房 +1、Boss +3、完美 +2。

## 当前文档

- 代码结构/分工 → [`DEVELOPMENT.md`](DEVELOPMENT.md)
- 当前内容清单 → [`CONTENT.md`](CONTENT.md)
- 新功能需求 → [`FEATURE_REQUESTS.md`](FEATURE_REQUESTS.md)
- 路线图 → [`../ROADMAP.md`](../ROADMAP.md)
