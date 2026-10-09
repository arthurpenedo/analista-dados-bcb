from datetime import date

import pytest

from analista_dados_bcb import db


@pytest.fixture
def banco(tmp_path):
    """DuckDB pequeno e fictício, com o mesmo esquema do real."""
    caminho = str(tmp_path / "teste.duckdb")
    con = db.conectar(caminho)
    con.executemany(
        "INSERT INTO serie_sgs VALUES (?,?,?,?)",
        [
            (433, "ipca_mensal", date(2026, 6, 1), 0.30),
            (433, "ipca_mensal", date(2026, 7, 1), 0.07),
            (433, "ipca_mensal", date(2026, 8, 1), -0.32),
            (433, "ipca_mensal", date(2026, 9, 1), 0.82),
            (432, "selic_meta", date(2026, 1, 2), 14.75),
            (432, "selic_meta", date(2026, 6, 1), 14.25),
            (432, "selic_meta", date(2026, 10, 9), 13.75),
            (189, "igpm_mensal", date(2026, 9, 1), 0.50),
        ],
    )
    cat = "Top 15 - Bancos, Financeiras e Instituições de Pagamento"
    con.executemany(
        "INSERT INTO reclamacoes VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("maiores_bancos", 1, 2026, 2, "T", cat, "Conglomerado", None, "BANCO A", 80.0),
            ("maiores_bancos", 2, 2026, 2, "T", cat, "Conglomerado", None, "BANCO B", 60.0),
            ("maiores_bancos", 3, 2026, 2, "T", cat, "Conglomerado", None, "BANCO C", 40.0),
            ("maiores_bancos", 1, 2026, 1, "T", cat, "Conglomerado", None, "BANCO C", 90.0),
            ("maiores_bancos", 2, 2026, 1, "T", cat, "Conglomerado", None, "BANCO A", 70.0),
            ("demais_bancos", 1, 2026, 2, "T", "Demais", "Conglomerado", None, "BANCO D", 120.0),
            ("consorcio", 1, 2026, 1, "S", "Consórcios", "Banco/financeira", None, "CONSORCIO E", 30.0),
        ],
    )
    con.executemany(
        "INSERT INTO juros_semanal VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (date(2026, 9, 21), date(2026, 9, 25), "PESSOA FÍSICA", "Cartão de crédito - rotativo total - Prefixado", 1, "BANCO A", 10.0, 220.0, "1"),
            (date(2026, 9, 21), date(2026, 9, 25), "PESSOA FÍSICA", "Cartão de crédito - rotativo total - Prefixado", 2, "BANCO B", 14.0, 380.0, "2"),
            (date(2026, 9, 21), date(2026, 9, 25), "PESSOA FÍSICA", "Cheque especial - Prefixado", 1, "BANCO B", 7.0, 125.0, "2"),
            (date(2026, 9, 14), date(2026, 9, 18), "PESSOA FÍSICA", "Cartão de crédito - rotativo total - Prefixado", 1, "BANCO A", 9.0, 180.0, "1"),
        ],
    )
    con.executemany(
        "INSERT INTO juros_mensal VALUES (?,?,?,?,?,?,?)",
        [
            ("2026-08", "Financiamento imobiliário com taxas de mercado - Prefixado", 1, "CAIXA", 0.86, 10.76, "00360305"),
            ("2026-08", "Financiamento imobiliário com taxas de mercado - Prefixado", 2, "BANCO B", 1.18, 15.12, "2"),
        ],
    )
    con.close()
    return caminho
