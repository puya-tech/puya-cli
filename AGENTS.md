# AGENTS.md — guía para coding agents que usen `puya` CLI

Audiencia: Puyol Ops, Puyol Dev, Codex y cualquier agente cloud que
ejecute `puya odoo *` desde sesión OpenCode/Inngest. No es un manual de
usuario humano (eso vive en [README.md](README.md)). Acá pongo lo
mínimo que necesitás internalizar para no equivocarte.

## Qué es el CLI

Wrapper HTTP delgado que habla con `puya-chat /api/cli-odoo/*`. Vos no
hablás con Odoo: hablás con el proxy. El proxy decide RBAC, modelos
permitidos, approval, audit. Una API key encapsula:

- `target_env` — `staging` o `production` (fijo al emitir la key).
- `cli_mode` — `read_only` o `full` (Dev recibe `read_only` por construcción).
- whitelist de modelos Odoo y endpoints custom.
- rate limit propio.

Todo eso es **server-side**. Vos solo presentás la key y el comando.

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
| 1    | input mal formado, modelo no whitelist, env mismatch (400) | leer el `error` del JSON, NO retry ciego                |
| 2    | puya-chat caído u Odoo timeout (5xx)         | esperar y reintentar 1 vez; si persiste, escalar humano |
| 3    | pending action creada                        | reportar `pending_id`, esperar approval — NO retry      |

## Si tu container es un agente Puyol

- `PUYA_API_KEY_STAGING` y `PUYA_API_KEY_PROD` se inyectan por Railway.
- `PUYA_TARGET_ENV` por default es `staging` mientras estés en validación.
  Solo Nico (humano) lo cambia a `production` cuando corresponda.
- Tu `cli_mode` (full vs read_only) ya viene fijado en cada key:
  - `puyol-ops-*` → `full` con approval.
  - `puyol-dev-*` → `read_only` (Dev nunca escribe Odoo, por construcción).
- El header `X-Puya-Requested-Env` lo manda el CLI automáticamente cuando
  resolvés un env explícito. **No hace falta que lo seteés a mano.**

## Versión

Este AGENTS.md describe el comportamiento desde **v1.1.0** (multi-env).
Para v1.0.x el modelo era single-key (`PUYA_API_KEY` solamente, sin
`--env`). Si ves `puya version` y dice `1.0.x`, no esperes que `--env`
funcione — bumpeá el `pip install` con `git+https://...` para traer la
versión nueva.
