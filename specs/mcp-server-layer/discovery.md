# Discovery

How MCP servers are registered and made available to C.O.B.R.A. — manual configuration only.

## Source Mapping

| Source | Reference |
|--------|-----------|
| mcp-server-layer.md | Section 1 (Discovery) |
| mcp-server-layer-flow.mermaid | `S1` (load list from config); `CONFIG` subgraph; implicit manual-only rule |

## Responsibilities

- MCP servers are **manually configured only** — added explicitly via the config file or the setup wizard.
- **No automatic network scanning or auto-discovery.**
- Each server entry in the config defines: **name**, **endpoint URL**, **description**, and **what capabilities it provides**.
- New servers can be added at any time **without restarting C.O.B.R.A.**

## Inputs / Outputs

| Direction | Content |
|-----------|---------|
| **In** | Config file `mcp_servers` entries; setup wizard additions |
| **Out** | Server list consumed by startup validation and live registry |

## Flow

```mermaid
flowchart LR
    Config[config.yaml mcp_servers] --> S1[Load MCP server list]
    Wizard[Setup wizard] --> Config
    S1 --> Validate[Startup Validation]
```

## Rules and Constraints

- Discovery is never automatic — user must explicitly add each server.
- Server metadata fields are defined in [config-structure.md](config-structure.md).

## Open Items

_None specific to this component._

## Cross-References

- [config-structure.md](config-structure.md) — YAML shape for server entries
- [startup-validation.md](startup-validation.md) — validates loaded servers on start
- [specs/configuration/first-time-setup.md](../configuration/first-time-setup.md) — wizard may add MCP servers
