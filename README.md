# puya

CLI de Puya Tech — thin HTTP client al CLI proxy de **puya-chat**.

A partir de v1.0 el CLI **no se conecta a Odoo directamente**. Toda
operación pasa por el proxy en puya-chat, donde vive el RBAC, audit,
approvals y multi-env. El consumer solo necesita una API key.

## Setup

Requiere Python ≥3.10 en cualquier OS (macOS, Linux, WSL, Windows).

```bash
pipx install git+https://github.com/puya-tech/puya-cli.git
puya version
```

**Personas:** entra con tu Google @costasurmat.cl. Un admin (Nico o Diego)
te habilita el acceso en puya-chat; tú no manejas keys.

```bash
puya login                 # abre el navegador; --env staging|production si tienes ambos
puya odoo status
puya login --no-browser    # sin navegador en este equipo (SSH): pegas la dirección de vuelta
puya logout
```

La sesión queda en `~/.config/puya/credentials.json` (permisos 600) y se
refresca sola. Dura hasta 30 días; después, `puya login` de nuevo.

**Máquinas (agentes, servicios):** usan una key `puya_` por entorno. Pedile a un
admin del proxy de puya-chat (Slack `#puya-dev`) una key por
entorno y materializala en
https://puya-chat-interno.vercel.app/cli-account (se ve plana **una sola
vez**).

Setear las env vars de la manera que prefieras en tu shell — ver
[`.env.example`](.env.example) para la lista completa:

```bash
export PUYA_BASE_URL=https://puya-chat-interno.vercel.app
export PUYA_API_KEY_STAGING=puya_...
export PUYA_API_KEY_PROD=puya_...
export PUYA_TARGET_ENV=staging   # default cuando hay ambas keys cargadas
```

Verificá:

```bash
puya odoo status
```

Si devuelve tu consumer + modelos permitidos, está listo. A partir de
acá descubrís todo con `puya --help` y los `--help` de cada subcomando.

## Exit codes

| Código | Significado |
|--------|-------------|
| 0 | OK (200 / 201) |
| 1 | Error de input o RBAC (400, 403, 404, 409, 422, 429) |
| 2 | Usage error de Click: comando inexistente, missing option, valor de tipo inválido — corregir invocación |
| 3 | Approval pendiente (202) — la mutación queda en cola y se ejecuta cuando un admin apruebe |
| 4 | Auth: key inválida, vencida o no autorizada (401) — rotar key o pedir nueva al admin |
| 5 | Server lejano caído / network: puya-chat o Odoo timeout (5xx + RequestError) — el CLI ya reintentó 1 vez para GETs, si llegaste a 5 escalar |

## Para agentes / scripts

Defaults a JSON parseable en stdout. Errores van a stderr. Ejemplo de
loop "intentar / esperar approval":

```bash
out=$(puya odoo write product.template '[1234]' \
  -v '{"list_price": 1620}' -r "ajuste Q3")
code=$?
if [ $code -eq 3 ]; then
  pending_id=$(echo "$out" | jq -r .pending_id)
  # Bloquea hasta que se ejecuta, falla, se rechaza o expira (máx 30 min).
  puya odoo wait "$pending_id"
fi
```

O en un paso: `puya odoo write ... --wait`. `puya odoo wait` imprime una
línea JSON por pending con su `outcome` (`executed` con el resultado,
`failed` con el error, `rejected`, `cancelled`, `expired`) y sale con 0 si
todos se ejecutaron, 1 si alguno terminó distinto y 3 si se acabó el tiempo.

## Referencias

- Materializar y administrar keys: `https://puya-chat-interno.vercel.app/cli-account`
- Operación interna del CLI, flow approval, deployment de agentes: [AGENTS.md](AGENTS.md)
- Issues: [github.com/puya-tech/puya-cli/issues](https://github.com/puya-tech/puya-cli/issues)
