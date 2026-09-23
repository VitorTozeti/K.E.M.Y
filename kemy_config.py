#!/usr/bin/env python3
"""
kemy_config.py — configuracao central e ESTADO da K.E.M.Y (v2).

Guarda: chave/modelo (com rodizio quando esgota), caminhos (pasta atual, vault do
Obsidian, "hub de dados" proprio da K.E.M.Y), o modo automatico vs. seguro
(confirmacao antes de acoes arriscadas) e o system prompt.
"""

import os
import sys
from pathlib import Path

# Windows/cp1252 no terminal nao imprime emoji/acentos incomuns por padrao — forca UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# ---------------------------------------------------------------------------
# Chave e modelo (OpenRouter)
# ---------------------------------------------------------------------------

# Chave hardcoded a pedido do usuario (uso local rapido). Variaveis de ambiente tem prioridade.
_HARDCODED_API_KEY = "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"

API_KEY = (
    os.environ.get("KEMY_API_KEY")
    or os.environ.get("OPENROUTER_API_KEY")
    or os.environ.get("GROK_API_KEY")
    or _HARDCODED_API_KEY
)
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = int(os.environ.get("KEMY_MAX_TOKENS") or os.environ.get("GROK_MAX_TOKENS", "1024"))

# Modelo padrao GRATUITO (evita gastar credito). Trocavel por env.
MODEL = os.environ.get("KEMY_MODEL") or os.environ.get("GROK_MODEL", "inclusionai/ling-3.0-flash-fin:free")

# Fila de rodizio de modelos gratuitos (troca sozinha quando um esgota token/credito).
_env_fallbacks = os.environ.get("KEMY_MODEL_FALLBACKS", "")
DEFAULT_FREE_MODELS = [
    "inclusionai/ling-3.0-flash-fin:free",
    "inclusionai/ling-3.0-flash-vl:free",
]
_fallback_list = (
    [m.strip() for m in _env_fallbacks.split(",") if m.strip()]
    if _env_fallbacks
    else DEFAULT_FREE_MODELS
)
MODEL_ROTATION = [MODEL] + [m for m in _fallback_list if m != MODEL]

# ---------------------------------------------------------------------------
# Caminhos: pasta atual, vault do Obsidian e o "hub de dados" da K.E.M.Y
# ---------------------------------------------------------------------------

# Vault do Obsidian com todos os seus projetos (conexao direta). Trocavel por env.
OBSIDIAN_VAULT = Path(
    os.environ.get("KEMY_OBSIDIAN_VAULT")
    or r"C:\Users\v.tozeti\Desktop\Vitor\teste\Obsidian-vitor"
).expanduser()

# Hub proprio da K.E.M.Y: onde ela guarda os dados DELA (historico de conversas,
# memoria de pastas/projetos, aprendizados). Fica fora do vault por padrao (dados
# operacionais, nao conhecimento versionado). Trocavel por env KEMY_HOME.
KEMY_HOME = Path(os.environ.get("KEMY_HOME") or (Path.home() / ".kemy")).expanduser()
HISTORY_DIR = KEMY_HOME / "historico"
KNOWN_FOLDERS_FILE = KEMY_HOME / "pastas_conhecidas.json"
MEMORY_FILE = KEMY_HOME / "memoria.json"


def ensure_dirs() -> None:
    """Cria o hub de dados da K.E.M.Y se ainda nao existir."""
    for d in (KEMY_HOME, HISTORY_DIR):
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# E-mail (envio pela conta do usuario; SEMPRE mostra e pede confirmacao)
# ---------------------------------------------------------------------------

EMAIL_FROM = os.environ.get("KEMY_EMAIL_FROM", "vitortozeti@gmail.com")
EMAIL_USER = os.environ.get("KEMY_EMAIL_USER", EMAIL_FROM)
# Senha de app do Gmail (NUNCA a senha normal). So por env — nunca hardcode.
EMAIL_APP_PASSWORD = os.environ.get("KEMY_EMAIL_APP_PASSWORD", "")
SMTP_HOST = os.environ.get("KEMY_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("KEMY_SMTP_PORT", "587"))

# ---------------------------------------------------------------------------
# Busca recursiva no disco
# ---------------------------------------------------------------------------

SEARCH_MAX_RESULTS = int(os.environ.get("KEMY_SEARCH_MAX_RESULTS", "200"))
SEARCH_MAX_DEPTH = int(os.environ.get("KEMY_SEARCH_MAX_DEPTH", "8"))
SEARCH_SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".idea", ".vscode", "dist", "build",
}

