# puya

CLI de Puya Tech — thin HTTP client al CLI proxy de **puya-chat**.

A partir de v1.0 el CLI **no se conecta a Odoo directamente**. Toda
operación pasa por endpoints `/api/cli-odoo/*` en puya-chat, donde vive
el RBAC, audit, approvals y multi-env. El consumer solo necesita una
API key opaca tipo `puya_xxx`.

## Quick start

```bash
# 1. Instalar (Python ≥3.10)
pipx install git+https://github.com/puya-tech/puya-cli.git

# 2a. Modo single-env (legacy, una sola key)
export PUYA_BASE_URL=https://puya-chat-interno.vercel.app
export PUYA_API_KEY=puya_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 2b. Modo multi-env (recomendado para agentes, desde v1.1.0)
export PUYA_BASE_URL=https://puya-chat-interno.vercel.app
export PUYA_API_KEY_STAGING=puya_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export PUYA_API_KEY_PROD=puya_yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
export PUYA_TARGET_ENV=staging   # default cuando no se pasa --env

# 3. Verificar
puya odoo status                  # usa el default
puya odoo status --env production # override puntual
```

## Cómo conseguir la API key

1. **Solicitá acceso** en `https://puya-chat-interno.vercel.app/cli-signup`
   con tu email, nombre y organización.
2. Un admin **aprueba** tu solicitud desde Slack y elige tu tipo
   (interno / externo).
3. Recibís un **magic link** por email — abrilo, te loguea en
   `/cli-account`.
4. El admin te crea un **slot de API key** (con env, modelos permitidos
   y endpoints custom). Aparece en tu panel.
5. Click **"Generar mi key"** → ves la key plana **una sola vez** con
   botón copiar.
6. Copiala, exportala como `PUYA_API_KEY`, y listo.

> Si la perdés, no se puede recuperar — pediselo al admin que te cree
> un slot nuevo.

## Comandos

```bash
puya odoo status                                           # handshake + permisos efectivos
puya odoo search <model> -d '<dom>' -f a,b -l 50          # search_read
puya odoo count <model> -d '<dom>'                         # search_count
puya odoo fields <model> -a string,type                    # fields_get (discovery)
puya odoo read <model> '1,2,3' -f a,b                      # read

# Mutaciones — siempre approval humano via Slack del admin
puya odoo write <model> '[1,2]' -v '{"x":1}' -r "razón"    # devuelve exit 3 + pending_id
puya odoo create <model> -v '{...}' -r "razón"             # idem
puya odoo delete <model> '[1,2]' -r "razón"                # idem
puya odoo call <model> <method> --args '[[1,2]]' --kwargs '{}'   # idem

puya odoo pending                                          # lista mis pendings
puya odoo cancel <pending_id>                              # cancelo uno propio
```

Output por default = JSON parseable. Cambiá con `--output table | raw`.

### Exit codes

| Código | Significado |
|--------|-------------|
| 0 | OK (200 / 201) |
| 1 | Error de input, auth o RBAC (4xx) |
| 2 | Error externo: puya-chat caído u Odoo timeout (5xx) |
| 3 | Approval pendiente (202) — la mutación se ejecuta cuando un admin apruebe en Slack |

## Multi-environment

Cada API key sigue apuntando a **un solo entorno** (su `target_env` queda
fijo server-side al emitirla — `staging` o `production`). La novedad de
**v1.1.0** es que el CLI puede tener **dos keys cargadas a la vez** y
elegir cuál usar por invocación.

### Env vars y resolución

| Variable                | Rol                                                                 |
| ----------------------- | ------------------------------------------------------------------- |
| `PUYA_BASE_URL`         | URL del backend puya-chat                                           |
| `PUYA_API_KEY_STAGING`  | Key con `target_env=staging` (modo multi-env)                       |
| `PUYA_API_KEY_PROD`     | Key con `target_env=production` (modo multi-env)                    |
| `PUYA_TARGET_ENV`       | Default cuando no se pasa `--env`. Valores: `staging` \| `production` |
| `PUYA_API_KEY`          | Key única (modo single-env legacy)                                  |

**Orden de resolución** de la key efectiva en cada comando:

