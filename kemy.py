#!/usr/bin/env python3
"""
KEMY_AI — converse no terminal com a K.E.M.Y (Kernel Engine for Modular Yield).

v2: web, documentos (ler/editar PDF/Word/Excel), busca web, historico persistente,
memoria de pastas/projetos, e-mail com confirmacao, area de transferencia, conexao
com o Obsidian, multiagente e modo automatico vs. seguro.

Ela se apresenta e responde SEMPRE como K.E.M.Y. Por baixo usa modelos GRATUITOS do
OpenRouter (com rodizio quando um esgota token/credito).

Uso:
    python kemy.py            # nova conversa
    python kemy.py --continuar  # retoma a ultima conversa salva
"""

import datetime as _dt
import json
import sys
from pathlib import Path

import requests

import kemy_config as cfg
import kemy_tools as tools


# ---------------------------------------------------------------------------
# Chamada da API com rodizio de modelo
# ---------------------------------------------------------------------------

class _ModelExhausted(Exception):
    """Modelo atual sem tokens/credito/limite (402/429/quota)."""


def _call(messages: list, model: str) -> dict:
    resp = requests.post(
        cfg.API_URL,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg.API_KEY}"},
        json={
            "model": model,
            "messages": messages,
            "tools": tools.TOOL_DEFINITIONS,
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": cfg.MAX_TOKENS,
        },
        timeout=120,
    )
    if not resp.ok:
        if cfg.looks_exhausted(resp.status_code, resp.text):
            raise _ModelExhausted(f"{resp.status_code}: {resp.text}")
        raise RuntimeError(f"Erro da API (motor de inferencia) ({resp.status_code}): {resp.text}")
    return resp.json()


