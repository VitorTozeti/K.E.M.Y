---
name: KEMY_AI
description: chat-bot de terminal em Python (ex grok-chat-cli) cuja persona é a K.E.M.Y — Kernel Engine for Modular Yield — assistente de engenharia de software estilo Claude Code, com ferramentas de arquivo/shell; motor Grok/OpenRouter por baixo
tags: [projeto, proj/kemy-ai, cli, python, chatbot, agente, openrouter, grok]
updated: 2026-09-23 (v2 + interface web index.html/kemy_server.py; testado no navegador: modelo gratuito CONFIRMADO suportando tool-calling; código modularizado)
---

# KEMY_AI — assistente de terminal K.E.M.Y

Chat-bot de terminal em **Python** que conversa livremente (mantendo o contexto de
toda a conversa, como no Claude Code) e pode usar ferramentas para ler/escrever
arquivos, listar pastas e rodar comandos de shell no projeto atual. A persona
exposta ao usuário é a **K.E.M.Y**, que se apresenta e responde **sempre** com esse
nome. O modelo por baixo é o **Grok (xAI) via OpenRouter**, mas isso fica escondido:
para quem usa, quem responde é a K.E.M.Y.

> Antes se chamava **grok-chat-cli**. Foi renomeado para **KEMY_AI** em 2026-09-23.

## O nome — K.E.M.Y = *Kernel Engine for Modular Yield*

Sigla escolhida com cara de desenvolvimento:

- **K**ernel — o núcleo do agente (mantém a conversa e decide o que fazer).
- **E**ngine — o motor que orquestra chamadas de modelo + ferramentas.
- **M**odular — ferramentas plugáveis (`read_file`, `write_file`, `list_dir`,
  `run_command`), fáceis de estender.
- **Y**ield — *entregar/produzir* código e resultados (aceno ao `yield` da programação).

Leitura curta: *"o motor-núcleo modular que entrega código"*.

## Estado atual (2026-09-23)

- **Fase:** **v2 funcionando** — código modularizado e muito mais capaz. Vive **dentro do
  próprio vault**, em `projetos/KEMY_AI/`. Ver mapa completo em [[KEMY_AI-dados]].
- **Interface web (2026-09-23, feito e testado):** `kemy_server.py` (servidor stdlib
  `http.server`, sem dep nova) serve `index.html` (chat tema escuro azul) e a API
  `/api/chat|status|reset|mode`. Roda com `python kemy_server.py` → http://localhost:8000.
  Usa o MESMO cérebro do terminal (`kemy.run_turn`). No web roda em `assume_yes` (não trava
  em confirmação); o `run_turn` ganhou um `emit` para a UI mostrar as ferramentas usadas.
  **Terminal segue funcionando** (`python kemy.py`). Config de preview: `kemy-web` na porta 8800.
  - ✅ **Testado no navegador:** o modelo gratuito `inclusionai/ling-3.0-flash-fin:free`
    **chamou ferramentas com sucesso** (`list_dir`) e respondeu como K.E.M.Y — ou seja, o
    `:free` SUPORTA tool-calling (dúvida das versões anteriores resolvida).
- **v2 — grande expansão de capacidades (2026-09-23, feito):**
  - **Código modularizado:** `kemy.py` (REPL/orquestração) + `kemy_config.py` (config +
    estado + modo) + `kemy_tools.py` (20 ferramentas) + `kemy_agents.py` (multiagente)
    + `kemy_server.py` + `index.html` (web).
  - **Web:** `fetch_url` (baixa/limpa página), `web_search` (DuckDuckGo, sem chave).
  - **Documentos:** `read_document` (PDF/Word/Excel/CSV), `edit_docx`, `edit_excel`.
  - **E-mail:** `send_email` pela conta `vitortozeti@gmail.com` — **sempre mostra e pede
    confirmação** antes de enviar (usa senha de app do Gmail via `KEMY_EMAIL_APP_PASSWORD`).
  - **Área de transferência:** `clipboard_read/write`.
  - **Obsidian:** `obsidian_list_projects`, `obsidian_read_note`, `obsidian_write_note`
    (conexão direta com este vault; caminho em `KEMY_OBSIDIAN_VAULT`).
  - **Memória própria (hub de dados dela):** pasta `~/.kemy/` guarda **histórico
    persistente** das conversas (`--continuar` retoma a última) e a **memória de pastas/
    projetos** que ela já usou (`remember_folder`/`list_known_folders`).
  - **Multiagente:** `spawn_agents` roda várias tarefas em paralelo (threads) e junta.
  - **Modo automático x seguro:** `/auto` e `/seguro` (ou env `KEMY_CONFIRM`) — no seguro
    ela pede OK antes de escrever/rodar/editar/sair pra web; e-mail **sempre** confirma.
  - **Comandos de barra:** `/ajuda /modelo /seguro /auto /pasta /ferramentas /projetos
    /pastas /salvar /limpar`.
  - **Deps opcionais:** `beautifulsoup4, pypdf, python-docx, openpyxl, pyperclip`
    (importadas sob demanda; sem elas a K.E.M.Y avisa `pip install ...`).
