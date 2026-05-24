# puya

CLI de Puya Tech — thin HTTP client al CLI proxy de **puya-chat**.

A partir de v1.0 el CLI **no se conecta a Odoo directamente**. Toda
operación pasa por el proxy en puya-chat, donde vive el RBAC, audit,
approvals y multi-env. El consumer solo necesita una API key.

## Instalar

```bash
pipx install git+https://github.com/puya-tech/puya-cli.git
```

Requiere Python ≥3.10.

## Configurar

Necesitás una API key emitida por puya-chat. Pedila al admin de tu
organización (no se obtiene self-service): te van a crear un slot y vas
a poder materializar la key plana **una sola vez** en `/cli-account`.

Después exportá:

```bash
export PUYA_BASE_URL=https://puya-chat-interno.vercel.app
export PUYA_API_KEY=puya_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Verificá que arrancó bien:

```bash
puya odoo status
```

Si responde con tu consumer, api_key, modelos permitidos y endpoints
custom habilitados, estás listo. Si no, el mensaje de error indica qué
falta.

## Comandos disponibles

```bash
puya --help                            # raíz: lista subcomandos
puya odoo --help                       # operaciones contra Odoo
puya tool --help                       # endpoints custom registrados
puya version
```

Cada subcomando tiene su propio `--help` con flags, formato y ejemplos.
Para descubrir qué endpoints custom puede invocar tu key:

```bash
puya tool list                         # devuelve cada slug con su JSON Schema
puya tool call <slug> --json '<body>'  # invoca
```

## Multi-environment

Cada API key apunta a un solo entorno (`staging` o `production`, fijo
server-side). El CLI soporta cargar dos keys a la vez y elegir por
invocación con `--env`. Detalle: `puya odoo status --help` y el bloque
multi-env del [AGENTS.md](AGENTS.md).

## Exit codes

| Código | Significado |
|--------|-------------|
| 0 | OK (200 / 201) |
| 1 | Error de input o RBAC (400, 403, 404, 409, 422, 429) |
| 2 | Error externo: puya-chat caído u Odoo timeout (5xx) |
| 3 | Approval pendiente (202) — la mutación queda en cola y se ejecuta cuando un admin apruebe |
| 4 | Auth: key inválida, vencida o no autorizada (401) — rotar key o pedir nueva al admin |

## Para agentes / scripts

Defaults a JSON parseable en stdout. Errores van a stderr. Ejemplo de
loop "intentar / esperar approval":

```bash
out=$(puya odoo write product.template '[1234]' \
  -v '{"list_price": 1620}' -r "ajuste Q3")
code=$?
if [ $code -eq 3 ]; then
  pending_id=$(echo "$out" | jq -r .pending_id)
  echo "Esperando aprobación de pending #$pending_id en Slack..."
fi
```

## Referencias

- Materializar y administrar keys: `https://puya-chat-interno.vercel.app/cli-account`
- Operación interna del CLI, flow approval, deployment de agentes: [AGENTS.md](AGENTS.md)
- Issues: [github.com/puya-tech/puya-cli/issues](https://github.com/puya-tech/puya-cli/issues)