def call_with_fallback(messages: list) -> dict:
    """Chama com o modelo atual; se esgotar, troca para o proximo da fila e avisa."""
    last_exc = None
    for tried in range(len(cfg.MODEL_ROTATION)):
        model = cfg.current_model()
        try:
            return _call(messages, model)
        except _ModelExhausted as exc:
            last_exc = exc
            nxt = (cfg.STATE.model_idx + 1) % len(cfg.MODEL_ROTATION)
            if tried + 1 >= len(cfg.MODEL_ROTATION):
                break
            print(f"\n  [K.E.M.Y] Modelo '{model}' sem tokens/credito/limite — "
                  f"trocando para '{cfg.MODEL_ROTATION[nxt]}'...\n")
            cfg.STATE.model_idx = nxt
    raise RuntimeError(
        f"Todos os modelos gratuitos ficaram sem tokens/credito/limite. Ultimo erro: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Turno (com chamadas de ferramenta em cadeia)
# ---------------------------------------------------------------------------

def run_turn(messages: list, emit=None) -> str:
    """Roda um turno. `emit(kind, text)` recebe eventos ('tool'/'result'); se None,
    imprime no terminal (comportamento padrao). O servidor web passa um coletor."""
    def _ev(kind: str, text: str) -> None:
        if emit is not None:
            emit(kind, text)
        elif kind == "tool":
            print(f"\n  [ferramenta] {text}")
        elif kind == "result":
            print(f"  [resultado] {text}\n")

    for _ in range(12):
        data = call_with_fallback(messages)
        message = data["choices"][0]["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return message.get("content") or ""

        for call in tool_calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            _ev("tool", f"{name}({args})")
            impl = tools.TOOL_IMPLS.get(name)
            try:
                result = impl(**args) if impl else f"Ferramenta desconhecida: {name}"
            except Exception as exc:  # noqa: BLE001
                result = f"Erro: {exc}"
            if not isinstance(result, str):
                result = str(result)
            preview = result if len(result) <= 400 else result[:400] + "…"
            _ev("result", preview)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

    return "(atingi o limite de passos nesta rodada — pode me pedir para continuar)"


# ---------------------------------------------------------------------------
# Historico persistente
# ---------------------------------------------------------------------------

def _new_history_path() -> Path:
    cfg.ensure_dirs()
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return cfg.HISTORY_DIR / f"conversa-{stamp}.jsonl"


def _append_history(path: Path, role_msg: dict) -> None:
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(role_msg, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _load_last_history() -> list:
    cfg.ensure_dirs()
    files = sorted(cfg.HISTORY_DIR.glob("conversa-*.jsonl"))
    if not files:
        print("(nenhuma conversa anterior para retomar)")
        return []
    msgs = []
    with files[-1].open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    msgs.append(json.loads(line))
                except ValueError:
                    pass
    print(f"(retomando {files[-1].name} — {len(msgs)} mensagens)")
    return msgs


# ---------------------------------------------------------------------------
# Comandos de barra (/...)
# ---------------------------------------------------------------------------

def _print_help():
    print("""
Comandos:
  /ajuda                 mostra esta ajuda
  /modelo                mostra o modelo ativo e a fila de rodizio
  /seguro                liga o modo seguro (pede confirmacao antes de acoes arriscadas)
  /auto                  liga o modo automatico (sem confirmacoes; e-mail ainda confirma)
  /pasta <caminho>       muda a pasta-raiz atual (e anota na memoria da K.E.M.Y)
  /ferramentas           lista as ferramentas disponiveis
  /projetos              lista os projetos do vault do Obsidian
  /pastas                lista as pastas/projetos que a K.E.M.Y ja anotou
  /salvar                salva a conversa agora (ja salva automatico a cada msg)
  /limpar                limpa a conversa (mantem so a persona)
  sair | exit            encerra
""")


def _handle_slash(cmd: str, messages: list, history_path: Path) -> bool:
    """Trata um comando de barra. Retorna True se era um comando (nao mandar pro modelo)."""
    parts = cmd.split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if name in ("/ajuda", "/help"):
        _print_help()
    elif name == "/modelo":
        print(f"  Modelo ativo: {cfg.current_model()}")
        print(f"  Fila de rodizio: {', '.join(cfg.MODEL_ROTATION)}")
    elif name == "/seguro":
        cfg.STATE.confirm_mode = True
        print("  Modo SEGURO ligado — vou pedir confirmacao antes de escrever/rodar/editar/sair pra web.")
    elif name == "/auto":
        cfg.STATE.confirm_mode = False
        print("  Modo AUTOMATICO ligado — sem confirmacoes (e-mail ainda mostra e confirma).")
    elif name == "/pasta":
        if not arg:
            print(f"  Pasta atual: {cfg.STATE.root}")
        else:
            novo = Path(arg).expanduser()
            if novo.is_dir():
                cfg.STATE.root = novo.resolve()
                tools.remember_folder(cfg.STATE.root)
                print(f"  Pasta-raiz agora: {cfg.STATE.root}")
            else:
                print(f"  Pasta inexistente: {novo}")
    elif name == "/ferramentas":
        print("  " + ", ".join(sorted(tools.TOOL_IMPLS.keys())))
    elif name == "/projetos":
        print(tools.tool_obsidian_list_projects())
    elif name == "/pastas":
        print(tools.tool_list_known_folders())
    elif name == "/salvar":
        # regrava tudo do zero (historico ja e append; aqui so confirma)
        print(f"  Conversa em: {history_path}")
    elif name == "/limpar":
        del messages[1:]
        print("  Conversa limpa (persona mantida).")
    else:
        print(f"  Comando desconhecido: {name} (use /ajuda)")
    return True


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

def main() -> None:
    cfg.ensure_dirs()
    continuar = "--continuar" in sys.argv or "--continue" in sys.argv

    print("K.E.M.Y — Kernel Engine for Modular Yield (v2)")
    print(f"Pasta atual: {cfg.STATE.root}")
    print(f"Modelo ativo: {cfg.current_model()}")
    if len(cfg.MODEL_ROTATION) > 1:
        print(f"Rodizio (troca sozinho se acabar token/credito): {', '.join(cfg.MODEL_ROTATION)}")
    print(f"Modo: {'SEGURO (pede confirmacao)' if cfg.STATE.confirm_mode else 'AUTOMATICO'}"
          "  —  troque com /seguro ou /auto")
    print(f"Vault Obsidian: {cfg.OBSIDIAN_VAULT}")
    print(f"Dados da K.E.M.Y: {cfg.KEMY_HOME}")
    print('Digite normalmente, ou /ajuda. Para sair: "sair", "exit" ou Ctrl+C.\n')

    tools.remember_folder(cfg.STATE.root)

    if continuar:
        old = _load_last_history()
        messages = old if old else [{"role": "system", "content": cfg.SYSTEM_PROMPT}]
    else:
        messages = [{"role": "system", "content": cfg.SYSTEM_PROMPT}]

    history_path = _new_history_path()
    for m in messages:
        _append_history(history_path, m)

    while True:
        try:
            user_input = input("voce> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAte mais!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"sair", "exit", "quit"}:
            print("Ate mais!")
            break
        if user_input.startswith("/"):
            _handle_slash(user_input, messages, history_path)
            continue

        user_msg = {"role": "user", "content": user_input}
        messages.append(user_msg)
        _append_history(history_path, user_msg)

        n_before = len(messages)
        try:
            reply = run_turn(messages)
        except Exception as exc:  # noqa: BLE001
            print(f"\nErro: {exc}\n")
            del messages[n_before - 1:]  # remove a msg do usuario sem resposta valida
            continue

        # grava o que o turno acrescentou (assistant + tools); a msg do usuario ja foi gravada
        for m in messages[n_before:]:
            _append_history(history_path, m)

        print(f"\nK.E.M.Y> {reply}\n")


if __name__ == "__main__":
    main()
