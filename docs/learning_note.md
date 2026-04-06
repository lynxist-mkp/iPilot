我会按章节顺序推进；每章先手敲，再运行最小验收。

00
uv固定python版本为3.12.4，符合原始项目要求

01
完成了cli初始搭建、环境搭建和测试cli是否正常可用。

02
config的schema设计, 获取config路径的方法，加载与保存config，初始化配置文件onboard

03
双向message的定义，双向message队列、session定义、session_manager定义（内部的get、save、load等方法）

04
对工具、标准llm输出和llm提供商进行了规范，定义了llm提供商的标准形态，完成对openaicomatible格式的调用方法

05
标准工具定义、工具注册、文件系统操作工具、系统命令工具的实现

06
添加记忆库、技能库、和上下文拼装系统。上下文拼装系统中添加启动时的prompt动态组装，从agents、个性、用户个性、工具能力等上下文拼装，并可拓展至channel信息和历史信息拼装。

07
agentloop功能实现，包括tool调用与tool消息追加。

09
网页端初步搭建，测试流程正常

10
失败重试机制、stream流式输出、hooks实现功能拓展

11
心跳机制实现

12
channel功能实现、