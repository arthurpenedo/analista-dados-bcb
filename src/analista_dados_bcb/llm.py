"""Gerador de SQL com modelo aberto local (Ollama). Gratuito: roda na sua máquina, sem API paga."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Callable

from .db import ESQUEMA_TEXTO

OLLAMA = "http://localhost:11434/api/generate"
MODELO_PADRAO = "qwen2.5-coder:3b"

PROMPT = """Você converte perguntas em português em UMA consulta SQL DuckDB (somente SELECT/WITH).
Tabelas disponíveis (use só estas, exatamente com estes nomes de coluna):
{esquema}
Regras:
- Responda apenas com o SQL, sem explicação.
- Para "mais recente"/"último", use subconsulta com max()/ORDER BY ... DESC LIMIT 1 em vez de datas fixas.
- Nomes de bancos estão em MAIÚSCULAS e às vezes sem acento (use strip_accents(instituicao) ILIKE '%itau%').
- Sempre use LIMIT quando pedirem "top" ou "quais bancos".
{erro}
Pergunta: {pergunta}
SQL:"""

Chamar = Callable[[str, str], str]


def chamar_ollama(prompt: str, modelo: str) -> str:
    corpo = json.dumps({"model": modelo, "prompt": prompt, "stream": False,
                        "options": {"temperature": 0, "num_predict": 400}}).encode()
    req = urllib.request.Request(OLLAMA, corpo, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["response"]


def ollama_disponivel() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2).read()
        return True
    except Exception:
        return False


def extrair_sql(resposta: str) -> str:
    """Pega o SQL de dentro de ```sql ... ``` ou o texto inteiro."""
    bloco = re.search(r"```(?:sql)?\s*(.*?)```", resposta, re.S | re.I)
    return (bloco.group(1) if bloco else resposta).strip().rstrip(";").strip()


def gerar_sql(pergunta: str, modelo: str = MODELO_PADRAO, chamar: Chamar = chamar_ollama,
              erro_anterior: str | None = None) -> str:
    erro = f"Sua tentativa anterior falhou: {erro_anterior}. Corrija.\n" if erro_anterior else ""
    return extrair_sql(chamar(PROMPT.format(esquema=ESQUEMA_TEXTO, pergunta=pergunta, erro=erro), modelo))
