---
name: KEMY_AI-dados
description: mapa de onde os dados do KEMY_AI vivem — pasta/código, motor Grok via OpenRouter (endpoint, modelo, parâmetros), as 4 ferramentas, variáveis de ambiente KEMY_*/GROK_* e o loop de turno
tags: [projeto, proj/kemy-ai, dados, arquitetura, openrouter, python]
updated: 2026-09-23 (v2: código modularizado em 4 arquivos; 20 ferramentas incl. web/documentos/e-mail/obsidian/multiagente; hub de dados ~/.kemy; modo auto/seguro; incidente de chave versionada corrigido; chave antiga revogada→rotacionada por 401 "User not found")
---

# KEMY_AI — Onde os dados vivem

Nota de dados/arquitetura do [[KEMY_AI]]. O que existe, onde mora e como se conecta.

## Código / repositório

- **Pasta real:** `C:\Users\v.tozeti\Desktop\Vitor\teste\Obsidian-vitor\projetos\KEMY_AI`
  (o código vive **dentro do vault** — diferente dos outros projetos).
- **Git:** no `.gitignore` do vault, **`kemy_config.py`** (contém a chave hardcoded) e
  **`KEMY_AI.zip`** são ignorados; os demais módulos (`kemy.py`, `kemy_tools.py`,
  `kemy_agents.py`), notas, README e `.env.example` **são versionados**.
- **Estrutura (v2, modularizada):**
  - `kemy.py` — entrada: REPL, orquestração do turno, chamada da API com rodízio,
    histórico persistente, comandos de barra.
  - `kemy_config.py` — **config + ESTADO** (chave/modelo, caminhos, modo auto/seguro,
    system prompt, `confirm()`/`confirm_always()`). ⚠️ tem a chave hardcoded → gitignored.
  - `kemy_tools.py` — as **20 ferramentas** + `TOOL_DEFINITIONS` (deps pesadas importadas
    sob demanda).
  - `kemy_agents.py` — multiagente (`run_agents`, paralelo com ThreadPoolExecutor).
  - `kemy_server.py` — servidor web (stdlib `http.server`): serve `index.html` + API
    `/api/chat|status|reset|mode`; sessão única em memória com lock; seta `assume_yes`.
  - `index.html` — interface de chat (tema escuro azul, vanilla JS, fetch na API).
  - `README.md`, `requirements.txt` (base `requests` + extras opcionais), `.env.example`,
    `.gitignore` interno, `KEMY_AI.zip` (pacote distribuível).
