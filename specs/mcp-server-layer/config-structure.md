# Config Structure

YAML schema for manually configured MCP servers.

## Source Mapping

| Source | Reference |
|--------|-----------|
| mcp-server-layer.md | Section 8 (Config Structure) |
| mcp-server-layer-flow.mermaid | `CONFIG` subgraph `CF1`–`CF5`; `S1` linked to `CONFIG` |

## Responsibilities

Define the `mcp_servers` block in C.O.B.R.A. configuration:

| Field | Purpose |
|-------|---------|
| `name` (`CF1`) | Server display name |
| `endpoint` (`CF2`) | URL |
| `description` (`CF3`) | Human-readable description |
| `capabilities` (`CF4`) | List of capability strings |
| `enabled` (`CF5`) | `true` / `false` |

Full example from parent spec:

```yaml
mcp_servers:
  - name: "Web Search MCP"
    endpoint: "http://localhost:3000"
    description: "Provides web search capability"
    capabilities:
      - web_search
    enabled: true

  - name: "Calendar MCP"
    endpoint: "http://localhost:3001"
    description: "Provides calendar read and write"
    capabilities:
      - calendar_read
      - calendar_write
    enabled: true
```

## Inputs / Outputs

| Direction | Content |
|-----------|---------|
| **In** | User edits config or wizard |
| **Out** | Parsed server list for [discovery.md](discovery.md) and validation |

## Flow

```mermaid
flowchart LR
    CF[CONFIG mcp_servers] --> S1[Load MCP server list]
```

## Rules and Constraints

- Servers added via config or setup wizard only ([discovery.md](discovery.md)).
- New entries can be added without restart (hot reload per [specs/configuration/hot-reload.md](../configuration/hot-reload.md) when integrated).

## Open Items

- [ ] Define whether capability routing priority can be manually configured per server

## Cross-References

- [discovery.md](discovery.md)
- [routing-logic.md](routing-logic.md)
- [specs/configuration/config-file-structure.md](../configuration/config-file-structure.md)
