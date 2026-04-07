# LangGraph SQLite 持久化流程图

## 总览图

```mermaid
flowchart LR
    U["User CLI API"] --> L["AgentLoop process_direct"]
    L --> C["thread_id session_key"]
    C --> G["LangGraph ainvoke"]
    G --> S["StateGraph nodes"]
    S --> CP["checkpointer"]
    CP -->|SQLite| DB["checkpoints sqlite3"]
    CP -->|Memory| IM["InMemorySaver"]

    DB --> T1["checkpoints table"]
    DB --> T2["writes table"]

    T1 --> R["restore list get_tuple"]
    T2 --> R
    R --> G
```

## 创表流程

```mermaid
sequenceDiagram
    autonumber
    participant App as iPilot LangGraph
    participant Saver as SqliteSaver
    participant Conn as sqlite3.Connection
    participant DB as SQLite file

    App->>Saver: create saver
    Saver->>Conn: sqlite3.connect
    App->>Saver: first use
    Saver->>Saver: cursor setup
    Saver->>Conn: executescript create tables
    Conn->>DB: tables exist
    Saver-->>App: ready
```

## 更新流程

```mermaid
flowchart TD
    A["new message"] --> B["AgentLoop process_direct"]
    B --> C["build context"]
    B --> D["thread_id session_key"]
    D --> E["graph ainvoke"]
    E --> F["load last checkpoint or start"]
    F --> G["call_model"]
    G --> H["confirm tools"]
    H --> I["write checkpoint"]
    H --> J["write writes"]
    I --> K["checkpoints table"]
    J --> L["writes table"]
    K --> M["next checkpoint_id"]
    M --> N["same thread next turn"]
```

## 失败恢复流程

```mermaid
flowchart LR
    A["crash or stop"] --> B["keep SQLite file"]
    B --> C["same session_key next run"]
    C --> D["graph ainvoke"]
    D --> E["checkpointer get_tuple"]
    E --> F["checkpoints table"]
    E --> G["writes table"]
    F --> H["restore latest checkpoint"]
    G --> H
    H --> I["restore state and pending writes"]
    I --> J["continue from checkpoint_id"]
    J --> K["final result"]
```

## 人工介入流程

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant A as AgentLoop
    participant G as LangGraph
    participant N as ConfirmNode
    participant S as SqliteSaver
    participant D as SQLite

    U->>A: send
    A->>G: ainvoke thread_id
    G->>N: enter confirm
    N->>N: detect risky command
    N->>G: interrupt
    G->>S: save pause point
    S->>D: write
    G-->>A: interrupts

    U->>A: resume
    A->>G: ainvoke resume thread_id
    G->>S: get_tuple
    S->>D: load pause point
    G->>G: continue
    G-->>A: final result
```

## 备注

- 正式持久化入口使用 `SqliteSaver.from_conn_string(...)`。
- `session_key` 对应 LangGraph 的 `thread_id`。
- `InMemorySaver` 只适合实验入口。