- ⚠️ **Segurança (2026-09-23):** a chave hardcoded migrou para `kemy_config.py`; um
  auto-commit do vault chegou a versioná-la (commits locais **não** pushados) — corrigido
  com `git rm --cached` + `.gitignore` apontando p/ `kemy_config.py`. Ver [[KEMY_AI-dados]].
- **Rebrand grok-chat-cli → KEMY_AI (feito):**
  - Pasta `projetos/grok-chat-cli/` → `projetos/KEMY_AI/`; script `grok_chat.py` → `kemy.py`.
  - Banner do REPL e prompt de resposta agora são `K.E.M.Y>` (antes `grok>`).
  - `SYSTEM_PROMPT` reescrito com **identidade inegociável**: a IA deve se apresentar e
    se referir a si mesma **sempre como K.E.M.Y**, **nunca** como "Grok"/"xAI".
  - Variáveis de ambiente novas **`KEMY_API_KEY` / `KEMY_MODEL` / `KEMY_MAX_TOKENS`**,
    com **fallback** para as antigas `GROK_*` (compatibilidade).
  - Função interna `call_grok` → `call_kemy`; README e `.env.example` refeitos; `KEMY_AI.zip`
    reempacotado (sem `.env`/`__pycache__`).
- **Modelo/infra:** OpenRouter, endpoint `chat/completions`, **modelo padrão GRATUITO
  `inclusionai/ling-3.0-flash-fin:free`** (trocado em 2026-09-23 para **evitar gastos**;
  trocável por `KEMY_MODEL`), `temperature 0.3`, `max_tokens` 1024. A chave agora aceita
  `KEMY_API_KEY` → `OPENROUTER_API_KEY` → `GROK_API_KEY`. Loop de ferramentas com teto de 12
  passos por turno. ⚠️ modelos `:free` podem não suportar tool-calling — ver [[KEMY_AI-dados]].
- **Rodízio automático de modelo (2026-09-23, feito):** se o modelo em uso ficar **sem
  tokens/crédito/limite** (402/429/quota), a K.E.M.Y **detecta e troca sozinha** para o
  próximo modelo gratuito da fila (`MODEL_ROTATION`), avisando no terminal — sem precisar
  reiniciar nem o usuário mexer em nada. Fila padrão: `ling-3.0-flash-fin:free` →
  `ling-3.0-flash-vl:free`; customizável via `KEMY_MODEL_FALLBACKS`. Só troca nesse cenário
  específico (erro de quota/limite) — outros erros da API continuam sendo reportados normalmente.
- **Ferramentas (6):** `read_file`, `write_file`, `list_dir`, `find_files`, `search_text`,
  `run_command` — todas **sem trava de pasta** (aceitam caminho absoluto, fora do projeto)
  e `run_command` roda shell real sem confirmar. Ver o aviso de segurança abaixo.
- **Busca livre pelas pastas (2026-09-23, feito):** ganhou `find_files` (acha arquivo por
  nome/glob) e `search_text` (grep dentro dos arquivos), ambos **recursivos** a partir de
  qualquer caminho — a K.E.M.Y agora "procura à vontade" pelo disco, não só lista uma pasta.
  Pulam pastas de ruído (`.git`, `node_modules`, etc.); limites por env `KEMY_SEARCH_MAX_RESULTS`
  (200) e `KEMY_SEARCH_MAX_DEPTH` (8). O `SYSTEM_PROMPT` passou a instruir **procurar antes de
  assumir/perguntar**. Detalhes em [[KEMY_AI-dados]].

## ⚠️ Segurança (dois pontos herdados, ainda válidos)

1. **Chave de API hardcoded** em `kemy.py` (`_HARDCODED_API_KEY`, OpenRouter). Conveniente
   para uso local, **inseguro** para qualquer outra coisa. Por isso `kemy.py` e `KEMY_AI.zip`
   ficam no `.gitignore` do vault — **nunca versionar/compartilhar o script com a chave**.
   As **notas** (`KEMY_AI.md`, `KEMY_AI-dados.md`), o README e o `.env.example` **são**
   versionados normalmente. Se a chave vazar: revogar em `openrouter.ai/settings/keys`.
2. **Sem sandbox de pasta + `run_command` sem confirmação:** a K.E.M.Y pode ler/sobrescrever
   qualquer arquivo do usuário no Windows e rodar comandos reais. Um prompt malicioso escondido
   num arquivo que ela leia pode causar estrago fora do projeto. Acompanhar o que ela propõe.

## Como rodar

```bash
pip install -r requirements.txt
python kemy.py
```

Conversa livre; `sair`/`exit`/Ctrl+C encerra. Config completa no [[KEMY_AI-dados]] e no README da pasta.

## Relacionado
- [[KEMY_AI-dados]] — onde os dados vivem: repo, API/OpenRouter, ferramentas, variáveis de ambiente
- ⭐[[mapa-projetos]] — carregamento de contexto por projeto
