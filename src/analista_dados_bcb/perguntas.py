"""Benchmark: perguntas em português com o SQL de referência escrito à mão.

O SQL de referência não depende de datas fixas (usa max()/subconsultas), então vale para qualquer coleta.
Algumas perguntas ficam de propósito fora do que o baseline por regras cobre.
"""

ROT = "'Cartão de crédito - rotativo total - Prefixado'"
PARC = "'Cartão de crédito - parcelado - Prefixado'"
CHEQUE = "'Cheque especial - Prefixado'"
PESSOAL = "'Crédito pessoal não consignado - Prefixado'"
INSS = "'Crédito pessoal consignado INSS - Prefixado'"
PRIVADO = "'Crédito pessoal consignado privado - Prefixado'"
PUBLICO = "'Crédito pessoal consignado público - Prefixado'"
VEICULOS = "'Aquisição de veículos - Prefixado'"
IMOB = "'Financiamento imobiliário com taxas de mercado - Prefixado'"


def _rec(ranking: str, ordem: str = "DESC", n: int | None = 5, extra: str = "") -> str:
    limite = f" LIMIT {n}" if n else ""
    return (
        "SELECT instituicao, indice FROM reclamacoes WHERE ranking = '" + ranking + "' "
        "AND ano * 10 + periodo = (SELECT max(ano * 10 + periodo) FROM reclamacoes WHERE ranking = '" + ranking + "')"
        + extra + f" ORDER BY indice {ordem}, instituicao" + limite
    )


def _jur(mod: str, ordem: str = "ASC", n: int | None = 5, extra: str = "", tabela: str = "juros_semanal") -> str:
    campo = "ano_mes" if tabela == "juros_mensal" else "inicio"
    limite = f" LIMIT {n}" if n else ""
    return (
        f"SELECT instituicao, taxa_mes FROM {tabela} WHERE modalidade = {mod} "
        f"AND {campo} = (SELECT max({campo}) FROM {tabela}){extra} ORDER BY taxa_mes {ordem}, instituicao" + limite
    )


def _media(mod: str) -> str:
    return (f"SELECT round(avg(taxa_mes), 2) FROM juros_semanal WHERE modalidade = {mod} "
            "AND inicio = (SELECT max(inicio) FROM juros_semanal)")


def _ultimo(serie: str) -> str:
    return f"SELECT data, valor FROM serie_sgs WHERE serie = '{serie}' ORDER BY data DESC LIMIT 1"


def _mes(serie: str, ano: int, mes: int) -> str:
    return (f"SELECT data, valor FROM serie_sgs WHERE serie = '{serie}' "
            f"AND data >= DATE '{ano}-{mes:02d}-01' AND data < DATE '{ano}-{mes:02d}-01' + INTERVAL 1 MONTH")


def _acum12(serie: str) -> str:
    return ("SELECT round((product(1 + valor / 100) - 1) * 100, 2) FROM "
            f"(SELECT valor FROM serie_sgs WHERE serie = '{serie}' ORDER BY data DESC LIMIT 12)")


