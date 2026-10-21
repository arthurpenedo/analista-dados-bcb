"""Mede acerto por execução: o resultado do SQL gerado é igual ao do SQL de referência?"""

from __future__ import annotations

import time
from dataclasses import dataclass

from . import llm
from .perguntas import PERGUNTAS
from .responder import perguntar
from .trava import executar_seguro


def normalizar_linhas(linhas: list[tuple]) -> list[tuple]:
    """Ignora nomes de coluna e ordem das linhas; números comparados com 4 casas."""
    def v(x):
        return round(x, 4) if isinstance(x, float) else x
    return sorted((tuple(v(x) for x in l) for l in linhas), key=repr)


@dataclass
class Item:
    id: str
    pergunta: str
    acertou: bool
    motivo: str  # "ok", "sem SQL", "erro de execução", "resultado diferente"
    sql: str | None
    segundos: float


def rodar(banco: str, motor: str = "regras", modelo: str = llm.MODELO_PADRAO, chamar=llm.chamar_ollama,
          perguntas=PERGUNTAS) -> list[Item]:
    itens = []
    for id_, pergunta, ref_sql in perguntas:
        _, esperado = executar_seguro(banco, ref_sql)  # a referência também passa pela trava
        t = time.time()
        r = perguntar(banco, pergunta, motor, modelo, chamar)
        dt = time.time() - t
        if r.sql is None:
            itens.append(Item(id_, pergunta, False, "sem SQL", None, dt))
        elif not r.ok:
            itens.append(Item(id_, pergunta, False, "erro de execução", r.sql, dt))
        elif normalizar_linhas(r.linhas) == normalizar_linhas(esperado):
            itens.append(Item(id_, pergunta, True, "ok", r.sql, dt))
        else:
            itens.append(Item(id_, pergunta, False, "resultado diferente", r.sql, dt))
    return itens


def pagina_html(itens: list[Item], motor: str = "regras") -> str:
    """Página estática: cada pergunta, o SQL gerado e se o resultado bateu com a referência."""
    from html import escape

    acertos = sum(i.acertou for i in itens)
    total = len(itens) or 1
    linhas = "".join(
        "<tr class='{cls}'><td>{id}</td><td>{perg}</td><td><code>{sql}</code></td><td>{res}</td></tr>".format(
            cls="ok" if i.acertou else "erro",
            id=escape(i.id),
            perg=escape(i.pergunta),
            sql=escape(i.sql or "(sem SQL)"),
            res="certo" if i.acertou else "errado: " + escape(i.motivo),
        )
        for i in itens
    )
    css = (
        "body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}"
        "table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #ddd;padding:.4rem;"
        "text-align:left;vertical-align:top}code{font-size:.8rem;word-break:break-word}"
        "tr.ok td:last-child{color:#0a6b2d}tr.erro td:last-child{color:#b00020;font-weight:600}"
    )
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        f"<title>analista-dados-bcb: benchmark</title><style>{css}</style></head><body>"
        "<h1>analista-dados-bcb: benchmark</h1>"
        f"<p>Motor <b>{escape(motor)}</b>: <b>{acertos}/{len(itens)}</b> ({100 * acertos / total:.1f}%) "
        "de acerto por execução (resultado do SQL gerado igual ao do SQL de referência). "
        "<a href='https://github.com/arthurpenedo/analista-dados-bcb'>Código no GitHub</a>.</p>"
        "<table><tr><th>id</th><th>Pergunta</th><th>SQL gerado</th><th>Resultado</th></tr>"
        f"{linhas}</table>"
        "<p><small>Perguntas e referências escritas pelo autor; dados abertos do Banco Central.</small></p>"
        "</body></html>"
    )


def resumo(itens: list[Item]) -> str:
    por_grupo: dict[str, list[Item]] = {}
    for i in itens:
        por_grupo.setdefault(i.id[0], []).append(i)
    nomes = {"r": "reclamações", "j": "juros", "s": "séries SGS", "c": "cruzando tabelas"}
    linhas = [f"Acerto por execução: {sum(i.acertou for i in itens)}/{len(itens)} "
              f"({100 * sum(i.acertou for i in itens) / len(itens):.1f}%)"]
    for g, lista in por_grupo.items():
        linhas.append(f"  {nomes.get(g, g)}: {sum(i.acertou for i in lista)}/{len(lista)}")
    erros = [i for i in itens if not i.acertou]
    if erros:
        linhas.append("Erros:")
        linhas += [f"  {i.id} [{i.motivo}] {i.pergunta}" for i in erros]
    return "\n".join(linhas)
