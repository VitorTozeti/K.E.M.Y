#!/usr/bin/env python3
"""
kemy_tools.py — todas as ferramentas que a K.E.M.Y pode chamar (v2).

Grupos: arquivos, busca no disco, shell, WEB (fetch/search), DOCUMENTOS (ler/editar
PDF/Word/Excel), area de transferencia, E-MAIL (com confirmacao), OBSIDIAN (vault),
memoria de pastas/projetos e MULTIAGENTE.

Dependencias pesadas sao importadas SOB DEMANDA (dentro de cada ferramenta), com
mensagem amigavel de "pip install ..." quando faltarem — assim o base roda mesmo
sem tudo instalado.
"""

import fnmatch
import json
import os
import subprocess
from pathlib import Path

import requests

import kemy_config as cfg


# ---------------------------------------------------------------------------
# Arquivos e caminhos (SEM trava de pasta — usa a pasta-raiz atual do estado)
# ---------------------------------------------------------------------------

def _resolve_path(rel_path: str) -> Path:
    return (cfg.STATE.root / rel_path).expanduser().resolve()


def tool_read_file(path: str) -> str:
    return _resolve_path(path).read_text(encoding="utf-8")


def tool_write_file(path: str, content: str) -> str:
    p = _resolve_path(path)
    if not cfg.confirm(f"Escrever/sobrescrever o arquivo: {p} ({len(content)} caracteres)"):
        return "Acao cancelada pelo usuario."
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Arquivo gravado: {p}"


def tool_list_dir(path: str = ".") -> str:
    p = _resolve_path(path)
    entries = sorted(p.iterdir(), key=lambda e: e.name)
    return "\n".join(e.name + "/" if e.is_dir() else e.name for e in entries)


def tool_run_command(command: str) -> str:
    if not cfg.confirm(f"Rodar o comando de shell: {command}"):
        return "Acao cancelada pelo usuario."
    try:
        result = subprocess.run(
            command, cwd=cfg.STATE.root, shell=True,
            capture_output=True, text=True, timeout=120,
        )
        out = (result.stdout or "") + (result.stderr or "")
        return out.strip() or "(comando executado sem saida)"
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao executar comando: {exc}"


# ---------------------------------------------------------------------------
# Busca recursiva no disco
# ---------------------------------------------------------------------------