- **Como rodar:** web → `python kemy_server.py` (http://localhost:8000); terminal →
  `python kemy.py`. Preview do app (launch.json): `kemy-web`, porta 8800.

## Ferramentas (20) e o hub de dados da K.E.M.Y

- **Arquivos/disco:** `read_file`, `write_file`, `list_dir`, `find_files`, `search_text`, `run_command`.
- **Web:** `fetch_url` (baixa+limpa HTML), `web_search` (POST em `html.duckduckgo.com`, sem chave).
- **Documentos:** `read_document` (dispatch por extensão: `pypdf`/`python-docx`/`openpyxl`/texto),
  `edit_docx` (append/replace/create), `edit_excel` (cell+value / append_row).
- **Área de transferência:** `clipboard_read`, `clipboard_write` (`pyperclip`).
- **E-mail:** `send_email` — SMTP Gmail (`smtp.gmail.com:587`, STARTTLS), remetente
  `KEMY_EMAIL_FROM` (padrão `vitortozeti@gmail.com`), senha só via `KEMY_EMAIL_APP_PASSWORD`
  (senha de APP, nunca hardcode). **Sempre** monta preview e chama `confirm_always` antes de enviar.
- **Obsidian:** `obsidian_list_projects` (lê `referencias/mapa-projetos.md` + `projetos/`),
  `obsidian_read_note`, `obsidian_write_note`. Vault em `KEMY_OBSIDIAN_VAULT`.
- **Memória:** `remember_folder`, `list_known_folders`.
- **Multiagente:** `spawn_agents(tasks[])` → `kemy_agents.run_agents` (paralelo, cada agente
  é um chat simples sem ferramentas, com o mesmo rodízio de modelo).
- **Hub de dados dela (`KEMY_HOME`, padrão `~/.kemy/`):** `historico/conversa-*.jsonl` (uma
  linha JSON por mensagem; `--continuar` retoma a última) e `pastas_conhecidas.json`
  (pastas/projetos que já usou). Fica **fora do vault** (dado operacional, não conhecimento).

## Modo automático x seguro

- Estado em `cfg.STATE.confirm_mode` (env `KEMY_CONFIRM`, padrão auto). `cfg.confirm(desc)`
  retorna True direto no modo auto; no seguro imprime a ação e pede `s/N`. Ferramentas de
  escrita/execução/edição/web chamam `confirm`; **e-mail usa `confirm_always`** (pede OK
  mesmo no auto). Troca a quente com `/auto` e `/seguro`.

## ⚠️ Incidente de segurança (2026-09-23) — chave versionada, corrigido

- Ao migrar a chave hardcoded de `kemy.py` para `kemy_config.py`, o **auto-sync do vault**
  (`.scripts/auto-sync.ps1`, faz `git add -A` + commit + push periódico) rodou na janela
  antes de o `.gitignore` ser atualizado e **commitou `kemy_config.py` com a chave** (commits
  locais `d8737cd`/`0cdb919`).
- **Contido:** os commits **não** foram pushados para `origin`
  (`github.com/VitorTozeti/Obsidian-vitor`); fiz `git rm --cached kemy_config.py` e apontei o
  `.gitignore` para `kemy_config.py`, então o `git add -A` do auto-sync não o reinclui mais.
- **Pendência (decisão do usuário):** a chave ainda está no histórico local não-pushado.
  Fix bulletproof = **revogar/rotacionar a chave** em `openrouter.ai/settings/keys` (ela é de
  uso local e já vai embalada no zip, então rotacionar é barato). Alternativa: limpar os 2
  commits locais antes que o auto-sync os empurre.

### Rotação de chave (2026-09-23) — a chave antiga foi revogada
- A 1ª chave hardcoded passou a devolver **`401 {"message":"User not found"}`** em toda
  chamada (login e web) — sintoma clássico de **chave revogada** pelo OpenRouter (bate com o
  vazamento acima: a chave versionada foi detectada/derrubada).
- **Corrigido:** usuário gerou nova chave e substituímos `_HARDCODED_API_KEY` em
  `kemy_config.py` (linha ~26). Teste direto no endpoint retornou **HTTP 200** — voltou a
  funcionar. A chave nova continua hardcoded (gitignored), então **o risco de re-revogação
  persiste** se ela vazar; recomendação em aberto: mover para `.env` (não versionado).

## Motor de inferência (API)

- **Provedor:** OpenRouter. **Endpoint:** `https://openrouter.ai/api/v1/chat/completions`.
- **Modelo padrão:** `inclusionai/ling-3.0-flash-fin:free` — **GRATUITO** no OpenRouter
  (escolhido em 2026-09-23 para **evitar gastos**). Trocável por env `KEMY_MODEL` (ex.
  `x-ai/grok-4.3`, pago). Lista: `openrouter.ai/models`.
  - ✅ **Tool-calling confirmado:** teste no navegador (2026-09-23) mostrou o
    `inclusionai/ling-3.0-flash-fin:free` chamando `list_dir` com sucesso — o `:free`
    **suporta** function-calling. (Se algum modelo futuro da fila não suportar, as
    ferramentas simplesmente deixam de ser chamadas; aí é só trocar de modelo.)
- **Parâmetros:** `temperature = 0.3`, `max_tokens = 1024` (default), `tool_choice = "auto"`.
- **Auth:** header `Authorization: Bearer <API_KEY>`.
- ⚠️ **Chave hardcoded** em `_HARDCODED_API_KEY` (dentro de `kemy.py`). Variável de ambiente
  tem prioridade. Revogar/gerar em `https://openrouter.ai/settings/keys`.

## Variáveis de ambiente (com fallback)

| Nova (prioridade) | Fallback | Default | Para quê |
|---|---|---|---|
| `KEMY_API_KEY` | `OPENROUTER_API_KEY` → `GROK_API_KEY` | `_HARDCODED_API_KEY` | chave do OpenRouter |
| `KEMY_MODEL` | `GROK_MODEL` | `inclusionai/ling-3.0-flash-fin:free` (grátis) | modelo usado |
| `KEMY_MAX_TOKENS` | `GROK_MAX_TOKENS` | `1024` | teto de tokens da resposta |

Ordem de resolução da **chave**: `KEMY_API_KEY` → `OPENROUTER_API_KEY` → `GROK_API_KEY` →
`_HARDCODED_API_KEY`. Do **modelo**: `KEMY_MODEL` → `GROK_MODEL` → default grátis. As antigas
`GROK_*` seguem funcionando para não quebrar setups existentes.

## Rodízio automático de modelo (quando esgota tokens/crédito)

Implementado em `kemy.py`: `MODEL_ROTATION`, `current_model()`, `_looks_exhausted()`,
`_ModelExhausted` e `call_kemy_with_fallback()`.

- **Fila (`MODEL_ROTATION`):** o `MODEL` atual entra primeiro, seguido dos modelos de
  `KEMY_MODEL_FALLBACKS` (env, separado por vírgula) — ou, se a env não for definida, do
  `DEFAULT_FREE_MODELS` hardcoded: `inclusionai/ling-3.0-flash-fin:free`,
  `inclusionai/ling-3.0-flash-vl:free`. Sem duplicar o modelo atual na fila.
- **Detecção de esgotamento (`_looks_exhausted`):** HTTP `402` (crédito insuficiente) ou
  `429` (rate limit), OU o corpo da resposta contendo palavras-chave (`insufficient
  credit`, `rate limit`, `quota`, `too many requests`, etc.) — cobre variações de texto
  que o OpenRouter pode devolver.
  - `nvidia/nemotron-3-embed-1b:free` **não** entra nessa lista: é modelo de
    **embeddings**, não serve para chat/tool-calling — citado pelo usuário mas descartado
    por não ser aplicável ao caso de uso da K.E.M.Y.
- **Troca (`call_kemy_with_fallback`):** ao bater um erro "esgotado", avisa no terminal
  (`[K.E.M.Y] Modelo '...' sem tokens/credito/limite — trocando para '...'`) e tenta o
  próximo da fila. Persiste o índice do modelo ativo (`_current_model_idx`) para a sessão
  inteira — não volta a tentar o modelo que já esgotou. Se **todos** esgotarem, levanta erro
  (não inventa resposta). Erros que **não** são de esgotamento (ex. request malformado)
  propagam imediatamente, sem trocar de modelo.
- **Transparência:** o banner do REPL (`main()`) mostra o modelo ativo e a fila completa
  ao iniciar.

## Ferramentas base de arquivo/disco (parte das 20)

As 6 ferramentas originais (`read_file`, `write_file`, `list_dir`, `find_files`,
`search_text`, `run_command`) seguem existindo dentro das 20 (lista completa na seção
"Ferramentas (20)" acima). Diferença na v2: `write_file` e `run_command` passam pela
confirmação do **modo seguro** (`cfg.confirm`); no modo automático rodam direto como antes.

### Busca recursiva (grande liberdade de acesso a pastas)
- `find_files`/`search_text` usam o helper `_walk_limited` (os.walk com teto de profundidade
  e skip de pastas de ruído). **Limites** por env: `KEMY_SEARCH_MAX_RESULTS` (padrão 200),
  `KEMY_SEARCH_MAX_DEPTH` (padrão 8).
- **Pastas ignoradas** (`SEARCH_SKIP_DIRS`): `.git`, `.hg`, `.svn`, `node_modules`,
  `__pycache__`, `.venv`, `venv`, `.mypy_cache`, `.pytest_cache`, `.idea`, `.vscode`,
  `dist`, `build` — além de pastas ocultas (começam com `.`).
- `search_text` lê como UTF-8 com `errors="ignore"` (arquivo binário/ilegível é pulado).

⚠️ **Sem trava de pasta:** `_resolve_path` faz `expanduser().resolve()` sem restringir à raiz —
por decisão do usuário — então o agente alcança **e agora também vasculha recursivamente**
qualquer arquivo/pasta que o processo tenha permissão (inclusive achar `.env`/chaves varrendo o disco).

## Estado da conversa e loop de turno

- `messages` guarda a conversa inteira (system + user + assistant + tool) e é reenviada a cada pergunta.
- Persona fixada na 1ª mensagem `system` (`SYSTEM_PROMPT`): identidade **K.E.M.Y** obrigatória.
- `run_turn` roda até **12 iterações**/turno: chama a API, se vier `tool_calls` executa e devolve
  o resultado como mensagem `role: "tool"`, repete até a resposta final (ou o teto de passos).
- Encoding: `stdout/stderr` forçados a UTF-8 (Windows/cp1252 quebraria acentos/emoji).

## Relacionado
- [[KEMY_AI]] — hub do projeto (estado atual, rebrand, significado da sigla)
- ⭐[[mapa-projetos]]
