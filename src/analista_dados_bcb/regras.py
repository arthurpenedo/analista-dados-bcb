"""Baseline sem modelo: modelos de SQL escolhidos por regras sobre o texto da pergunta.

Serve de piso para comparar com o modelo aberto e funciona sem Ollama. Devolve None quando não
reconhece a pergunta (em vez de chutar um SQL).
"""

from __future__ import annotations

import re
import unicodedata

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
SERIES = {"selic": "selic_meta", "ipca": "ipca_mensal", "igpm": "igpm_mensal"}
# (regex na pergunta, padrão LIKE da modalidade)
MODALIDADES = [
    (r"cartao.*rotativo|rotativo", "Cartão de crédito - rotativo total%"),
    (r"cartao.*parcelado|parcelado", "Cartão de crédito - parcelado%"),
    (r"cheque especial", "Cheque especial%"),
    (r"consignado.*inss|inss", "Crédito pessoal consignado INSS%"),
    (r"consignado.*privado", "Crédito pessoal consignado privado%"),
    (r"consignado.*publico", "Crédito pessoal consignado público%"),
    (r"credito pessoal|emprestimo pessoal", "Crédito pessoal não consignado%"),
    (r"veiculo|carro", "Aquisição de veículos%"),
]
IMOBILIARIO = r"imobiliario|casa propria"
PARADAS = {"de", "do", "da", "dos", "das", "s", "a", "sa", "ip", "financeira", "credito", "financiamento"}


def normalizar(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9/\- ]", " ", sem_acento.lower())).strip()


def chaves_de_bancos(nomes) -> dict[str, str]:
    """'BANCO C6' -> 'c6', 'ITAÚ UNIBANCO' -> 'itau': primeira palavra útil do nome."""
    chaves: dict[str, str] = {}
    for nome in nomes:
        palavras = [p for p in re.split(r"[^a-z0-9]+", normalizar(nome)) if p]
        palavras = [p for p in palavras if p not in ("banco", "bco") and p not in PARADAS]
        if palavras and len(palavras[0]) >= 2:
            chaves.setdefault(palavras[0], nome)
    return chaves


def _limite(q: str, padrao: int) -> int:
    if re.search(r"\bqual (banco|instituicao|financeira|o banco)\b|\bo banco que\b"
                 r"|\bqual (?:a|o|era a|foi a) (?:menor|maior|melhor|pior)\b", q):
        return 1
    m = re.search(r"\btop\s*(\d+)|\b(?:os|as)\s+(\d+)\b|\b(\d+)\s+(?:bancos|instituicoes|maiores|menores)", q)
    if m:
        return int(next(g for g in m.groups() if g))
    return padrao


def _banco(q: str, chaves: dict[str, str]) -> str | None:
    achados = [(m.start(), chave) for chave in chaves if (m := re.search(rf"\b{re.escape(chave)}\b", q))]
    return min(achados)[1] if achados else None  # o banco citado primeiro: resultado não depende da ordem do DuckDB


def _periodo_reclamacoes(q: str, ranking: str) -> str:
    m = re.search(r"\b(\d)\s?o?\s+(?:trimestre|semestre)|(?:trimestre|semestre)\s+(\d)\b", q)
    a = re.search(r"\b(20\d\d)\b", q)
    base = f"ranking = '{ranking}'"
    if m and a:
        return f"{base} AND ano = {a.group(1)} AND periodo = {next(g for g in m.groups() if g)}"
    if a:
        return (f"{base} AND ano = {a.group(1)} AND periodo = "
                f"(SELECT max(periodo) FROM reclamacoes WHERE {base} AND ano = {a.group(1)})")
    return (f"{base} AND (ano, periodo) IN "
            f"(SELECT ano, periodo FROM reclamacoes WHERE {base} ORDER BY ano DESC, periodo DESC LIMIT 1)")


def _reclamacoes(q: str, chaves: dict[str, str]) -> str:
    ranking = "consorcio" if "consorcio" in q else "demais_bancos" if "demais" in q else "maiores_bancos"
    filtro = _periodo_reclamacoes(q, ranking)
    banco = _banco(q, chaves)
    if banco:
        return (f"SELECT instituicao, indice FROM reclamacoes WHERE {filtro} "
                f"AND strip_accents(instituicao) ILIKE '%{banco}%' ORDER BY instituicao")
    ordem = "ASC" if re.search(r"\b(menos|menor|menores|melhor|melhores)\b", q) else "DESC"
    return (f"SELECT instituicao, indice FROM reclamacoes WHERE {filtro} "
            f"ORDER BY indice {ordem}, instituicao LIMIT {_limite(q, 5)}")


