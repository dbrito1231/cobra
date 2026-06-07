# HTTP Transport (v1)

C.O.B.R.A. v1 uses a **REST HTTP shim** to communicate with MCP-compatible servers. Standard MCP JSON-RPC/SSE transport is deferred to a future phase.

## Endpoints

Each configured MCP server exposes these paths relative to its `endpoint` base URL:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Reachability probe (startup validation) |
| `GET` | `/capabilities` | Returns declared capability list + protocol version |
| `POST` | `/invoke` | Execute a capability call |

## Invoke request

```json
{
  "capability": "web_search",
  "query": "sanitized topic-only query"
}
```

## Invoke response

Success:

```json
{
  "result": { }
}
```

Failure: non-2xx HTTP status with optional error body.

## Implementation

Client: [`src/mcp/client.py`](../../src/mcp/client.py)

If `/capabilities` is unavailable, configured capabilities from `config.yaml` are used as fallback.

## Future work

- Native MCP JSON-RPC/SSE client for standard MCP servers
- Transport negotiation during startup validation

## Cross-references

- [startup-validation.md](startup-validation.md)
- [execution-flow.md](execution-flow.md)
