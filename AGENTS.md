# AGENTS.md — guía para coding agents que usen `puya` CLI

Audiencia: Puyol Ops, Puyol Dev, Codex, Claude Code y cualquier agente
(cloud o local) que ejecute `puya odoo *`. No es un manual de usuario
humano (eso vive en [README.md](README.md)). Acá pongo lo mínimo que
necesitás internalizar para no equivocarte.

## Quién es el admin

Para todo lo que requiera intervención humana (crear slots, queries
grandes, permisos especiales):

- **`nlewin@costasurmat.cl`** — Nico Lewin
- **`dducci@costasurmat.cl`** — Diego Ducci

También responden en Slack `#puya-dev`.

## Qué es el CLI

Wrapper HTTP delgado que habla con `puya-chat /api/cli-odoo/*`. Vos no
hablás con Odoo: hablás con el proxy. El proxy decide RBAC, modelos
permitidos, approval, audit. Una API key encapsula:

- `target_env` — `staging` o `production` (fijo al emitir la key).
- `cli_mode` — `read_only` o `full` (Dev recibe `read_only` por construcción).
- whitelist de modelos Odoo y endpoints custom.
- rate limit propio.

Todo eso es **server-side**. Vos solo presentás la key y el comando.

## Si recién llegás (onboarding 60 segundos)

1. **Verificar instalación**:
   ```bash
   puya version    # esperás "puya 1.1.0" o más
   ```
   Si no está instalado:
   - Container con Python ≥3.10:
     `pip3 install --break-system-packages git+https://github.com/puya-tech/puya-cli.git`
   - Máquina local:
     `pipx install git+https://github.com/puya-tech/puya-cli.git`

2. **Verificar config**:
   ```bash
   puya odoo status
   ```
   Casos:
   - **200 OK con `target_env`** → todo listo, vas a operar contra ese env.
     La respuesta lista `cli_mode`, `models[]` y `custom_endpoints[]` —
     **leelos**, son tu fuente de verdad sobre qué podés hacer.
   - **"API key no seteada"** → el humano debe setear las env vars
     (`PUYA_BASE_URL`, `PUYA_API_KEY_STAGING`, `PUYA_API_KEY_PROD`,
     `PUYA_TARGET_ENV`). Pediselas, no inventes.
   - **401/403** → key inválida o expirada. Reportar al humano para que
     pida una nueva al admin.
   - **400 env mismatch** → la key no corresponde al env pedido. Ver
     "Reglas duras" abajo.

3. **No asumas permisos**. Si `puya odoo status` no lista un modelo en
   `models[]`, no insistas con ese modelo — el proxy te va a rechazar
   con 403. Reportá el límite y derivá al humano si hace falta acceso.

## Cómo accede cada tipo de agente

| Agente | Provisioning de la key | Variables setean |
|---|---|---|
| **Puyol Ops** (container Railway) | Admin emite `puyol-ops-{staging,prod}` keys → Nico las inyecta en `puyol-production` | Set por Railway |
| **Puyol Dev** (container Railway) | Idem con `puyol-dev-{staging,prod}` (cli_mode=read_only) | Set por Railway |
| **Codex / Claude Code en máquina del dev** | El dev ya tiene su key personal (consumer = su email). Si no, pide acceso en `/cli-signup` y la usa después | El dev las exporta en su shell |
| **Agente cloud nuevo (ej. otro container)** | Pedirle al admin que cree un consumer dedicado + slot por env | Inyectar en el container al deploy |

> Para coding agents que corren en la máquina del developer (Claude Code,
> Codex local), **NO podés asumir que el CLI ya está instalado o
> autenticado**. Hacé el smoke test del onboarding (`puya version` →
> `puya odoo status`). Si falla, primero arregla eso antes de avanzar.

## Resolución del env (lo que tenés que entender)

Hay 5 env vars. Tres son las nuevas (multi-env, v1.1.0+) y dos son
legacy. Orden de prioridad cuando ejecutás un comando:

1. **Flag `--env staging|production`** del comando — gana sobre todo.
2. **`PUYA_TARGET_ENV`** — default cuando `--env` no viene.
3. **Una sola** de `PUYA_API_KEY_STAGING` / `PUYA_API_KEY_PROD` seteada
   — se asume esa.
