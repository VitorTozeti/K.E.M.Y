#!/usr/bin/env python3
"""
kemy_agents.py — multiagente: roda varias tarefas em paralelo, cada uma num agente
independente (chamada de chat simples, sem ferramentas, para ser rapido e seguro),
e junta os resultados. Usado pela ferramenta spawn_agents.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

import kemy_config as cfg

_AGENT_SYSTEM = (
    "Voce e um sub-agente da K.E.M.Y trabalhando em UMA tarefa especifica. "
    "Seja objetivo e responda em portugues do Brasil, so com o resultado da tarefa."
)


def _run_one(task: str) -> str:
    """Roda uma tarefa num modelo gratuito, tentando a fila de rodizio se esgotar."""
    last_err = None
    for model in cfg.MODEL_ROTATION:
        try:
            resp = requests.post(
                cfg.API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {cfg.API_KEY}",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _AGENT_SYSTEM},
                        {"role": "user", "content": task},
                    ],
                    "temperature": 0.3,
                    "max_tokens": cfg.MAX_TOKENS,
                },
                timeout=120,
            )
            if not resp.ok:
                if cfg.looks_exhausted(resp.status_code, resp.text):
                    last_err = f"{resp.status_code} (esgotado)"
                    continue  # tenta proximo modelo
                return f"[erro {resp.status_code}] {resp.text[:200]}"
            data = resp.json()
            return (data["choices"][0]["message"].get("content") or "").strip()
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            continue
    return f"[falhou em todos os modelos] {last_err}"


def run_agents(tasks: list, max_parallel: int = 4) -> str:
    """Dispara as tarefas em paralelo e devolve os resultados numerados, na ordem."""
    if not tasks:
        return "(nenhuma tarefa passada)"
    results = [None] * len(tasks)
    print(f"\n  [multiagente] disparando {len(tasks)} agentes em paralelo...")
    with ThreadPoolExecutor(max_workers=min(max_parallel, len(tasks))) as pool:
        fut_to_idx = {pool.submit(_run_one, t): i for i, t in enumerate(tasks)}
        for fut in as_completed(fut_to_idx):
            idx = fut_to_idx[fut]
            results[idx] = fut.result()
    blocks = []
    for i, (task, res) in enumerate(zip(tasks, results), 1):
        blocks.append(f"=== Agente {i}: {task[:80]} ===\n{res}")
    return "\n\n".join(blocks)