def _walk_limited(base: Path, max_depth: int):
    base_depth = len(base.parts)
    for root, dirs, files in os.walk(base, onerror=lambda e: None):
        depth = len(Path(root).parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [
            d for d in sorted(dirs)
            if d not in cfg.SEARCH_SKIP_DIRS and not d.startswith(".")
        ]
        yield root, sorted(files)


def tool_find_files(pattern: str, path: str = ".", max_depth: int = None) -> str:
    max_depth = cfg.SEARCH_MAX_DEPTH if max_depth is None else max_depth
    base = _resolve_path(path)
    if not base.exists():
        return f"Caminho inexistente: {base}"
    pat = pattern.lower()
    hits = []
    for root, files in _walk_limited(base, max_depth):
        for name in files:
            if fnmatch.fnmatch(name.lower(), pat):
                hits.append(str(Path(root) / name))
                if len(hits) >= cfg.SEARCH_MAX_RESULTS:
                    hits.append(f"(... limite de {cfg.SEARCH_MAX_RESULTS} resultados atingido)")
                    return "\n".join(hits)
    return "\n".join(hits) or f"(nenhum arquivo casando '{pattern}' em {base})"


def tool_search_text(query: str, path: str = ".", file_glob: str = "*", max_depth: int = None) -> str:
    max_depth = cfg.SEARCH_MAX_DEPTH if max_depth is None else max_depth
    base = _resolve_path(path)
    if not base.exists():
        return f"Caminho inexistente: {base}"
    needle = query.lower()
    fglob = file_glob.lower()
    out = []
    for root, files in _walk_limited(base, max_depth):
        for name in files:
            if not fnmatch.fnmatch(name.lower(), fglob):
                continue
            fp = Path(root) / name
            try:
                with fp.open("r", encoding="utf-8", errors="ignore") as fh:
                    for lineno, line in enumerate(fh, 1):
                        if needle in line.lower():
                            out.append(f"{fp}:{lineno}: {line.strip()[:200]}")
                            if len(out) >= cfg.SEARCH_MAX_RESULTS:
                                out.append(f"(... limite de {cfg.SEARCH_MAX_RESULTS} ocorrencias atingido)")
                                return "\n".join(out)
            except (OSError, ValueError):
                continue
    return "\n".join(out) or f"(nenhuma ocorrencia de '{query}' em {base})"


# ---------------------------------------------------------------------------
# WEB — baixar pagina e pesquisar
# ---------------------------------------------------------------------------

def _html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        import re
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return "\n".join(l for l in (soup.get_text("\n").splitlines()) if l.strip())


def tool_fetch_url(url: str, max_chars: int = 8000) -> str:
    """Baixa uma URL e devolve o texto limpo (sem HTML). Para 'resuma esse link'."""
    if not cfg.confirm(f"Acessar a web (baixar): {url}"):
        return "Acao cancelada pelo usuario."
    try:
        resp = requests.get(
            url, timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (KEMY_AI)"},
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao acessar {url}: {exc}"
    ctype = resp.headers.get("Content-Type", "")
    if "html" in ctype or "<html" in resp.text[:500].lower():
        text = _html_to_text(resp.text)
    else:
        text = resp.text
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n(... truncado em {max_chars} caracteres)"
    return f"[{url}]\n{text}"


def tool_web_search(query: str, max_results: int = 6) -> str:
    """Pesquisa na web (DuckDuckGo, sem chave). Retorna titulo + link + resumo."""
    if not cfg.confirm(f"Pesquisar na web: {query}"):
        return "Acao cancelada pelo usuario."
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (KEMY_AI)"},
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return f"Erro na busca: {exc}"
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        return ("Para a busca web funcionar bem instale o beautifulsoup4:\n"
                "    pip install beautifulsoup4\n"
                "(a K.E.M.Y consegue usar fetch_url mesmo sem ele.)")
    soup = BeautifulSoup(resp.text, "html.parser")
    out = []
    for res in soup.select(".result")[:max_results]:
        a = res.select_one(".result__a")
        snippet = res.select_one(".result__snippet")
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        link = a.get("href", "")
        desc = snippet.get_text(" ", strip=True) if snippet else ""
        out.append(f"- {title}\n  {link}\n  {desc}")
    return "\n".join(out) or f"(nenhum resultado para '{query}')"


# ---------------------------------------------------------------------------
# DOCUMENTOS — ler PDF / Word / Excel / CSV / texto
# ---------------------------------------------------------------------------

def tool_read_document(path: str, max_chars: int = 12000) -> str:
    """Le o conteudo textual de um documento: .pdf, .docx, .xlsx/.xls, .csv ou texto."""
    p = _resolve_path(path)
    if not p.exists():
        return f"Arquivo inexistente: {p}"
    ext = p.suffix.lower()
    try:
        if ext == ".pdf":
            text = _read_pdf(p)
        elif ext == ".docx":
            text = _read_docx(p)
        elif ext in (".xlsx", ".xlsm", ".xls"):
            text = _read_xlsx(p)
        else:
            text = p.read_text(encoding="utf-8", errors="ignore")
    except _MissingDep as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao ler {p}: {exc}"
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n(... truncado em {max_chars} caracteres)"
    return f"[{p.name}]\n{text}"


class _MissingDep(Exception):
    pass


def _need(module: str, pip_name: str):
    try:
        return __import__(module)
    except ImportError:
        raise _MissingDep(
            f"Falta a biblioteca '{pip_name}' para este tipo de arquivo. Instale com:\n"
            f"    pip install {pip_name}"
        )


def _read_pdf(p: Path) -> str:
    _need("pypdf", "pypdf")
    from pypdf import PdfReader  # type: ignore
    reader = PdfReader(str(p))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx(p: Path) -> str:
    _need("docx", "python-docx")
    import docx  # type: ignore
    doc = docx.Document(str(p))
    parts = [para.text for para in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _read_xlsx(p: Path) -> str:
    _need("openpyxl", "openpyxl")
    import openpyxl  # type: ignore
    wb = openpyxl.load_workbook(str(p), data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"== Planilha: {ws.title} ==")
        for row in ws.iter_rows(values_only=True):
            cells = ["" if c is None else str(c) for c in row]
            if any(cells):
                out.append(" | ".join(cells))
    wb.close()
    return "\n".join(out)


# ---------------------------------------------------------------------------
# DOCUMENTOS — editar Word (.docx) e Excel (.xlsx)
# ---------------------------------------------------------------------------

def tool_edit_docx(path: str, action: str, text: str = "", find: str = "") -> str:
    """Edita um Word .docx. action: 'append' (adiciona paragrafo com `text`),
    'replace' (troca `find` por `text` em todo o documento) ou 'create' (cria novo)."""
    p = _resolve_path(path)
    if not cfg.confirm(f"Editar Word ({action}): {p}"):
        return "Acao cancelada pelo usuario."
    try:
        _need("docx", "python-docx")
        import docx  # type: ignore
    except _MissingDep as exc:
        return str(exc)
    try:
        if action == "create" or not p.exists():
            doc = docx.Document()
            if text:
                doc.add_paragraph(text)
        else:
            doc = docx.Document(str(p))
            if action == "append":
                doc.add_paragraph(text)
            elif action == "replace":
                n = 0
                for para in doc.paragraphs:
                    if find and find in para.text:
                        para.text = para.text.replace(find, text)
                        n += 1
                if n == 0:
                    return f"'{find}' nao encontrado no documento (nada alterado)."
            else:
                return f"action invalida: {action} (use append/replace/create)"
        p.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(p))
        return f"Word salvo: {p}"
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao editar {p}: {exc}"


def tool_edit_excel(path: str, sheet: str = "", cell: str = "", value: str = "",
                    append_row: str = "") -> str:
    """Edita um Excel .xlsx. Use `cell`+`value` para setar uma celula (ex cell='B2'),
    ou `append_row` (valores separados por '|') para adicionar uma linha ao fim."""
    p = _resolve_path(path)
    if not cfg.confirm(f"Editar Excel: {p} (sheet={sheet or 'ativa'})"):
        return "Acao cancelada pelo usuario."
    try:
        _need("openpyxl", "openpyxl")
        import openpyxl  # type: ignore
    except _MissingDep as exc:
        return str(exc)
    try:
        if p.exists():
            wb = openpyxl.load_workbook(str(p))
        else:
            wb = openpyxl.Workbook()
        ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb.active
        did = []
        if cell and value != "":
            ws[cell] = value
            did.append(f"{ws.title}!{cell} = {value}")
        if append_row:
            row = [v.strip() for v in append_row.split("|")]
            ws.append(row)
            did.append(f"linha adicionada em {ws.title}: {row}")
        if not did:
            return "Nada a fazer: passe cell+value ou append_row."
        p.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(p))
        return "Excel salvo: " + p.as_posix() + "\n" + "\n".join(did)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao editar {p}: {exc}"


# ---------------------------------------------------------------------------
# Area de transferencia
# ---------------------------------------------------------------------------

def tool_clipboard_read() -> str:
    try:
        _need("pyperclip", "pyperclip")
        import pyperclip  # type: ignore
    except _MissingDep as exc:
        return str(exc)
    return pyperclip.paste() or "(area de transferencia vazia)"


def tool_clipboard_write(text: str) -> str:
    try:
        _need("pyperclip", "pyperclip")
        import pyperclip  # type: ignore
    except _MissingDep as exc:
        return str(exc)
    pyperclip.copy(text)
    return f"Copiado para a area de transferencia ({len(text)} caracteres)."


# ---------------------------------------------------------------------------
# E-MAIL — envio pela conta do usuario (SEMPRE mostra e pede confirmacao)
# ---------------------------------------------------------------------------

def tool_send_email(to: str, subject: str, body: str) -> str:
    """Envia um e-mail pela conta configurada. SEMPRE mostra o e-mail e pede
    confirmacao antes de enviar (mesmo no modo automatico)."""
    preview = (
        f"De:      {cfg.EMAIL_FROM}\n"
        f"Para:    {to}\n"
        f"Assunto: {subject}\n"
        f"---\n{body}\n---"
    )
    if not cfg.confirm_always("Enviar este e-mail?\n\n" + preview):
        return "Envio cancelado pelo usuario."
    if not cfg.EMAIL_APP_PASSWORD:
        return ("Falta a senha de app do Gmail. Defina a variavel de ambiente "
                "KEMY_EMAIL_APP_PASSWORD (senha de app, NAO a senha normal) — gere em "
                "https://myaccount.google.com/apppasswords . O e-mail NAO foi enviado.")
    import smtplib
    from email.mime.text import MIMEText
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = cfg.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    try:
        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=30) as srv:
            srv.starttls()
            srv.login(cfg.EMAIL_USER, cfg.EMAIL_APP_PASSWORD)
            srv.sendmail(cfg.EMAIL_FROM, [to], msg.as_string())
        return f"E-mail enviado para {to}."
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao enviar e-mail: {exc}"