4. **`PUYA_API_KEY`** legacy single-env — fallback.
5. Nada → error. El CLI te dice qué falta.

Si STAGING y PROD están seteadas pero no hay `--env` ni `PUYA_TARGET_ENV`,
el CLI **rechaza**. No adivina. Tenés que elegir.

## Reglas duras

1. **No asumas el env del default sin chequear.** Antes de operar,
   `puya odoo status` te confirma `target_env` efectivo. La salida
   incluye `api_key.target_env` — verificalo.

2. **Para mutaciones (write/create/delete/call) en producción, siempre
   `--env production` explícito en el comando.** Aunque `PUYA_TARGET_ENV`
   sea `production`, ser explícito en el CLI deja trail más claro en logs
   y previene errores cuando alguien (humano o agente) lo desetea.

3. **Mismatch key/env**. Si pegás una key de staging en
   `PUYA_API_KEY_PROD` por error y corrés `--env production`, puya-chat
   responde 400: `env mismatch: client requested "production" but API key
   is for "staging"`. No llega a Odoo. Si ves ese error, **no insistas** —
   reportalo al humano, no intentes "arreglarlo" cambiando flags.

4. **Una mutación bloqueada por approval** devuelve **exit code 3** con
   `pending_id` en el JSON. Tu siguiente paso NO es reintentar: es
   responder al humano con el `pending_id` y que apruebe en Slack.
   Cuando aprueba, la acción corre server-side; vos no la disparás de
   nuevo.

5. **No expongas la key**. Nunca la imprimas en logs, mensajes de Slack,
   tarjetas Notion ni en respuestas. Solo viaja en `Authorization: Bearer`
   del request HTTP, automatizado por el CLI.

## Comandos clave para agentes

```bash
# Handshake — primer comando de cualquier sesión nueva.
puya odoo status                              # ¿qué env, qué cli_mode, qué modelos puedo tocar?

# Reads
puya odoo search <model> -d '<json>' -l 50    # search_read
puya odoo read   <model> '1,2,3' -f a,b       # read por ids
puya odoo count  <model> -d '<json>'          # search_count
puya odoo fields <model> -a string,type       # discovery (qué campos tiene)

# Mutaciones — exit code 3 = pending Slack
puya odoo write  <model> '[1,2]' -v '{"x":1}' -r "razón" [--env production]
puya odoo create <model> -v '{...}'           -r "razón" [--env production]
puya odoo delete <model> '[1,2]'              -r "razón" [--env production]
puya odoo call   <model> <method> --args '[[1,2]]' --kwargs '{}' -r "razón" [--env production]

# Pendings (consumer-self)
puya odoo pending                             # listar mis pendings
puya odoo pending <id>                        # detalle (incluye result si fue read aprobado)
puya odoo cancel <id>                         # cancelar uno propio
```

`-o table | json | raw` cambia el formato del stdout. Default = JSON
parseable, ideal para que el agente parsee con `jq` o equivalente.

## Para ops vs dev (semántica del cli_mode)

| `cli_mode` | search_read | write/create/delete/call |
| ---------- | ----------- | ------------------------ |
| `read_only`| ✅          | ❌ → 403 desde el proxy   |
| `full`     | ✅          | ✅ con approval Slack     |

El cli_mode lo asigna el admin al emitir la key. **Vos no lo cambiás.**
Si tu key es read_only y necesitás escribir, no es bug del CLI: es
política. Reportalo o derivá la tarea (handoff Ops ↔ Dev).

## Casos de uso típicos para coding agents

Esto es lo que esperamos que hagas en una sesión normal — no son
ejemplos exhaustivos, son patrones recurrentes.

### Investigar antes de tocar código

```bash
# "El usuario reporta bug en sale.order — quiero ver datos reales"
puya odoo search sale.order -d '[["state","=","draft"]]' -f id,partner_id,date_order -l 5
puya odoo read sale.order '12345' -f name,state,amount_total,order_line
puya odoo fields sale.order -a string,type,relation   # discovery del schema
```

### Cruzar con código del repo

Después de una `puya odoo read` que te dio el shape del record, abrí
el modelo correspondiente en `~/odoo/costasurmat/<modulo>/models/` para
entender la lógica custom que aplica. El CLI te da datos; el repo te da
el "por qué".

