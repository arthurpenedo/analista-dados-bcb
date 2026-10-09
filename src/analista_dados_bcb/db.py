"""Esquema do DuckDB e descrição das tabelas (usada também no prompt do modelo)."""

from __future__ import annotations

import duckdb

TABELAS = ("serie_sgs", "reclamacoes", "juros_mensal", "juros_semanal")

DDL = """
CREATE TABLE IF NOT EXISTS serie_sgs (
    codigo INTEGER, serie VARCHAR, data DATE, valor DOUBLE
);
CREATE TABLE IF NOT EXISTS reclamacoes (
    ranking VARCHAR, posicao INTEGER, ano INTEGER, periodo INTEGER, tipo_periodo VARCHAR,
    categoria VARCHAR, tipo VARCHAR, cnpj_if VARCHAR, instituicao VARCHAR, indice DOUBLE
);
CREATE TABLE IF NOT EXISTS juros_mensal (
    ano_mes VARCHAR, modalidade VARCHAR, posicao INTEGER, instituicao VARCHAR,
    taxa_mes DOUBLE, taxa_ano DOUBLE, cnpj8 VARCHAR
);
CREATE TABLE IF NOT EXISTS juros_semanal (
    inicio DATE, fim DATE, segmento VARCHAR, modalidade VARCHAR, posicao INTEGER,
    instituicao VARCHAR, taxa_mes DOUBLE, taxa_ano DOUBLE, cnpj8 VARCHAR
);
"""

# Texto entregue ao modelo (ou lido por quem usa a ferramenta) para saber o que existe.
ESQUEMA_TEXTO = """\
serie_sgs(codigo INTEGER, serie VARCHAR, data DATE, valor DOUBLE)
  -- séries do SGS: 'selic_meta' (432, % a.a., muda só nas reuniões do Copom),
     'ipca_mensal' (433, variação % no mês), 'igpm_mensal' (189, variação % no mês).
reclamacoes(ranking VARCHAR, posicao INTEGER, ano INTEGER, periodo INTEGER, tipo_periodo VARCHAR,
            categoria VARCHAR, tipo VARCHAR, cnpj_if VARCHAR, instituicao VARCHAR, indice DOUBLE)
  -- ranking de reclamações do BCB. ranking: 'maiores_bancos' | 'demais_bancos' | 'consorcio'.
     indice = índice de reclamações do BCB (reclamações procedentes por milhão de clientes; maior = pior).
     tipo_periodo: 'T' trimestre (maiores_bancos, demais_bancos) ou 'S' semestre (consorcio); periodo = número dele.
     A API só publica o período mais recente: o histórico se forma coletando de novo a cada período.
juros_mensal(ano_mes VARCHAR 'AAAA-MM', modalidade VARCHAR, posicao INTEGER, instituicao VARCHAR,
             taxa_mes DOUBLE, taxa_ano DOUBLE, cnpj8 VARCHAR)
  -- taxas médias mensais por instituição, só financiamento imobiliário (% ao mês e % ao ano).
juros_semanal(inicio DATE, fim DATE, segmento VARCHAR, modalidade VARCHAR, posicao INTEGER,
              instituicao VARCHAR, taxa_mes DOUBLE, taxa_ano DOUBLE, cnpj8 VARCHAR)
  -- taxas médias de 5 dias úteis por instituição: cartão, cheque especial, consignado, veículos,
     capital de giro etc. (as últimas semanas coletadas). segmento: 'PESSOA FÍSICA' ou 'PESSOA JURÍDICA'.
"""


def conectar(caminho: str = "bcb.duckdb", somente_leitura: bool = False) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(caminho, read_only=somente_leitura)
    if not somente_leitura:
        con.execute(DDL)
    return con
