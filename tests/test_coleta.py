from datetime import date

from analista_dados_bcb import coleta, db


def falso_buscar(url):
    """Imita as APIs do BCB sem rede."""
    if "bcdata.sgs" in url:
        return [{"data": "01/08/2026", "valor": "-0.32"}, {"data": "01/09/2026", "valor": "0.82"}, {"data": "01/10/2026", "valor": ""}]
    if "RankingReclamacoes" in url and "$skip=0" in url:
        return {"value": [
            {"Posicao": 1, "Ano": 2026, "Periodo": 2, "TipoPeriodo": "T", "Categoria": "Top 15", "Tipo": "Conglomerado",
             "CnpjIf": None, "InstituicaoFinanceira": "BANCO A", "Indice": "1.084,90"}]}
    if "ConsultaDatas" in url:
        datas = [f"2026-09-{d:02d}" for d in range(1, 21)]
        return {"value": [{"inicioPeriodo": d, "fimPeriodo": d, "tipoModalidade": "D"} for d in datas]
                + [{"inicioPeriodo": "2026-09-01", "fimPeriodo": "2026-09-30", "tipoModalidade": "M"}]}
    if "TaxasJurosDiariaPorInicioPeriodo" in url:
        inicio = url.split("%27")[1]
        return {"value": [{"InicioPeriodo": inicio, "FimPeriodo": inicio, "Segmento": "PESSOA FÍSICA", "Modalidade": "Cheque especial",
                           "Posicao": 1, "InstituicaoFinanceira": "BANCO A", "TaxaJurosAoMes": 7.0, "TaxaJurosAoAno": 125.0, "cnpj8": "1"}]}
    if "TaxasJurosMensalPorMes" in url:
        return {"value": [{"anoMes": "2026-08", "Modalidade": "Imob", "Posicao": 1, "InstituicaoFinanceira": "CAIXA",
                           "TaxaJurosAoMes": 0.86, "TaxaJurosAoAno": 10.76, "cnpj8": "3"}]}
    raise AssertionError(url)


def test_coleta_completa_com_api_falsa(tmp_path):
    con = db.conectar(str(tmp_path / "x.duckdb"))
    contagens = coleta.coletar_tudo(con, falso_buscar)
    assert contagens == {"serie_sgs": 6, "reclamacoes": 3, "juros_mensal": 1, "juros_semanal": 4}  # 3 séries x 2 valores
    assert con.execute("SELECT indice FROM reclamacoes WHERE ranking='maiores_bancos'").fetchone() == (1084.9,)
    assert con.execute("SELECT data, valor FROM serie_sgs WHERE codigo=433 ORDER BY data").fetchall()[0] == (date(2026, 8, 1), -0.32)


def test_coleta_semanal_pula_de_cinco_em_cinco(tmp_path):
    con = db.conectar(str(tmp_path / "x.duckdb"))
    coleta.coletar_juros_semanal(con, falso_buscar, semanas=4)
    inicios = [r[0].day for r in con.execute("SELECT DISTINCT inicio FROM juros_semanal ORDER BY 1 DESC").fetchall()]
    assert inicios == [20, 15, 10, 5]


def test_reclamacoes_mantem_historico_e_nao_duplica(tmp_path):
    con = db.conectar(str(tmp_path / "x.duckdb"))
    con.execute("INSERT INTO reclamacoes VALUES ('maiores_bancos',1,2026,1,'T','c','t',NULL,'BANCO A',10.0)")
    coleta.coletar_reclamacoes(con, falso_buscar)
    coleta.coletar_reclamacoes(con, falso_buscar)  # rodar de novo não duplica o T2
    assert con.execute("SELECT periodo, count(*) FROM reclamacoes WHERE ranking='maiores_bancos' GROUP BY 1 ORDER BY 1").fetchall() == [(1, 1), (2, 1)]


def test_erro_do_sgs_vira_mensagem_clara(tmp_path):
    import pytest

    con = db.conectar(str(tmp_path / "x.duckdb"))
    with pytest.raises(RuntimeError, match="SGS 432"):
        coleta.coletar_series(con, lambda url: {"error": "janela maior que 10 anos"})