def _juros(q: str, chaves: dict[str, str]) -> str | None:
    if re.search(IMOBILIARIO, q):
        tabela = "juros_mensal"
        data = "ano_mes = (SELECT max(ano_mes) FROM juros_mensal)"
        mod = "modalidade = 'Financiamento imobiliário com taxas de mercado - Prefixado'"
    else:
        padrao = next((p for rx, p in MODALIDADES if re.search(rx, q)), None)
        if padrao is None:
            return None
        tabela = "juros_semanal"
        data = "inicio = (SELECT max(inicio) FROM juros_semanal)"
        mod = f"modalidade LIKE '{padrao}'"
    filtro = f"{data} AND {mod}"
    if re.search(r"\bmedia\b", q):
        return f"SELECT round(avg(taxa_mes), 2) AS media_taxa_mes FROM {tabela} WHERE {filtro}"
    banco = _banco(q, chaves)
    if banco:
        return (f"SELECT instituicao, taxa_mes FROM {tabela} WHERE {filtro} "
                f"AND strip_accents(instituicao) ILIKE '%{banco}%' ORDER BY instituicao")
    ordem = "DESC" if re.search(r"\b(maior|maiores|mais cara|mais caro|mais alt[oa]s?|cobra mais|cobram mais)\b", q) else "ASC"
    return (f"SELECT instituicao, taxa_mes FROM {tabela} WHERE {filtro} "
            f"ORDER BY taxa_mes {ordem}, instituicao LIMIT {_limite(q, 5)}")


def _data_alvo(q: str) -> tuple[int, int | None] | None:
    """(ano, mês|None) citado na pergunta."""
    for nome, n in MESES.items():
        m = re.search(rf"\b{nome}\b(?: de| /)? (20\d\d)", q)
        if m:
            return int(m.group(1)), n
    m = re.search(r"\b(\d{1,2})/(20\d\d)\b", q) or re.search(r"\b(20\d\d)-(\d{2})\b", q)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return (b, a) if a <= 12 else (a, b)
    m = re.search(r"\b(20\d\d)\b", q)
    return (int(m.group(1)), None) if m else None


def _serie(q: str, serie: str) -> str:
    base = f"serie = '{serie}'"
    alvo = _data_alvo(q)
    if re.search(r"acumulad[oa].*12|12 meses|doze meses", q):
        return ("SELECT round((exp(sum(ln(1 + valor / 100))) - 1) * 100, 2) AS acumulado_12m FROM "
                f"(SELECT valor FROM serie_sgs WHERE {base} ORDER BY data DESC LIMIT 12)")
    if alvo and alvo[1] is None and re.search(r"acumulad", q) and serie != "selic_meta":
        return ("SELECT round((exp(sum(ln(1 + valor / 100))) - 1) * 100, 2) AS acumulado_ano FROM serie_sgs "
                f"WHERE {base} AND year(data) = {alvo[0]}")
    if re.search(r"\b(maior|maxima|mais alt[oa]|pico)\b", q):
        return f"SELECT data, valor FROM serie_sgs WHERE {base} ORDER BY valor DESC, data DESC LIMIT 1"
    if re.search(r"\b(menor|minima|mais baix[oa])\b", q):
        return f"SELECT data, valor FROM serie_sgs WHERE {base} ORDER BY valor ASC, data DESC LIMIT 1"
    if re.search(r"\bmedia\b", q) and alvo and alvo[1] is None:
        return f"SELECT round(avg(valor), 2) AS media FROM serie_sgs WHERE {base} AND year(data) = {alvo[0]}"
    if alvo and alvo[1] is not None and serie != "selic_meta":
        return f"SELECT data, valor FROM serie_sgs WHERE {base} AND year(data) = {alvo[0]} AND month(data) = {alvo[1]}"
    if alvo:  # valor vigente ao fim do ano/mês citado
        corte = f"year(data) = {alvo[0]}" + (f" AND month(data) = {alvo[1]}" if alvo[1] else "")
        return f"SELECT data, valor FROM serie_sgs WHERE {base} AND {corte} ORDER BY data DESC LIMIT 1"
    return f"SELECT data, valor FROM serie_sgs WHERE {base} ORDER BY data DESC LIMIT 1"


def gerar_sql(pergunta: str, instituicoes=()) -> str | None:
    q = normalizar(pergunta).replace("igp-m", "igpm")
    chaves = chaves_de_bancos(instituicoes)
    for palavra, serie in SERIES.items():
        if re.search(rf"\b{palavra}\b", q):
            return _serie(q, serie)
    if re.search(r"reclama|ouvidoria", q):
        return _reclamacoes(q, chaves)
    return _juros(q, chaves)  # None se não citar nenhuma modalidade de crédito conhecida
