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

# 2. Configurar 2 env vars
export PUYA_BASE_URL=https://puya-chat-interno.vercel.app
export PUYA_API_KEY=puya_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 3. Verificar
puya odoo status
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

Una API key apunta a **un solo entorno** (`staging` o `production`).
Si necesitás los dos, pediselo al admin: te crea 2 slots, generás 2 keys,
las exportás según el caso.

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

Setear `PUYA_BASE_URL` + `PUYA_API_KEY` como env vars del container. Sin
variables `ODOO_*`, `SUPABASE_*`, `SLACK_*`, `PUYA_ROLE` — todas quedaron
obsoletas en v1.0.

## Historial

v1.0.0 — refactor "Opción 3": el CLI ya no contiene credenciales de Odoo
ni lógica de RBAC. Todo el knowledge sensible vive server-side en
puya-chat.

v0.x — versiones legacy con XML-RPC directo + `permissions.yaml` local.
Borrado en este refactor.