# ---------------------------------------------------------------------------
# OBSIDIAN — conexao direta com o vault de projetos
# ---------------------------------------------------------------------------

def tool_obsidian_list_projects() -> str:
    """Lista os projetos do vault do Obsidian (le referencias/mapa-projetos.md e a
    pasta projetos/)."""
    vault = cfg.OBSIDIAN_VAULT
    if not vault.exists():
        return f"Vault do Obsidian nao encontrado em {vault} (ajuste KEMY_OBSIDIAN_VAULT)."
    out = [f"Vault: {vault}"]
    mapa = vault / "referencias" / "mapa-projetos.md"
    if mapa.exists():
        out.append("\n[mapa-projetos.md]")
        out.append(mapa.read_text(encoding="utf-8", errors="ignore"))
    projetos = vault / "projetos"
    if projetos.exists():
        out.append("\n[pastas em projetos/]")
        out += [f"- {d.name}" for d in sorted(projetos.iterdir()) if d.is_dir()]
    return "\n".join(out)


def tool_obsidian_read_note(name: str) -> str:
    """Le uma nota do vault pelo nome (com ou sem .md). Procura recursivamente."""
    vault = cfg.OBSIDIAN_VAULT
    target = name if name.lower().endswith(".md") else name + ".md"
    for root, _dirs, files in os.walk(vault):
        for f in files:
            if f.lower() == target.lower():
                return (Path(root) / f).read_text(encoding="utf-8", errors="ignore")
    return f"Nota '{name}' nao encontrada no vault {vault}."