### Proponer un cambio que requiera mutación

```bash
# Contar afectados (sanity check)
puya odoo count purchase.order -d '[["state","=","draft"],["partner_id","=",42]]'

# Pedir el write (NO se ejecuta hasta que humano apruebe en Slack)
puya odoo write purchase.order '[101,102,103]' \
  -v '{"date_planned":"2026-06-01"}' \
  -r "Reagendar tras retraso de proveedor — ticket #5712"
# → exit 3 + JSON con pending_id. Reportá ese pending_id al humano y parate.
```

### Cuando NO usar el CLI

- **Queries grandes (>1000 records)**: el proxy timeout-ea. Pedile al
  admin que la corra por SSH y te pase el resultado por canal aparte.
- **Modelos sistema**: `res.users`, `ir.config_parameter`, `payment.token`,
  etc. no están en ninguna whitelist y son rechazados por hardcoded
  FORBIDDEN_MODELS. No insistas.
- **Datos que ya están en Supabase** (agent_messages, llm_calls, etc.):
  usá el MCP de Supabase read-only en lugar del CLI Odoo.

## Smoke test 30 segundos

```bash
puya odoo status                              # 1) handshake
puya odoo search res.partner -l 1             # 2) read básico
puya odoo write res.partner '[<algún_id_test>]' \
  -v '{"comment":"test"}' -r "smoke"          # 3) mutación → debería dar exit 3 + pending_id
```

Si los 3 pasan, el wiring está OK.

## Errores que vas a ver y cómo responder

| Exit | Significado                                  | Qué hacer                                               |
| ---- | -------------------------------------------- | ------------------------------------------------------- |
| 0    | OK                                           | seguir                                                  |
| 1    | input mal formado, modelo no whitelist, RBAC (400/403/404/409/422/429) | leer el `error` del JSON, NO retry ciego  |
| 2    | usage error de Click (comando inexistente, missing option, tipo inválido) | corregir la invocación. NO retry — esto NUNCA es un problema de server |
| 3    | pending action creada                        | reportar `pending_id`, esperar approval — NO retry      |
| 4    | auth — key inválida/vencida/no autorizada (401) | NO retry. Reportar al humano para que rotee la key o pida una nueva al admin |
| 5    | puya-chat caído u Odoo timeout (5xx + RequestError) | el CLI YA reintentó 1 vez para GETs antes de devolver exit 5. Si llegaste a 5, escalar humano. Para POST (mutations) no hay retry — el server tiene dedupe de pending actions pero el cliente no lo asume |

## Si tu container es un agente Puyol

- `PUYA_API_KEY_STAGING` y `PUYA_API_KEY_PROD` se inyectan por Railway.
- `PUYA_TARGET_ENV` por default es `staging` mientras estés en validación.
  Solo Nico (humano) lo cambia a `production` cuando corresponda.
- Tu `cli_mode` (full vs read_only) ya viene fijado en cada key:
  - `puyol-ops-*` → `full` con approval.
  - `puyol-dev-*` → `read_only` (Dev nunca escribe Odoo, por construcción).
- El header `X-Puya-Requested-Env` lo manda el CLI automáticamente cuando
  resolvés un env explícito. **No hace falta que lo seteés a mano.**

## Cuándo escalar al humano

Reportá al usuario y parate si:

- `puya odoo status` falla con 401/403/500 → la key necesita
  intervención del admin.
- Un write devolvió exit 3 y pasó >10 min sin approval — el humano
  puede haberse olvidado.
- Un modelo que necesitás no está en `models[]` → política del admin,
  no es bug del CLI.
- Recibiste 400 con mensaje de "env mismatch" → config rota; no podés
  arreglarla cambiando flags, alguien tiene que mover la key.
- Un read masivo (>1000 records) timeout-ea con 504 → pedile al admin
  que lo corra por SSH.

## Versión

Este AGENTS.md describe el comportamiento desde **v1.1.0** (multi-env).
Para v1.0.x el modelo era single-key (`PUYA_API_KEY` solamente, sin
`--env`). Si ves `puya version` y dice `1.0.x`, no esperes que `--env`
funcione — bumpeá el `pip install` con `git+https://...` para traer la
versión nueva.
