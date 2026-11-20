# -*- coding: utf-8 -*-
"""全项目事件名注册表。

命名规范见 ``docs/EVENT_NAMING.md``。

规则：
- 只在这里定义跨层语义事件名，格式 ``DOMAIN_ACTION[_STATE]``。
- 常量名必须和字符串值完全一样。
- 同一个 PR 里注册并使用；不要预埋没有发送方/接收方的事件。
- 业务模块里使用 ``from memory_run import events``，不要写裸字符串。

当前仓库还没有统一的事件总线，因此本文件暂时保持为空。
第一个真正接入 ``emit`` / ``subscribe`` 的 PR 再按规范添加常量。
"""

# --- 战斗 / Battle ---
# --- 卡牌 / Card ---
# --- 敌人 / Enemy ---
# --- 玩家 / Player ---
# --- GC ---
# --- 远征 / Run ---
# --- 房间 / Room ---
# --- 商店 / Shop ---
# --- 界面 / UI ---