def tool_obsidian_write_note(name: str, content: str, folder: str = "projetos") -> str:
    """Cria/atualiza uma nota no vault. `folder` e relativo a raiz do vault."""
    vault = cfg.OBSIDIAN_VAULT
    fname = name if name.lower().endswith(".md") else name + ".md"
    p = (vault / folder / fname)
    if not cfg.confirm(f"Escrever nota no Obsidian: {p}"):
        return "Acao cancelada pelo usuario."
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Nota salva: {p}"
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao salvar nota: {exc}"


# ---------------------------------------------------------------------------
# MEMORIA de pastas/projetos que a K.E.M.Y ja usou (hub proprio de dados)
# ---------------------------------------------------------------------------

def _load_known() -> dict:
    try:
        return json.loads(cfg.KNOWN_FOLDERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"pastas": []}


def _save_known(data: dict) -> None:
    cfg.ensure_dirs()
    cfg.KNOWN_FOLDERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def remember_folder(path: Path, projeto: str = "") -> None:
    """Registra (sem UI) uma pasta usada + projeto, no hub de dados da K.E.M.Y."""
    data = _load_known()
    sp = str(path)
    for item in data["pastas"]:
        if item.get("caminho") == sp:
            if projeto and projeto not in item.get("projetos", []):
                item.setdefault("projetos", []).append(projeto)
            return _save_known(data)
    data["pastas"].append({"caminho": sp, "projetos": [projeto] if projeto else []})
    _save_known(data)


def tool_remember_folder(path: str, projeto: str = "") -> str:
    p = _resolve_path(path)
    remember_folder(p, projeto)
    return f"Anotei a pasta {p}" + (f" (projeto: {projeto})" if projeto else "") + "."


def tool_list_known_folders() -> str:
    data = _load_known()
    if not data["pastas"]:
        return "Ainda nao anotei nenhuma pasta."
    out = []
    for item in data["pastas"]:
        projs = ", ".join(item.get("projetos", [])) or "-"
        out.append(f"- {item['caminho']}  (projetos: {projs})")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# MULTIAGENTE — dispara varios agentes em paralelo
# ---------------------------------------------------------------------------

def tool_spawn_agents(tasks: list) -> str:
    """Roda varias sub-tarefas em paralelo, cada uma num agente independente, e
    devolve os resultados juntos. `tasks` e uma lista de strings (as tarefas)."""
    import kemy_agents
    if isinstance(tasks, str):
        tasks = [tasks]
    return kemy_agents.run_agents([str(t) for t in tasks])


# ---------------------------------------------------------------------------
# Registro das ferramentas
# ---------------------------------------------------------------------------

