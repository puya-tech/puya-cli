# puya

CLI unificado de Puya Tech para operar Odoo, Notion, Supabase y otras integraciones de Costasurmat. Diseñado tanto para uso humano (devs en terminal) como para ser invocado por agentes (Puyol vía OpenCode).

## Por qué CLI en vez de MCP

Benchmarks 2026: CLIs son 4-32x más eficientes en tokens y 100% vs 72% más confiables que MCP servers para tareas equivalentes. Más detalle en la [tarea Notion del proyecto Puyol](https://www.notion.so/34a806fdf28f8153bfcad4496dcddccd).

## Instalación

### Para humanos (devs locales)

```bash
pipx install git+https://github.com/puya-tech/puya-cli.git
# o con uv:
uv tool install git+https://github.com/puya-tech/puya-cli.git
```

### Para containers / agentes (Puyol)

```bash
pip3 install --break-system-packages --no-cache-dir \
  git+https://github.com/puya-tech/puya-cli.git
```

## Configuración (env vars)

```bash
# Multi-entorno (recomendado)
export ODOO_ENV=staging                  # production | staging
export ODOO_STAGING_URL=https://...
export ODOO_STAGING_DB=...
export ODOO_LOGIN=puyol@costasurmat.cl
export ODOO_STAGING_API_KEY=...

# O modo legacy directo (compat con setup MCP actual)
export ODOO_URL=...
export ODOO_DB=...
export ODOO_LOGIN=...
export ODOO_API_KEY=...

# Role efectivo (default: vendedor)
export PUYA_ROLE=vendedor

# Para audit + approvals (opcional pero recomendado)
export SUPABASE_URL=https://....supabase.co
export SUPABASE_SERVICE_KEY=...

# Para notificaciones de aprobación a Slack
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_APPROVAL_CHANNEL=C...
```

## Uso

```bash
puya --help
puya odoo status
puya odoo search purchase.order --domain '[["state","=","purchase"]]' -f name,date_order -l 5
puya odoo write purchase.order 3203 --values '{"date_planned":"2026-05-24"}' --reason "ajuste por proveedor"
puya odoo confirm 88
```

Output JSON por default (parseable). `--output table` para humanos. `--output raw` para debug.

## Exit codes

| Code | Significado |
|---|---|
| 0 | OK |
| 1 | Error de input/permisos del usuario |
| 2 | Error externo (Odoo, red, Supabase) |
| 3 | Bloqueo por aprobación humana requerida (no es error) |

## Comandos disponibles

### Capa 1 — Odoo low-level

| Comando | Equivalente MCP | Notas |
|---|---|---|
| `puya odoo status` | `odoo_status` | env, role, conectividad |
| `puya odoo search` | `odoo_search` | search_read genérico |
| `puya odoo count` | `odoo_search_count` | |
| `puya odoo fields` | `odoo_fields` | descubrir schema de modelo |
| `puya odoo read` | `odoo_read` | lee por ids |
| `puya odoo write` | `odoo_write` | preview + approval flow |
| `puya odoo create` | `odoo_create` | preview + confirm |
| `puya odoo delete` | `odoo_unlink` | preview + approval flow |
| `puya odoo call` | `odoo_execute` | invocar método |
| `puya odoo confirm` | `odoo_confirm` | ejecuta pending tras OK |
| `puya odoo cancel` | `odoo_cancel` | rechaza pending |
| `puya odoo pending` | `odoo_pending_list` | lista pendings del user |

### Capa 3 — Operations high-level (futuro)

A diseñar junto con las skills de Puyol (`stock-investigation`, `inventory-adjustment`, etc.). Candidatos: `puya stock adjust`, `puya purchase modify-date`, `puya product update-price`.

## Arquitectura

```
Capa 3 — Operations (high-level, business-aware) ← FUTURO
  └─ puya stock adjust, puya purchase modify-date, ...
       │
       ▼
Capa 2 — RBAC + Approval + Audit (gating)
  ├─ lib/rbac.py        permissions.yaml + check_model_access
  ├─ lib/audit.py       mcp_audit_log + mcp_pending_actions
  └─ lib/approvals.py   notify Slack/Telegram, build_details
       │
       ▼
Capa 1 — Odoo client (XML-RPC)
  └─ lib/odoo_client.py search/write/create/execute/unlink raw
```

## Desarrollo

```bash
git clone https://github.com/puya-tech/puya-cli.git
cd puya-cli
uv sync
uv run puya --help
uv run pytest
uv run ruff check
uv run ruff format
```

## Licencia

MIT
