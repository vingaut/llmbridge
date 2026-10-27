# Formes écrites par harnais

Référence pour les contributions : ce que l'outil écrit exactement, et ce qu'il
préserve. Tous les exemples viennent de fichiers réels produits et relus.

## opencode — `~/.config/opencode/opencode.jsonc`

Écrit dans `providers` (pluriel). Les commentaires `//` et les autres fournisseurs
sont conservés en mode `add`.

```jsonc
"lan-170-8080": {
  "name": "192.168.1.170:8080",
  "package": "@opencode-ai/ai/providers/openai-compatible",
  "settings": {
    "baseURL": "http://192.168.1.170:8080/v1",
    "apiKey": "none",
    "headerTimeout": 900000,
    "chunkTimeout": 300000
  },
  "models": {
    "deepseek-v4-1-flash": {
      "modelID": "deepseek-v4.1-flash",
      "name": "deepseek-v4.1-flash",
      "capabilities": { "tools": true, "input": ["text", "image"], "output": ["text"] },
      "compatibility": { "reasoningField": "reasoning_content" },
      "limit": { "context": 1048576, "output": 32768 }
    }
  }
}
```

- `alias` (clé sous `models`) = `slug(modelID)`, `modelID` = id réel sur le fil ;
- `apiKey` vaut la clé saisie, ou `"none"` si l'endpoint n'en demande pas ;
- `model` racine est réécrit si la case « model: → ce modèle » est cochée ;
- mode `reset` : `$schema` + `model` + ce fournisseur uniquement.

## Hermes Agent — `~/.hermes/config.yaml` (+ `.env`)

Entrée de liste sous `custom_providers`, plus le bloc `model:` si demandé.

```yaml
custom_providers:
  - name: lan-170-8080
    base_url: http://192.168.1.170:8080/v1
    key_env: HERMES_CUSTOM_192_168_1_170_8080_API_KEY
    model: deepseek-v4.1-flash
    models:
      deepseek-v4.1-flash: {}
    models_discovered: true
model:
  default: deepseek-v4.1-flash
  provider: custom
  base_url: http://192.168.1.170:8080/v1
  api_key: "${HERMES_CUSTOM_192_168_1_170_8080_API_KEY}"
  context_length: 1048576
```

- repérage par `name` (pas par position) : l'entrée existante est remplacée ;
- `key_env` pointe sur une variable du `.env` voisin (jamais la clé en clair) ;
- `mcp_servers`, `model_overrides`, `compression`, `cron`… ne sont jamais touchés en
  mode `add` ;
- mode `reset` : seuls `custom_providers` et `model` restent (très destructeur).

## dsh — `~/.dsh/cordis.patch.yml` (+ `.env`)

Fournisseur sous `llm-pi-ai → config.providers`, et `agent-default-model`.

```yaml
- id: llm-pi-ai
  config:
    providers:
      lan-170-8080:
        displayName: 192.168.1.170:8080
        apiKeyEnv: LAN_170_8080_API_KEY
        api: openai-completions
        baseURL: http://192.168.1.170:8080/v1
        streamIdleTimeoutMs: 1800000
        compat:
          thinkingFormat: chat-template
          chatTemplateKwargs:
            enable_thinking: { $var: thinking.enabled }
            reasoning_effort: { $var: thinking.effort, omitWhenOff: true }
        models:
          - id: deepseek-v4.1-flash
            name: deepseek-v4.1-flash
            contextWindow: 1048576
            maxTokens: 32768
            input: [text, image]
            reasoningEfforts:
              off: none
              low: low
              high: high
              max: max
- id: agent-default-model
  config:
    provider: lan-170-8080
    model: deepseek-v4.1-flash
    reasoningEffort: high
```

- `preserve_thinking` est écrit **dans** `chatTemplateKwargs` (c'est là que dsh le lit) ;
- les entrées `compaction-basic`, `ui-settings-general`, etc. sont conservées ;
- mode `reset` : `llm-pi-ai` + `agent-default-model` seulement.

## `.env`

Mise à jour par nom de variable, sans doublon, en conservant le reste du fichier :

```dotenv
LAN_170_8080_API_KEY=sk-…
```

Le bloc `.env` de l'interface ne s'active que si le fichier existe (ou si son chemin
est déclaré) ; une valeur vide ne touche à rien.