# (id, pergunta, sql de referência)
PERGUNTAS: list[tuple[str, str, str]] = [
    # --- reclamações
    ("r01", "Quais bancos tiveram mais reclamações no último trimestre?", _rec("maiores_bancos")),
    ("r02", "Quais os 3 bancos com menos reclamações no trimestre mais recente?", _rec("maiores_bancos", "ASC", 3)),
    ("r03", "Qual banco tem o pior índice de reclamações?", _rec("maiores_bancos", "DESC", 1)),
    ("r04", "Qual banco tem o melhor índice de reclamações?", _rec("maiores_bancos", "ASC", 1)),
    ("r05", "Top 10 bancos com mais reclamações", _rec("maiores_bancos", "DESC", 10)),
    ("r06", "Qual o índice de reclamações do Itaú?", _rec("maiores_bancos", "DESC", None, " AND instituicao = 'ITAU'")),
    ("r07", "Quantas reclamações por milhão de clientes o Santander tem?",
     _rec("maiores_bancos", "DESC", None, " AND instituicao = 'SANTANDER'")),
    ("r08", "Quais consórcios têm mais reclamações?", _rec("consorcio")),
    ("r09", "Qual administradora de consórcio tem menos reclamações?", _rec("consorcio", "ASC", 1)),
    ("r10", "Quais os 5 demais bancos com mais reclamações?", _rec("demais_bancos")),
    ("r11", "Ranking de reclamações do Bradesco", _rec("maiores_bancos", "DESC", None, " AND instituicao = 'BRADESCO'")),
    ("r12", "Qual banco teve mais reclamações no 2º trimestre de 2026?",
     "SELECT instituicao, indice FROM reclamacoes WHERE ranking = 'maiores_bancos' AND ano = 2026 AND periodo = 2 "
     "ORDER BY indice DESC, instituicao LIMIT 1"),
    ("r13", "Quais bancos têm índice de reclamações acima de 50?", _rec("maiores_bancos", "DESC", None, " AND indice > 50")),
    ("r14", "Quantos bancos aparecem no ranking dos maiores bancos?",
     "SELECT count(*) FROM reclamacoes WHERE ranking = 'maiores_bancos' AND ano * 10 + periodo = "
     "(SELECT max(ano * 10 + periodo) FROM reclamacoes WHERE ranking = 'maiores_bancos')"),
    # --- juros
    ("j01", "Qual banco cobra menos juros no cartão rotativo?", _jur(ROT, "ASC", 1)),
    ("j02", "Qual a menor taxa de juros do cheque especial?", _jur(CHEQUE, "ASC", 1)),
    ("j03", "Quais os 5 bancos com juros mais altos no cartão rotativo?", _jur(ROT, "DESC", 5)),
    ("j04", "Qual a taxa média do cartão de crédito rotativo?", _media(ROT)),
    ("j05", "Quanto o Santander cobra de juros no cheque especial?",
     _jur(CHEQUE, "ASC", None, " AND instituicao LIKE '%SANTANDER%'")),
    ("j06", "Quais bancos têm os maiores juros no crédito pessoal?", _jur(PESSOAL, "DESC", 5)),
    ("j07", "Qual a taxa média do consignado INSS?", _media(INSS)),
    ("j08", "Qual banco tem o menor juro no financiamento de veículos?", _jur(VEICULOS, "ASC", 1)),
    ("j09", "Qual banco tem a menor taxa de financiamento imobiliário?", _jur(IMOB, "ASC", 1, tabela="juros_mensal")),
    ("j10", "Qual a taxa de juros do financiamento imobiliário na Caixa?",
     _jur(IMOB, "ASC", None, " AND instituicao LIKE 'CAIXA%'", "juros_mensal")),
    ("j11", "Qual a taxa média do consignado privado?", _media(PRIVADO)),
    ("j12", "Como a taxa média do rotativo mudou nas últimas semanas?",
     f"SELECT inicio, round(avg(taxa_mes), 2) FROM juros_semanal WHERE modalidade = {ROT} GROUP BY inicio ORDER BY inicio"),
    ("j13", "Quais bancos cobram menos de 5% ao mês no cheque especial?", _jur(CHEQUE, "ASC", None, " AND taxa_mes < 5")),
    ("j14", "Qual banco tem o consignado público mais barato?", _jur(PUBLICO, "ASC", 1)),
    ("j15", "Qual a taxa do Itaú no cartão de crédito parcelado?",
     _jur(PARC, "ASC", None, " AND strip_accents(instituicao) ILIKE '%itau%'")),
    ("j16", "Qual banco cobra mais no crédito pessoal?", _jur(PESSOAL, "DESC", 1)),
    # --- séries do SGS
    ("s01", "Qual a Selic atual?", _ultimo("selic_meta")),
    ("s02", "Qual era a meta da Selic em dezembro de 2024?",
     "SELECT data, valor FROM serie_sgs WHERE serie = 'selic_meta' AND data = DATE '2024-12-31'"),
    ("s03", "Qual foi a maior Selic da série?",
     "SELECT data, valor FROM serie_sgs WHERE serie = 'selic_meta' ORDER BY valor DESC, data DESC LIMIT 1"),
    ("s04", "Qual o último IPCA?", _ultimo("ipca_mensal")),
    ("s05", "Qual foi o IPCA de agosto de 2026?", _mes("ipca_mensal", 2026, 8)),
    ("s06", "Qual o IPCA acumulado em 12 meses?", _acum12("ipca_mensal")),
    ("s07", "Qual o IPCA acumulado em 2025?",
     "SELECT round((product(1 + valor / 100) - 1) * 100, 2) FROM serie_sgs "
     "WHERE serie = 'ipca_mensal' AND data BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'"),
    ("s08", "Qual a média da Selic em 2025?",
     "SELECT round(avg(valor), 2) FROM serie_sgs WHERE serie = 'selic_meta' "
     "AND data BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'"),
    ("s09", "Qual foi o maior IPCA mensal desde 2018?",
     "SELECT data, valor FROM serie_sgs WHERE serie = 'ipca_mensal' ORDER BY valor DESC, data DESC LIMIT 1"),
    ("s10", "Qual o IGP-M mais recente?", _ultimo("igpm_mensal")),
    ("s11", "Quantos meses o IPCA ficou negativo desde 2018?",
     "SELECT count(*) FROM serie_sgs WHERE serie = 'ipca_mensal' AND valor < 0"),
    ("s12", "Qual a Selic em junho de 2026?",
     "SELECT data, valor FROM serie_sgs WHERE serie = 'selic_meta' AND data = DATE '2026-06-30'"),
    ("s13", "Em que mês o IPCA foi o menor desde 2018?",
     "SELECT data, valor FROM serie_sgs WHERE serie = 'ipca_mensal' ORDER BY valor ASC, data DESC LIMIT 1"),
    ("s14", "Qual o IGP-M acumulado em 12 meses?", _acum12("igpm_mensal")),
    # --- cruzando tabelas
    ("c01", "Qual a taxa do cartão rotativo no banco com mais reclamações?",
     f"SELECT instituicao, taxa_mes FROM juros_semanal WHERE modalidade = {ROT} "
     "AND inicio = (SELECT max(inicio) FROM juros_semanal) AND strip_accents(instituicao) ILIKE '%' || "
     "(SELECT split_part(instituicao, ' ', 1) FROM reclamacoes WHERE ranking = 'maiores_bancos' "
     "ORDER BY ano DESC, periodo DESC, indice DESC LIMIT 1) || '%'"),
    ("c02", "A Selic atual está acima da média da Selic em 2025?",
     "SELECT (SELECT valor FROM serie_sgs WHERE serie = 'selic_meta' ORDER BY data DESC LIMIT 1) > "
     "(SELECT avg(valor) FROM serie_sgs WHERE serie = 'selic_meta' AND year(data) = 2025)"),
]
