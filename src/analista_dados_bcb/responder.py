"""Pergunta -> SQL -> trava -> execução -> tabela, gráfico e o SQL usado."""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

from . import llm, regras
from .trava import SQLRecusado, executar_seguro


@dataclass
class Resposta:
    pergunta: str
    motor: str
    sql: str | None = None
    colunas: list[str] = field(default_factory=list)
    linhas: list[tuple] = field(default_factory=list)
    erro: str | None = None

    @property
    def ok(self) -> bool:
        return self.erro is None


def _instituicoes(banco: str) -> list[str]:
    con = duckdb.connect(banco, read_only=True)
    try:
        return [r[0] for r in con.execute(
            "SELECT instituicao FROM reclamacoes UNION SELECT instituicao FROM juros_semanal "
            "UNION SELECT instituicao FROM juros_mensal").fetchall() if r[0]]
    finally:
        con.close()


def perguntar(banco: str, pergunta: str, motor: str = "regras", modelo: str = llm.MODELO_PADRAO,
              chamar: llm.Chamar = llm.chamar_ollama) -> Resposta:
    """motor: 'regras' (sem modelo), 'ollama' (modelo aberto local) ou 'auto' (regras e, se não souber, Ollama)."""
    if motor in ("regras", "auto"):
        sql = regras.gerar_sql(pergunta, _instituicoes(banco))
        if sql:
            return _executar(banco, pergunta, "regras", sql)
        if motor == "regras":
            return Resposta(pergunta, "regras", erro="não entendi a pergunta (tente --motor ollama)")
    return _com_modelo(banco, pergunta, modelo, chamar)


def _executar(banco: str, pergunta: str, motor: str, sql: str) -> Resposta:
    try:
        colunas, linhas = executar_seguro(banco, sql)
        return Resposta(pergunta, motor, sql, colunas, linhas)
    except (SQLRecusado, duckdb.Error) as e:
        return Resposta(pergunta, motor, sql, erro=f"{type(e).__name__}: {e}")


def _com_modelo(banco, pergunta, modelo, chamar) -> Resposta:
    erro = None
    for _ in range(2):  # uma tentativa + uma correção devolvendo o erro ao modelo
        try:
            sql = llm.gerar_sql(pergunta, modelo, chamar, erro)
        except Exception as e:  # noqa: BLE001 - Ollama fora do ar, modelo não baixado, etc.: vira resposta com erro
            return Resposta(pergunta, "ollama", erro=f"modelo indisponível: {e}")
        r = _executar(banco, pergunta, "ollama", sql)
        if r.ok:
            return r
        erro = r.erro
    return r


def formatar(r: Resposta) -> str:
    if not r.ok:
        return f"Não consegui responder: {r.erro}" + (f"\nSQL tentado:\n{r.sql}" if r.sql else "")
    partes = [tabela(r.colunas, r.linhas)]
    graf = grafico(r.colunas, r.linhas)
    if graf:
        partes.append(graf)
    partes.append(f"SQL usado ({r.motor}):\n{r.sql}")
    return "\n\n".join(partes)


def _fmt(v) -> str:
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def tabela(colunas: list[str], linhas: list[tuple]) -> str:
    if not linhas:
        return "(sem linhas)"
    cel = [colunas] + [[_fmt(v) for v in linha] for linha in linhas]
    larg = [max(len(str(linha[i])) for linha in cel) for i in range(len(colunas))]

    def fmt(linha):
        return " | ".join(str(v).ljust(w) for v, w in zip(linha, larg, strict=True))

    return "\n".join([fmt(cel[0]), "-+-".join("-" * w for w in larg)] + [fmt(linha) for linha in cel[1:]])


def grafico(colunas: list[str], linhas: list[tuple], largura: int = 30) -> str | None:
    """Barras em texto quando o resultado é (rótulo, número) com 2 a 30 linhas."""
    if len(colunas) < 2 or not 2 <= len(linhas) <= 30:
        return None
    if not all(isinstance(lin[1], (int, float)) and not isinstance(lin[1], bool) for lin in linhas):
        return None
    maior = max(abs(lin[1]) for lin in linhas) or 1
    rot = max(len(str(lin[0])) for lin in linhas)
    return "\n".join(f"{str(lin[0]).ljust(rot)} {'█' * max(1, round(abs(lin[1]) / maior * largura))} {_fmt(lin[1])}"
                     for lin in linhas)