TOOL_IMPLS = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "list_dir": tool_list_dir,
    "find_files": tool_find_files,
    "search_text": tool_search_text,
    "run_command": tool_run_command,
    "fetch_url": tool_fetch_url,
    "web_search": tool_web_search,
    "read_document": tool_read_document,
    "edit_docx": tool_edit_docx,
    "edit_excel": tool_edit_excel,
    "clipboard_read": tool_clipboard_read,
    "clipboard_write": tool_clipboard_write,
    "send_email": tool_send_email,
    "obsidian_list_projects": tool_obsidian_list_projects,
    "obsidian_read_note": tool_obsidian_read_note,
    "obsidian_write_note": tool_obsidian_write_note,
    "remember_folder": tool_remember_folder,
    "list_known_folders": tool_list_known_folders,
    "spawn_agents": tool_spawn_agents,
}


def _fn(name, description, properties, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


_S = {"type": "string"}
_I = {"type": "integer"}

TOOL_DEFINITIONS = [
    _fn("read_file", "Le um arquivo de TEXTO. Caminho relativo ou absoluto.",
        {"path": {**_S, "description": "Caminho do arquivo"}}, ["path"]),
    _fn("write_file", "Cria/sobrescreve um arquivo de texto. Caminho relativo ou absoluto.",
        {"path": _S, "content": {**_S, "description": "Conteudo completo"}}, ["path", "content"]),
    _fn("list_dir", "Lista arquivos e pastas de um diretorio.",
        {"path": {**_S, "description": "Caminho (padrao '.')"}}),
    _fn("find_files", "Procura arquivos por NOME (glob, ex '*.pdf') recursivamente a partir de um caminho.",
        {"pattern": _S, "path": _S, "max_depth": _I}, ["pattern"]),
    _fn("search_text", "Procura um TEXTO dentro dos arquivos (grep) recursivamente. Retorna arquivo:linha:trecho.",
        {"query": _S, "path": _S, "file_glob": {**_S, "description": "ex '*.md' (padrao '*')"}, "max_depth": _I}, ["query"]),
    _fn("run_command", "Executa um comando de shell e retorna a saida.",
        {"command": _S}, ["command"]),
    _fn("fetch_url", "Acessa a WEB: baixa uma URL e devolve o texto limpo (sem HTML). Para resumir links.",
        {"url": _S, "max_chars": _I}, ["url"]),
    _fn("web_search", "Pesquisa na WEB (DuckDuckGo). Retorna titulos, links e resumos.",
        {"query": _S, "max_results": _I}, ["query"]),
    _fn("read_document", "Le o texto de um DOCUMENTO: PDF, Word (.docx), Excel (.xlsx), CSV ou texto.",
        {"path": _S, "max_chars": _I}, ["path"]),
    _fn("edit_docx", "Edita um Word .docx. action: 'append' (adiciona paragrafo `text`), 'replace' (troca `find` por `text`) ou 'create'.",
        {"path": _S, "action": {**_S, "description": "append | replace | create"}, "text": _S, "find": _S}, ["path", "action"]),
    _fn("edit_excel", "Edita um Excel .xlsx. Use cell+value (ex cell='B2') para setar celula, ou append_row (valores separados por '|') para adicionar linha.",
        {"path": _S, "sheet": _S, "cell": _S, "value": _S, "append_row": _S}, ["path"]),
    _fn("clipboard_read", "Le o conteudo atual da area de transferencia.", {}),
    _fn("clipboard_write", "Copia um texto para a area de transferencia.", {"text": _S}, ["text"]),
    _fn("send_email", "Envia um E-MAIL pela conta do usuario. SEMPRE mostra o e-mail e pede confirmacao antes.",
        {"to": _S, "subject": _S, "body": _S}, ["to", "subject", "body"]),
    _fn("obsidian_list_projects", "Lista os PROJETOS do vault do Obsidian (le o mapa-projetos e a pasta projetos/).", {}),
    _fn("obsidian_read_note", "Le uma nota do vault do Obsidian pelo nome (procura recursivamente).",
        {"name": _S}, ["name"]),
    _fn("obsidian_write_note", "Cria/atualiza uma nota no vault do Obsidian. `folder` relativo a raiz do vault (padrao 'projetos').",
        {"name": _S, "content": _S, "folder": _S}, ["name", "content"]),
    _fn("remember_folder", "Anota (na memoria da K.E.M.Y) uma pasta usada e, opcional, o projeto dela.",
        {"path": _S, "projeto": _S}, ["path"]),
    _fn("list_known_folders", "Lista as pastas/projetos que a K.E.M.Y ja anotou.", {}),
    _fn("spawn_agents", "Dispara VARIOS agentes em paralelo, um por tarefa, e junta os resultados. `tasks`: lista de tarefas (strings).",
        {"tasks": {"type": "array", "items": _S, "description": "Lista de tarefas independentes"}}, ["tasks"]),
]
