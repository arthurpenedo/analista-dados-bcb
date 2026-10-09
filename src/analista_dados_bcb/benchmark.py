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
