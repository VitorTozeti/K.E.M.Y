#!/usr/bin/env python3
"""
kemy_server.py — servidor web local simples para a K.E.M.Y.

Serve o index.html e uma API JSON (/api/chat, /api/status, /api/reset, /api/mode)
reaproveitando a MESMA logica do terminal (kemy.run_turn + as 20 ferramentas). Assim
voce usa a K.E.M.Y pelo navegador OU pelo terminal (`python kemy.py`), com o mesmo cerebro.

Uso:
    python kemy_server.py            # abre em http://localhost:8000
    python kemy_server.py 9000       # porta customizada

So use localmente. Nao ha autenticacao; nao exponha esta porta na internet.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import kemy_config as cfg
import kemy  # run_turn, call_with_fallback

HERE = Path(__file__).resolve().parent
INDEX = HERE / "index.html"

# Sessao unica em memoria (simples por enquanto). Protegida por lock: um chat por vez.
_SESSION = [{"role": "system", "content": cfg.SYSTEM_PROMPT}]
_LOCK = threading.Lock()

# No modo web nao ha terminal para responder s/N -> nao trava em confirmacoes.
cfg.STATE.assume_yes = True


def _status() -> dict:
    return {
        "modelo": cfg.current_model(),
        "rodizio": cfg.MODEL_ROTATION,
        "pasta": str(cfg.STATE.root),
        "vault": str(cfg.OBSIDIAN_VAULT),
        "ferramentas": sorted(kemy.tools.TOOL_IMPLS.keys()),
        "mensagens": len(_SESSION) - 1,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencia o log padrao ruidoso
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: dict, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    # ------------------------------------------------------------------
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            if INDEX.exists():
                self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"index.html nao encontrado", "text/plain; charset=utf-8")
        elif self.path == "/api/status":
            self._json(_status())
        else:
            self._send(404, b"nao encontrado", "text/plain; charset=utf-8")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            return self._json({"erro": "JSON invalido"}, 400)

        if self.path == "/api/reset":
            with _LOCK:
                del _SESSION[1:]
            return self._json({"ok": True, **_status()})

        if self.path == "/api/mode":
            cfg.STATE.confirm_mode = bool(data.get("seguro", False))
            return self._json({"ok": True, "seguro": cfg.STATE.confirm_mode})

        if self.path == "/api/chat":
            msg = (data.get("message") or "").strip()
            if not msg:
                return self._json({"erro": "mensagem vazia"}, 400)
            eventos = []
            with _LOCK:
                _SESSION.append({"role": "user", "content": msg})
                n = len(_SESSION)
                try:
                    reply = kemy.run_turn(
                        _SESSION,
                        emit=lambda kind, text: eventos.append({"tipo": kind, "texto": text}),
                    )
                except Exception as exc:  # noqa: BLE001
                    del _SESSION[n - 1:]
                    return self._json({"erro": str(exc)}, 500)
            return self._json({"reply": reply, "eventos": eventos, "modelo": cfg.current_model()})

        self._json({"erro": "rota desconhecida"}, 404)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    cfg.ensure_dirs()
    kemy.tools.remember_folder(cfg.STATE.root)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"K.E.M.Y web em http://localhost:{port}  (Ctrl+C para parar)")
    print(f"Modelo: {cfg.current_model()} | Ferramentas: {len(kemy.tools.TOOL_IMPLS)}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando.")
        srv.shutdown()


if __name__ == "__main__":
    main()
