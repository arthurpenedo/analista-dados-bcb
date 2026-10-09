"""Trava do SQL gerado: só uma consulta de leitura, só nas tabelas permitidas.

Duas camadas, porque SQL vindo de um modelo não é confiável:
1. `validar` olha o texto (um comando, começa com SELECT/WITH, sem palavras de escrita,
   toda tabela no FROM/JOIN precisa estar na lista, sem funções que leem arquivos).
2. `executar_seguro` roda numa conexão somente leitura, com acesso externo desligado e config travada.
"""

from __future__ import annotations

import re

import duckdb

from .db import TABELAS

PROIBIDAS = {
    "insert", "update", "delete", "drop", "create", "alter", "attach", "detach", "copy", "export",
    "import", "pragma", "install", "load", "call", "set", "reset", "truncate", "merge", "vacuum",
    "checkpoint", "begin", "commit", "rollback", "grant", "use", "describe", "show", "summarize",
    "explain", "prepare", "execute",
}
FUNCAO_PROIBIDA = re.compile(
    r"^(read_|write_|glob|getenv|current_setting|duckdb_|pragma_|sniff_|parquet_|query|iceberg|delta_|http|"
    r"load_|install_|which_secret|list_secrets|summary|sqlite_)",
    re.I,
)
FIM_DE_FROM = {"where", "group", "order", "having", "limit", "union", "intersect", "except", "qualify",
               "window", "offset", "fetch"}


class SQLRecusado(ValueError):
    pass


def _tokens(sql: str) -> list[str]:
    sem_comentario = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.S)
    return re.findall(
        r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|[A-Za-z_][A-Za-z_0-9$]*|\d+(?:\.\d+)?|::|<>|<=|>=|\|\||\S",
        sem_comentario,
    )


def _nome(token: str) -> str:
    return token[1:-1].replace('""', '"').lower() if token.startswith('"') else token.lower()


def validar(sql: str, tabelas: tuple[str, ...] = TABELAS) -> str:
    """Devolve o SQL limpo (sem ';' final) ou levanta SQLRecusado."""
    limpo = sql.strip().rstrip(";").strip()
    if not limpo:
        raise SQLRecusado("SQL vazio")
    toks = _tokens(limpo)
    if ";" in toks:
        raise SQLRecusado("mais de um comando")
    if _nome(toks[0]) not in ("select", "with", "from"):
        raise SQLRecusado("só consultas SELECT/WITH são aceitas")

    # CTEs: "WITH nome AS (" e ", nome AS ("
    ctes = {_nome(toks[i]) for i in range(len(toks) - 2)
            if toks[i + 1].lower() == "as" and toks[i + 2] == "(" and re.match(r"[\"A-Za-z_]", toks[i])
            and (i == 1 or toks[i - 1] in (",",) or _nome(toks[i - 1]) in ("with", "recursive"))}

    permitidas = {t.lower() for t in tabelas} | ctes
    esperando_tabela = False
    # um item por nível de parêntese: [dentro de uma lista FROM (para vírgulas), é argumento de função com FROM]
    pilha: list[list[bool]] = [[False, False]]
    i = 0
    while i < len(toks):
        tok = toks[i]
        baixo = tok.lower()
        eh_nome = bool(re.match(r"[A-Za-z_]", tok))
        if eh_nome and baixo in PROIBIDAS:
            raise SQLRecusado(f"palavra proibida: {baixo}")
        if eh_nome and FUNCAO_PROIBIDA.match(baixo) and i + 1 < len(toks) and toks[i + 1] == "(":
            raise SQLRecusado(f"função proibida: {baixo}")
        if tok == "(":
            anterior = toks[i - 1].lower() if i else ""
            # tabela esperada + "(" = subconsulta (ok) ou função de tabela (barrada)
            if esperando_tabela and _nome(toks[i + 1]) not in ("select", "with", "from"):
                raise SQLRecusado("função de tabela não permitida")
            pilha.append([False, anterior in ("extract", "trim", "substring", "overlay", "position")])
            esperando_tabela = False
        elif tok == ")":
            if len(pilha) > 1:
                pilha.pop()
        elif eh_nome and baixo in ("from", "join") and not pilha[-1][1] and not (
            baixo == "from" and i and toks[i - 1].lower() == "distinct"
        ):
            esperando_tabela = True
            pilha[-1][0] = True
        elif esperando_tabela:
            nome = _nome(tok)
            if i + 1 < len(toks) and toks[i + 1] == "(":
                raise SQLRecusado("função de tabela não permitida")
            if i + 1 < len(toks) and toks[i + 1] == ".":
                raise SQLRecusado("nomes qualificados (esquema.tabela) não são aceitos")
            if tok.startswith("'"):
                raise SQLRecusado("arquivo/URL no FROM não permitido")
            if nome not in permitidas:
                raise SQLRecusado(f"tabela não permitida: {nome}")
            esperando_tabela = False
        elif tok == "," and pilha[-1][0]:
            esperando_tabela = True
        elif eh_nome and baixo in FIM_DE_FROM:
            pilha[-1][0] = False
        i += 1
    return limpo


def conexao_segura(caminho: str) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(caminho, read_only=True)
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    return con


def executar_seguro(caminho: str, sql: str, limite: int = 1000) -> tuple[list[str], list[tuple]]:
    """Valida e executa. Devolve (colunas, linhas)."""
    limpo = validar(sql)
    con = conexao_segura(caminho)
    try:
        cur = con.execute(f"SELECT * FROM ({limpo}) AS _r LIMIT {int(limite)}")
        return [d[0] for d in cur.description], cur.fetchall()
    finally:
        con.close()
