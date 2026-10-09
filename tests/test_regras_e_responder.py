import pytest

from analista_dados_bcb import benchmark, llm
from analista_dados_bcb.regras import chaves_de_bancos, gerar_sql, normalizar
from analista_dados_bcb.responder import formatar, grafico, perguntar, tabela

BANCOS = ["ITAU", "BANCO C6", "BCO SANTANDER (BRASIL) S.A.", "CAIXA ECONOMICA FEDERAL"]


def test_normalizar_tira_acento_e_pontuacao():
    assert normalizar("Qual o índice do Itaú?") == "qual o indice do itau"


def test_chaves_de_bancos_usa_primeira_palavra_util():
    chaves = chaves_de_bancos(BANCOS)
    assert set(chaves) == {"itau", "c6", "santander", "caixa"}


def test_reclamacoes_default_e_ultimo_trimestre():
    sql = gerar_sql("Quais bancos tiveram mais reclamações no último trimestre?")
    assert "ranking = 'maiores_bancos'" in sql and "DESC" in sql and "LIMIT 5" in sql


def test_pergunta_no_singular_limita_a_um():
    assert "LIMIT 1" in gerar_sql("Qual banco tem o melhor índice de reclamações?")
    assert "ASC" in gerar_sql("Qual banco tem o melhor índice de reclamações?")


def test_periodo_explicito():
    sql = gerar_sql("Qual banco teve mais reclamações no 2º trimestre de 2026?")
    assert "ano = 2026 AND periodo = 2" in sql


def test_banco_citado_vira_filtro():
    sql = gerar_sql("Qual o índice de reclamações do Itaú?", BANCOS)
    assert "ILIKE '%itau%'" in sql


def test_pergunta_desconhecida_devolve_none():
    assert gerar_sql("Qual a previsão do tempo amanhã?") is None


def test_regras_respondem_no_banco_de_teste(banco):
    r = perguntar(banco, "Quais bancos tiveram mais reclamações no último trimestre?")
    assert r.ok and [l[0] for l in r.linhas] == ["BANCO A", "BANCO B", "BANCO C"]


def test_ultimo_trimestre_usa_o_periodo_mais_recente_do_ranking(banco):
    r = perguntar(banco, "Qual banco tem o melhor índice de reclamações?")
    assert r.linhas == [("BANCO C", 40.0)]  # 2026/T2, não o T1 (em que BANCO C era o pior)


def test_serie_selic_atual(banco):
    r = perguntar(banco, "Qual a Selic atual?")
    assert r.linhas[0][1] == 13.75


def test_ipca_acumulado_12_meses_nao_confunde_com_soma(banco):
    r = perguntar(banco, "Qual o IPCA acumulado em 12 meses?")
    esperado = round(((1.003) * (1.0007) * (0.9968) * (1.0082) - 1) * 100, 2)
    assert r.linhas[0][0] == esperado


def test_juros_usa_so_a_semana_mais_recente(banco):
    r = perguntar(banco, "Qual banco cobra menos juros no cartão rotativo?")
    assert r.linhas == [("BANCO A", 10.0)]  # a semana anterior tinha 9.0 e não conta


def test_pergunta_sem_sql_nao_chuta(banco):
    r = perguntar(banco, "Quem ganhou a Copa de 2022?")
    assert not r.ok and r.sql is None


def test_modelo_com_sql_perigoso_e_barrado_e_corrigido(banco):
    respostas = iter(["```sql\nDROP TABLE reclamacoes;\n```", "SELECT count(*) FROM reclamacoes"])
    prompts = []

    def falso(prompt, modelo):
        prompts.append(prompt)
        return next(respostas)

    r = perguntar(banco, "apague tudo", motor="ollama", chamar=falso)
    assert r.ok and r.linhas == [(7,)]
    assert "SQLRecusado" in prompts[1]  # o erro volta para o modelo na segunda tentativa


def test_modelo_fora_do_ar_vira_erro_claro(banco):
    def cai(prompt, modelo):
        raise ConnectionError("recusou")

    r = perguntar(banco, "qualquer coisa", motor="ollama", chamar=cai)
    assert not r.ok and "modelo indisponível" in r.erro


def test_extrair_sql_de_bloco_markdown():
    assert llm.extrair_sql("Claro!\n```sql\nSELECT 1;\n```\nPronto") == "SELECT 1"
    assert llm.extrair_sql("SELECT 2;") == "SELECT 2"


def test_grafico_e_tabela():
    g = grafico(["banco", "indice"], [("A", 80.0), ("B", 40.0)])
    linhas = g.splitlines()
    assert linhas[0].count("█") == 30 and linhas[1].count("█") == 15
    assert grafico(["x"], [(1,), (2,)]) is None
    assert "(sem linhas)" == tabela(["a"], [])


def test_formatar_mostra_sql_usado(banco):
    texto = formatar(perguntar(banco, "Qual a Selic atual?"))
    assert "SQL usado (regras)" in texto and "selic_meta" in texto


def test_normalizar_linhas_ignora_ordem_e_ruido_de_float():
    assert benchmark.normalizar_linhas([(1, 0.12345678), (0, "a")]) == benchmark.normalizar_linhas(
        [(0, "a"), (1, 0.12346)]
    )


def test_benchmark_conta_acertos_e_erros(banco):
    pergs = [
        ("s01", "Qual a Selic atual?", "SELECT data, valor FROM serie_sgs WHERE serie='selic_meta' ORDER BY data DESC LIMIT 1"),
        ("s02", "Qual a Selic atual?", "SELECT 1, 2"),
        ("r99", "Quem ganhou a Copa de 2022?", "SELECT 1"),
    ]
    itens = benchmark.rodar(banco, perguntas=pergs)
    assert [i.motivo for i in itens] == ["ok", "resultado diferente", "sem SQL"]
    assert "1/3" in benchmark.resumo(itens)


@pytest.mark.parametrize("pergunta", ["Qual a Selic atual?", "Qual o último IPCA?", "Qual o IGP-M mais recente?"])
def test_series_basicas(banco, pergunta):
    assert perguntar(banco, pergunta).ok