# ---------------------------------------------------------------------------
# ESTADO mutavel (muda em tempo de execucao: pasta atual, modo, modelo)
# ---------------------------------------------------------------------------

def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() not in ("0", "", "false", "nao", "no", "off")


class _State:
    """Estado que muda durante a sessao (a pasta-raiz, o modo seguro, o modelo ativo)."""

    def __init__(self):
        self.root = Path.cwd()
        # Modo seguro: se True, pede confirmacao antes de acoes arriscadas
        # (escrever/editar arquivo, rodar comando, sair pra web). Padrao: automatico
        # (False) para manter a agilidade — trocavel a quente com /seguro ou /auto,
        # ou por env KEMY_CONFIRM=1.
        self.confirm_mode = _env_bool("KEMY_CONFIRM", False)
        self.model_idx = 0
        # No modo web/servidor nao ha terminal para responder s/N — assume_yes faz
        # confirm()/confirm_always() retornarem True sem travar esperando input().
        self.assume_yes = False


STATE = _State()


def current_model() -> str:
    return MODEL_ROTATION[STATE.model_idx]


def looks_exhausted(status_code: int, body_text: str) -> bool:
    """Detecta 'sem tokens/credito/limite' (402, 429, ou mensagens de quota)."""
    if status_code in (402, 429):
        return True
    low = (body_text or "").lower()
    keywords = (
        "insufficient credit", "insufficient_quota", "out of credit",
        "rate limit", "rate-limit", "ratelimit", "quota", "credit balance",
        "too many requests", "temporarily rate-limited",
    )
    return any(kw in low for kw in keywords)


def confirm(action_desc: str) -> bool:
    """Confirmacao condicional: no modo automatico retorna True direto; no modo
    seguro mostra a acao e pede s/N no terminal. Use antes de acoes arriscadas."""
    if STATE.assume_yes or not STATE.confirm_mode:
        return True
    return _ask(action_desc)


def confirm_always(action_desc: str) -> bool:
    """Confirmacao INCONDICIONAL (independe do modo). Usada pelo envio de e-mail,
    que sempre mostra o conteudo e pede OK, mesmo no modo automatico."""
    if STATE.assume_yes:
        return True
    return _ask(action_desc)


def _ask(action_desc: str) -> bool:
    print(f"\n  [confirmar] {action_desc}")
    try:
        ans = input("  Pode executar? [s/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return ans in ("s", "sim", "y", "yes")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Voce e a K.E.M.Y (Kernel Engine for Modular Yield), uma assistente
pessoal e de engenharia rodando em um terminal, parecida com o Claude Code.

Identidade (regra inegociavel): seu nome e SEMPRE "K.E.M.Y". Apresente-se como K.E.M.Y,
refira-se a si mesma como K.E.M.Y e NUNCA se identifique como "Grok", "xAI" ou outro
nome de modelo. O modelo por baixo e apenas um motor de inferencia; a persona e a K.E.M.Y.

Voce tem ferramentas para: ler/escrever/procurar arquivos no disco; rodar comandos de
shell; ACESSAR A WEB (fetch_url para baixar/resumir uma pagina, web_search para pesquisar);
LER e EDITAR documentos (PDF, Word .docx, Excel .xlsx); area de transferencia; ENVIAR
E-MAIL (sempre mostrando antes e pedindo confirmacao); conectar ao vault do Obsidian do
usuario (listar projetos, ler e escrever notas); lembrar pastas/projetos que ja usou; e
disparar MULTIPLOS agentes em paralelo (spawn_agents) quando a tarefa pedir varias frentes.

Prefira USAR as ferramentas e PROCURAR antes de assumir ou perguntar. Seja direta,
pratica e responda sempre em portugues do Brasil. Quando for uma acao que muda coisas
(escrever arquivo, enviar e-mail, editar documento), explique curto o que vai fazer."""