1. Flag `--env staging|production` — gana sobre todo, requiere su key correspondiente.
2. `PUYA_TARGET_ENV` — actúa como default cuando `--env` no viene.
3. Si solo está seteada **una** de `PUYA_API_KEY_STAGING` / `PUYA_API_KEY_PROD`,
   se usa esa (sin ambigüedad).
4. Fallback a `PUYA_API_KEY` legacy (modo single-env).
5. Si nada de lo anterior aplica → error con instrucciones.

Si `STAGING` y `PROD` están seteadas pero **no hay default** (ni `--env`,
ni `PUYA_TARGET_ENV`, ni `PUYA_API_KEY`), el CLI **rechaza** y exige
elegir un env explícito. Es defensivo: evita que un script ambiguo le
pegue a prod por accidente.

### Validación server-side

El CLI manda el header `X-Puya-Requested-Env: <env>` cuando elegiste un
env explícito. Si por error pegaste la key staging en `PUYA_API_KEY_PROD`
y corrés `--env production`, **puya-chat responde 400** con un mensaje
claro de mismatch — no llega a Odoo. La key sigue siendo el origen de
verdad del env; el header es un check de coherencia.

### Ejemplo: agente con keys de los dos entornos

```bash
# Una sola exportación — todos los comandos heredan staging por default,
# y para tocar prod basta con --env production.
export PUYA_BASE_URL=https://puya-chat-interno.vercel.app
export PUYA_API_KEY_STAGING=puya_st_abc...
export PUYA_API_KEY_PROD=puya_pr_xyz...
export PUYA_TARGET_ENV=staging

puya odoo status                              # → staging
puya odoo search res.partner -l 5             # → staging
puya odoo status --env production             # → production
puya odoo write purchase.order '[42]' \
  -v '{"date_planned":"2026-06-01"}' \
  --env production -r "ajuste fecha"          # → pending Slack en prod
```

### Backwards compat

Si solo tenés `PUYA_API_KEY` seteada (modo legacy v1.0), el CLI sigue
funcionando idéntico. No se manda el header de coherencia y puya-chat
resuelve el env desde la key.

## Datasets grandes

El proxy aplica timeouts cortos (10s sin approval, 20s con approval) para
proteger al worker shared de Odoo.sh. Para queries que requieran más
tiempo o más records, **no van por acá** — se corren por SSH a Odoo.sh
y los resultados se entregan por canal aparte. Pediselo al admin:
`admin@costasurmat.cl`.

## Para containers / agentes

```bash
pip3 install --break-system-packages --no-cache-dir \
  git+https://github.com/puya-tech/puya-cli.git
```

Modo recomendado (multi-env, desde v1.1.0):

```bash
PUYA_BASE_URL=https://puya-chat-interno.vercel.app
PUYA_API_KEY_STAGING=puya_st_...
PUYA_API_KEY_PROD=puya_pr_...
PUYA_TARGET_ENV=staging   # default; sobreescribible por comando con --env
```

Modo legacy (single-env, sigue funcionando):

```bash
PUYA_BASE_URL=https://puya-chat-interno.vercel.app
PUYA_API_KEY=puya_...
```

Sin variables `ODOO_*`, `SUPABASE_*`, `SLACK_*`, `PUYA_ROLE` — todas
quedaron obsoletas en v1.0. Para guidance dirigida a coding agents
(Puyol Ops, Puyol Dev, Codex), ver [`AGENTS.md`](AGENTS.md).

## Historial

v1.1.0 — multi-env support: dos keys cargadas a la vez vía
`PUYA_API_KEY_STAGING` / `PUYA_API_KEY_PROD`, flag `--env` por comando,
default `PUYA_TARGET_ENV`. Validación `X-Puya-Requested-Env` server-side
para detectar mismatch key/env. Backwards compat con `PUYA_API_KEY`
single-env de v1.0.

v1.0.0 — refactor "Opción 3": el CLI ya no contiene credenciales de Odoo
ni lógica de RBAC. Todo el knowledge sensible vive server-side en
puya-chat.

v0.x — versiones legacy con XML-RPC directo + `permissions.yaml` local.
Borrado en este refactor.
