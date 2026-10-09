import pytest

from analista_dados_bcb.trava import SQLRecusado, executar_seguro, validar

BONS = [
    "SELECT * FROM reclamacoes",
    "select instituicao, indice from reclamacoes where ano = 2026 order by indice desc limit 5;",
    "WITH u AS (SELECT max(ano) a FROM reclamacoes) SELECT * FROM reclamacoes r JOIN u ON r.ano = u.a",
    "SELECT extract(year FROM data) FROM serie_sgs",
    "SELECT * FROM reclamacoes WHERE ano IS DISTINCT FROM 2025",
    "SELECT * FROM (SELECT * FROM juros_semanal) t",
    "SELECT a.instituicao FROM juros_semanal a, juros_mensal b WHERE a.cnpj8 = b.cnpj8",
    "-- comentário\nSELECT 1 AS x",
    "SELECT 'DROP TABLE x' AS texto",
]

RUINS = [
    "DROP TABLE reclamacoes",
    "DELETE FROM reclamacoes",
    "SELECT 1; DROP TABLE reclamacoes",
    "INSERT INTO reclamacoes SELECT * FROM reclamacoes",
    "SELECT * FROM usuarios",
    "SELECT * FROM read_csv('C:/Windows/win.ini')",
    "SELECT * FROM 'dados.csv'",
    "SELECT * FROM main.reclamacoes",
    "SELECT * FROM reclamacoes, segredo",
    "SELECT * FROM reclamacoes JOIN segredo ON 1=1",
    "SELECT * FROM duckdb_tables()",
    "SELECT read_text('C:/Windows/win.ini')",
    "COPY reclamacoes TO 'saida.csv'",
    "ATTACH 'outro.duckdb'",
    "PRAGMA database_list",
    "SELECT getenv('PATH')",
    "",
    "   ;  ",
]


@pytest.mark.parametrize("sql", BONS)
def test_aceita_consultas_legitimas(sql):
    assert validar(sql)


@pytest.mark.parametrize("sql", RUINS)
def test_recusa_o_que_nao_e_leitura_permitida(sql):
    with pytest.raises(SQLRecusado):
        validar(sql)


def test_execucao_segura_devolve_linhas(banco):
    colunas, linhas = executar_seguro(banco, "SELECT instituicao FROM reclamacoes WHERE ano=2026 AND periodo=2 AND ranking='maiores_bancos' ORDER BY posicao")
    assert colunas == ["instituicao"]
    assert [l[0] for l in linhas] == ["BANCO A", "BANCO B", "BANCO C"]


def test_segunda_camada_bloqueia_mesmo_se_o_texto_passasse(banco):
    """Se a validação falhar, a conexão somente leitura sem acesso externo ainda segura."""
    import duckdb

    from analista_dados_bcb.trava import conexao_segura

    con = conexao_segura(banco)
    with pytest.raises(duckdb.Error):
        con.execute("DELETE FROM reclamacoes")
    with pytest.raises(duckdb.Error):
        con.execute("SELECT * FROM read_csv('C:/Windows/win.ini')").fetchall()
    with pytest.raises(duckdb.Error):
        con.execute("SET enable_external_access = true")
    con.close()
