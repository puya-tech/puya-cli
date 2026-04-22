# puya

CLI unificado de Puya Tech para operar Odoo, Notion, Supabase y otras integraciones de Costasurmat. Diseñado tanto para uso humano (devs en terminal) como para ser invocado por agentes (Puyol vía OpenCode).

## Quick start

```bash
# 1. Instalar (requiere Python ≥3.10)
pipx install git+https://github.com/puya-tech/puya-cli.git

# 2. Configurar env vars de Odoo (ver "Configuración" más abajo)
export ODOO_ENV=staging
export ODOO_STAGING_URL=https://...dev.odoo.com
export ODOO_STAGING_DB=...
export ODOO_LOGIN=tu_email@costasurmat.cl
export ODOO_STAGING_API_KEY=...

# 3. Verificar
puya odoo status

# 4. Probar una query real
puya odoo search res.partner -d '[]' -f name,email -l 3
```

---

## Por qué CLI en vez de MCP

Benchmarks 2026: las CLIs son **4–32x más eficientes en tokens** y **100% vs 72% más confiables** que MCP servers para tareas equivalentes. Más detalle en la [tarea Notion del proyecto Puyol](https://www.notion.so/34a806fdf28f8153bfcad4496dcddccd).

`puya` reemplaza progresivamente al MCP server `puya-odoo-mcp`. Coexisten durante la migración.

---

## Instalación

### Devs locales

Recomendado: **pipx** (entorno aislado, no contamina tu Python global).

```bash
pipx install git+https://github.com/puya-tech/puya-cli.git
```

Update:
```bash
pipx upgrade puya
```

Alternativa con **uv**:
```bash
uv tool install git+https://github.com/puya-tech/puya-cli.git
uv tool upgrade puya
```

### Containers / agentes (Puyol)

```bash
pip3 install --break-system-packages --no-cache-dir \
  git+https://github.com/puya-tech/puya-cli.git
```

### Requisitos

- **Python ≥ 3.10**
- Acceso de red al Odoo (URL XML-RPC) y opcionalmente Supabase (audit) y Slack (aprobaciones).

---

## Configuración

`puya` lee config de **variables de entorno**. Ver `.env.example` para la lista completa.

### Modo multi-entorno (recomendado)

```bash
export ODOO_ENV=staging                  # o "production"
export ODOO_STAGING_URL=https://...
export ODOO_STAGING_DB=...
export ODOO_STAGING_API_KEY=...
export ODOO_LOGIN=tu_email@costasurmat.cl
```

`ODOO_ENV` indica contra qué entorno apuntar. Las vars con prefijo (`ODOO_STAGING_*`, `ODOO_PRODUCTION_*`) se eligen según ese flag.

### `LOGIN` y `API_KEY`: prefijo o global

Las vars `LOGIN` y `API_KEY` se buscan **primero con prefijo de entorno**, después caen al fallback global:

| Buscado primero | Fallback |
|---|---|
| `ODOO_STAGING_LOGIN` | `ODOO_LOGIN` |
| `ODOO_STAGING_API_KEY` | `ODOO_API_KEY` |

**Cuándo usar cada uno**:
- Si tu user es el **mismo email** en staging y prod → solo `ODOO_LOGIN` (alcanza)
- Si los users son **distintos por entorno** → usá `ODOO_STAGING_LOGIN` y `ODOO_PRODUCTION_LOGIN`
- API keys casi siempre cambian por entorno → usá las con prefijo

### Modo legacy directo (compat con MCP actual)

Si ya usás `puya-odoo-mcp` con vars sin prefijo, `puya` las acepta también:

```bash
export ODOO_URL=...
export ODOO_DB=...
export ODOO_LOGIN=...
export ODOO_API_KEY=...
```

### Persistir config entre terminales

Lo más cómodo: archivo con tus exports + source en el shell profile.

#### Linux / WSL (bash)

```bash
# 1. Crear archivo
cat > ~/puya-cli.env <<'EOF'
export ODOO_ENV=staging
export ODOO_STAGING_URL=https://...dev.odoo.com
export ODOO_STAGING_DB=...
export ODOO_STAGING_API_KEY=...
export ODOO_LOGIN=tu_email@costasurmat.cl
EOF

# 2. Proteger permisos (contiene API key)
chmod 600 ~/puya-cli.env

# 3. Auto-source en cada shell nueva
echo '[ -f ~/puya-cli.env ] && source ~/puya-cli.env' >> ~/.bashrc

# 4. Recargar
source ~/.bashrc
```

#### macOS (zsh por default)

Idéntico al anterior pero usando `~/.zshrc`:

```bash
# Pasos 1 y 2 igual que Linux
echo '[ -f ~/puya-cli.env ] && source ~/puya-cli.env' >> ~/.zshrc
source ~/.zshrc
```

Si usás oh-my-zsh, también vale poner el source al final del `.zshrc`.

#### Windows PowerShell

En PowerShell la sintaxis es `$env:VAR = "value"`. Se persiste via el profile (`$PROFILE`):

```powershell
# 1. Ubicar o crear profile
if (!(Test-Path $PROFILE)) { New-Item -Path $PROFILE -ItemType File -Force }

# 2. Abrir y agregar las vars
notepad $PROFILE
```

Agregás al profile:

```powershell
$env:ODOO_ENV = "staging"
$env:ODOO_STAGING_URL = "https://...dev.odoo.com"
$env:ODOO_STAGING_DB = "..."
$env:ODOO_STAGING_API_KEY = "..."
$env:ODOO_LOGIN = "tu_email@costasurmat.cl"
```

Guardás y en una nueva ventana de PowerShell `puya odoo status` ya debería mostrarlas.

Alternativa global en Windows: **Configuración → Variables de entorno del sistema** → agregarlas ahí (se comparten entre PowerShell, CMD y apps).

#### Actualizar / rotar una key

Editás el archivo (`~/puya-cli.env` en Linux/Mac, `$PROFILE` en Windows), abrís terminal nueva o `source` otra vez. Listo.

### Otras vars útiles

```bash
# Role efectivo del agente. Default: vendedor (always_approve=true)
export PUYA_ROLE=vendedor              # vendedor | administrativo | developer

# Audit + pending actions (recomendado para uso productivo)
export SUPABASE_URL=https://....supabase.co
export SUPABASE_SERVICE_KEY=eyJhbGc...

# Notificaciones de aprobación a Slack
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_APPROVAL_CHANNEL=C0...

# (alternativa) Notif a Telegram
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
```

---

## Uso

### Verificar conexión

```bash
puya --help
puya odoo --help
puya odoo status              # muestra env, role, conectividad
```

### Lectura

```bash
puya odoo search purchase.order -d '[["state","=","purchase"]]' -f name,date_order -l 5
puya odoo count product.product -d '[["active","=",true]]'
puya odoo read res.partner 1,2,3 -f name,email
puya odoo fields stock.move -a string,type,required
```

### Escritura (con flujo de aprobación)

```bash
# Crea un pending action y notifica a Slack si needs_approval
puya odoo write purchase.order 3203 \
  --values '{"date_planned":"2026-05-24"}' \
  --reason "ajuste por proveedor"

# Si NO necesita approval, devuelve pending_id y exit code 0
# Después confirmar:
puya odoo confirm 88

# Si rechazás:
puya odoo cancel 88

# Listar pendings tuyos:
puya odoo pending
```

### Output

JSON por default. Útil para parsing por agentes/scripts.

```bash
puya odoo status -o json     # (default)
puya odoo status -o table    # bonito en terminal
puya odoo status -o raw      # objeto Python crudo (debug)
```

---

## Exit codes

| Code | Significado |
|---|---|
| 0 | OK |
| 1 | Error de input/permisos del usuario |
| 2 | Error externo (Odoo, red, Supabase) |
| 3 | Bloqueo por aprobación humana requerida (no es error) |

---

## Comandos disponibles

### Capa 1 — Odoo low-level

| Comando | Equivalente MCP | Notas |
|---|---|---|
| `puya odoo status` | `odoo_status` | env, role, conectividad |
| `puya odoo search` | `odoo_search` | search_read genérico |
| `puya odoo count` | `odoo_search_count` | conteo por dominio |
| `puya odoo fields` | `odoo_fields` | descubrir schema de modelo |
| `puya odoo read` | `odoo_read` | lee por ids |
| `puya odoo write` | `odoo_write` | preview + approval flow |
| `puya odoo create` | `odoo_create` | preview + confirm |
| `puya odoo delete` | `odoo_unlink` | preview + approval flow |
| `puya odoo call` | `odoo_execute` | invocar método (action_confirm, etc.) |
| `puya odoo confirm` | `odoo_confirm` | ejecuta pending tras OK |
| `puya odoo cancel` | `odoo_cancel` | rechaza pending |
| `puya odoo pending` | `odoo_pending_list` | lista pendings del user |

### Capa 3 — Operations high-level (futuro)

A diseñar junto con las skills de Puyol (`stock-investigation`, `inventory-adjustment`, etc.). Candidatos:
- `puya stock adjust --sku --location --qty`
- `puya purchase modify-date --po-id --date`
- `puya product update-price --sku --kind=sale|cost --price`

---

## Roles y permisos

`puya` aplica el mismo RBAC que el MCP server. Los roles viven en `src/puya/lib/permissions.yaml` (mismo archivo que `puya-odoo-mcp`).

Roles actuales:

- **`vendedor`** (default) — `always_approve=true`. Cualquier write pasa por aprobación humana en Slack/Telegram. Wildcard `*: [search_read, write, create]` con `INFRA_BLOCKED_MODELS` excluidos hardcoded.
- **`administrativo`** — `always_approve=false`. Write/create explícito en business models (sale, account, etc.). Sin write en `purchase.order`.
- **`developer`** — todo. Sin approval. Solo para emergencias.

Cambiar el role: `export PUYA_ROLE=administrativo` (o pasarlo como flag en futuras versiones).

---

## Arquitectura

```
Capa 3 — Operations (high-level, business-aware) ← FUTURO
  └─ puya stock adjust, puya purchase modify-date, ...
       │
       ▼
Capa 2 — RBAC + Approval + Audit (gating)
  ├─ lib/rbac.py        permissions.yaml + check_model_access
  ├─ lib/audit.py       mcp_audit_log + mcp_pending_actions (Supabase)
  ├─ lib/approvals.py   needs_approval, build_details, notify
  ├─ lib/slack.py       Slack approval blocks
  └─ lib/telegram.py    Telegram fallback
       │
       ▼
Capa 1 — Odoo client (XML-RPC)
  └─ lib/odoo_client.py search/write/create/execute/unlink raw
```

Cada comando vive en `src/puya/commands/<dominio>/<comando>.py` y es un wrapper fino sobre las capas inferiores. El bootstrap común (`Config + RBAC + OdooClient + Audit`) está en `lib/runtime.py`.

---

## Desarrollo

```bash
git clone https://github.com/puya-tech/puya-cli.git
cd puya-cli

# Setup
uv sync                      # instala deps + dev deps en .venv

# Correr local (sin instalar)
uv run puya --help

# Tests + lint
uv run pytest
uv run ruff check
uv run ruff format
```

### Agregar un nuevo comando

1. Crear `src/puya/commands/<dominio>/<comando>.py` con función Typer
2. Importar y registrar en `src/puya/commands/<dominio>/__init__.py`
3. Si es un dominio nuevo, montar el sub-app en `src/puya/cli.py`
4. Tests en `tests/`

Cualquier mutación nueva debe pasar por `lib/approvals.py` (build_details + needs_approval + notify) — no llamar al `OdooClient` directo desde el comando.

### Release

Tag + push:
```bash
# Bumpear pyproject.toml + src/puya/__init__.py (ambos)
git commit -am "release: 0.x.y"
git tag v0.x.y
git push --tags
```

`pipx upgrade puya` traerá la nueva versión.

---

## Troubleshooting

### `ERROR: Package 'puya' requires a different Python: 3.10.x not in '>=3.12'`
Tenías una versión vieja del pyproject. Update con `pipx upgrade puya` o reinstalá: `pipx uninstall puya && pipx install git+https://github.com/puya-tech/puya-cli.git`.

### `Cannot determine package name from spec`
pipx tiene metadata cacheada de un install fallido. Igual que arriba: reinstalar.

### `error: faltan env vars de Odoo: URL, DB, ...`
No setteaste las env vars o `ODOO_ENV` apunta a un prefijo sin valores. Corré `puya odoo status` para ver qué tiene cargado.

### `OSError: unsupported XML-RPC protocol`
URL vacía o sin `https://`. Esto NO debería pasar con la validación de v0.1.2+; si lo ves, actualizá: `pipx upgrade puya`.

### `unauthorized: Authentication failed`
API key incorrecta para el `ODOO_LOGIN` en ese entorno. Verificá que la key sea de ese user puntual y de ese entorno (no mezclar staging/prod).

---

## Licencia

MIT
