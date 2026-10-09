"""Coleta das APIs abertas do Banco Central (SGS e Olinda) para o DuckDB. Sem chave, sem custo."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Callable

SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
OLINDA = "https://olinda.bcb.gov.br/olinda/servico/"
SERIES = {432: "selic_meta", 433: "ipca_mensal", 189: "igpm_mensal"}
RANKINGS = {
    "RankingMaioresBancos": "maiores_bancos",
    "RankingDemaisBancos": "demais_bancos",
    "RankingConsorcio": "consorcio",
}
PAGINA = 20000

Buscar = Callable[[str], object]


def buscar_json(url: str, tentativas: int = 3):
    ultimo = None
    for _ in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # rede instável: tenta de novo
            ultimo = e
    raise RuntimeError(f"falha ao buscar {url[:120]}: {ultimo}")


def _paginar(base: str, buscar: Buscar) -> list[dict]:
    linhas, pulo = [], 0
    while True:
        sep = "&" if "?" in base else "?"
        url = f"{base}{sep}$format=json&$top={PAGINA}&$skip={pulo}"
        lote = buscar(url)["value"]
        linhas += lote
        if len(lote) < PAGINA:
            return linhas
        pulo += PAGINA


def _num(texto) -> float | None:
    if texto is None or texto == "":
        return None
    return float(str(texto).replace(".", "").replace(",", ".")) if "," in str(texto) else float(texto)


def coletar_series(con, buscar: Buscar = buscar_json, desde: str = "01/01/2018") -> int:
    hoje = date.today().strftime("%d/%m/%Y")
    total = 0
    for codigo, nome in SERIES.items():
        url = SGS.format(codigo=codigo) + f"?formato=json&dataInicial={desde}&dataFinal={hoje}"
        dados = buscar(url)
        if not isinstance(dados, list):  # a API devolve um objeto de erro (ex.: janela > 10 anos em série diária)
            raise RuntimeError(f"SGS {codigo} devolveu {str(dados)[:200]}")
        con.execute("DELETE FROM serie_sgs WHERE codigo = ?", [codigo])
        linhas = [
            (codigo, nome, datetime.strptime(d["data"], "%d/%m/%Y").date(), float(d["valor"]))
            for d in dados
            if d.get("valor") not in (None, "")
        ]
        con.executemany("INSERT INTO serie_sgs VALUES (?, ?, ?, ?)", linhas)
        total += len(linhas)
    return total


def coletar_reclamacoes(con, buscar: Buscar = buscar_json, ano_inicial: int = 2023) -> int:
    total = 0
    for conjunto, nome in RANKINGS.items():
        base = f"{OLINDA}RankingReclamacoes/versao/v1/odata/{conjunto}?$filter=" + urllib.parse.quote(
            f"Ano ge {ano_inicial}"
        )
        # A API só devolve o período mais recente: apaga só os períodos que chegaram e mantém o histórico.
        dados = _paginar(base, buscar)
        for ano, periodo in {(d["Ano"], d["Periodo"]) for d in dados}:
            con.execute("DELETE FROM reclamacoes WHERE ranking = ? AND ano = ? AND periodo = ?", [nome, ano, periodo])
        linhas = [
            (
                nome, d.get("Posicao"), d.get("Ano"), d.get("Periodo"), d.get("TipoPeriodo"),
                d.get("Categoria"), d.get("Tipo"), d.get("CnpjIf"), d.get("InstituicaoFinanceira"),
                _num(d.get("Indice")),
            )
            for d in dados
        ]
        con.executemany("INSERT INTO reclamacoes VALUES (?,?,?,?,?,?,?,?,?,?)", linhas)
        total += len(linhas)
    return total


def coletar_juros(con, buscar: Buscar = buscar_json, meses: int = 24) -> int:
    hoje = date.today()
    indice = hoje.year * 12 + hoje.month - 1 - meses
    inicio = f"{indice // 12:04d}-{indice % 12 + 1:02d}"
    base = f"{OLINDA}taxaJuros/versao/v2/odata/TaxasJurosMensalPorMes?$filter=" + urllib.parse.quote(
        f"anoMes ge '{inicio}'"
    )
    con.execute("DELETE FROM juros_mensal")
    linhas = [
        (
            d.get("anoMes"), d.get("Modalidade"), d.get("Posicao"), d.get("InstituicaoFinanceira"),
            d.get("TaxaJurosAoMes"), d.get("TaxaJurosAoAno"), d.get("cnpj8"),
        )
        for d in _paginar(base, buscar)
    ]
    con.executemany("INSERT INTO juros_mensal VALUES (?,?,?,?,?,?,?)", linhas)
    return len(linhas)


def coletar_juros_semanal(con, buscar: Buscar = buscar_json, semanas: int = 4) -> int:
    """Taxas de 5 dias úteis (cartão, cheque especial, consignado...) das últimas `semanas` semanas."""
    base = f"{OLINDA}taxaJuros/versao/v2/odata/"
    datas = sorted(
        {d["inicioPeriodo"] for d in buscar(base + "ConsultaDatas?$format=json")["value"] if d["tipoModalidade"] == "D"}
    )
    # os períodos são janelas móveis de 5 dias úteis: pular de 5 em 5 dá semanas sem sobreposição
    escolhidas = datas[::-1][::5][:semanas]
    con.execute("DELETE FROM juros_semanal")
    total = 0
    for inicio in escolhidas:
        url = base + "TaxasJurosDiariaPorInicioPeriodo?$filter=" + urllib.parse.quote(f"InicioPeriodo eq '{inicio}'")
        linhas = [
            (
                d.get("InicioPeriodo"), d.get("FimPeriodo"), d.get("Segmento"), d.get("Modalidade"),
                d.get("Posicao"), d.get("InstituicaoFinanceira"), d.get("TaxaJurosAoMes"),
                d.get("TaxaJurosAoAno"), d.get("cnpj8"),
            )
            for d in _paginar(url, buscar)
        ]
        con.executemany("INSERT INTO juros_semanal VALUES (?,?,?,?,?,?,?,?,?)", linhas)
        total += len(linhas)
    return total


def coletar_tudo(con, buscar: Buscar = buscar_json) -> dict[str, int]:
    return {
        "serie_sgs": coletar_series(con, buscar),
        "reclamacoes": coletar_reclamacoes(con, buscar),
        "juros_mensal": coletar_juros(con, buscar),
        "juros_semanal": coletar_juros_semanal(con, buscar),
    }
