# iPilot + 独立 LightRAG MCP Server 手敲施工教程

这份教程改成了多章版本。你可以按顺序照着手敲，也可以先看总目录再跳到具体章节。

## 总目录

1. [第 1 章：现有主链与插入点](./lightrag_mcp_tutorial/01_现有主链与插入点.md)
2. [第 2 章：LightRAG MCP Server 完整代码](./lightrag_mcp_tutorial/02_LightRAG_MCP_Server_完整代码.md)
3. [第 3 章：iPilot 侧 MCP Client 与桥接完整代码](./lightrag_mcp_tutorial/03_iPilot_侧_MCP_Client_与桥接完整代码.md)
4. [第 4 章：接入运行时与工具聚合层](./lightrag_mcp_tutorial/04_接入运行时_与工具聚合层.md)
5. [第 5 章：测试矩阵、联调顺序、常见坑](./lightrag_mcp_tutorial/05_测试矩阵_联调顺序_常见坑.md)

## 你会得到什么

- 一套独立运行的 `LightRAG MCP server`
- 一套通用 `MCP client`
- 一层把 MCP tools 变成 LangChain tools 的桥接层
- 一条不改 `AgentLoop` 主职责的接入路径

## 先说结论

- `loop.py` 不改成业务中心
- `graph_runtime.py` 不直接懂 LightRAG
- MCP tools 最终还是要桥接成 LangChain tools，才能接进现有 `ToolNode`
- 第一版工具固定为 `rag_query`、`rag_index_paths`、`rag_rebuild`
- 服务端 transport 用 `streamable-http`

## 先装依赖

如果你还没装依赖，先在仓库根目录执行：

```bash
uv add "mcp[cli]" lightrag-hku
uv sync
```

如果你想先确认环境：

```bash
uv run python -c "import mcp; import lightrag; print('ok')"
```

## 阅读顺序建议

第一次接触的话，建议你按这个顺序看：

1. 第 1 章，先知道现在代码该往哪里接
2. 第 2 章，先把 LightRAG MCP server 手敲出来
3. 第 3 章，再做 iPilot 侧 client 和桥接
4. 第 4 章，把新工具接回现有 runtime
5. 第 5 章，最后按测试矩阵联调

