# analista-dados-bcb

[![CI](https://github.com/arthurpenedo/analista-dados-bcb/actions/workflows/ci.yml/badge.svg)](https://github.com/arthurpenedo/analista-dados-bcb/actions/workflows/ci.yml)

Pergunte em português sobre **juros, inflação e reclamações dos bancos** e receba tabela, gráfico e o **SQL usado**.
A pergunta vira SQL num DuckDB alimentado pelas APIs abertas do Banco Central (SGS e Olinda), e **uma trava
garante que só roda leitura, só nas tabelas permitidas**.

```
$ analista-dados-bcb perguntar Quais bancos tiveram mais reclamações no último trimestre?
instituicao           | indice
----------------------+-------
BRADESCO              | 84.90
BANCO C6              | 59.77
ITAU                  | 46.87
BTG PACTUAL/BANCO PAN | 41.98
MERCADO PAGO IP       | 40.81

BRADESCO              ██████████████████████████████ 84.90
...
SQL usado (regras): SELECT instituicao, indice FROM reclamacoes WHERE ranking = 'maiores_bancos' ...
```

## Por que existe
Os dados do BCB são públicos, mas quem não sabe SQL e as APIs OData não chega neles. Análise de dados com IA
exige duas coisas além de "gerar SQL": **confiar no SQL gerado** (por isso a trava) e **medir se acerta** (por isso o benchmark).

## O que tem
- **Coleta** (`coletar`): SGS (Selic meta, IPCA, IGP-M), ranking de reclamações (Olinda), juros por instituição
  (mensal de financiamento imobiliário e semanal de cartão, cheque especial, consignado, veículos, crédito pessoal etc.).
  Sem chave de API.
- **Trava de SQL** (`trava.py`), duas camadas:
  1. validação do texto: um comando só, começa com `SELECT`/`WITH`, sem `DROP/INSERT/COPY/ATTACH/PRAGMA...`,
     toda tabela do `FROM`/`JOIN` na lista permitida (CTEs incluídas), sem função de tabela nem de leitura de arquivo;
  2. execução numa conexão DuckDB **somente leitura**, com `enable_external_access=false` e configuração travada.
- **Dois motores**: `regras` (modelos de SQL escolhidos por regras, sem IA, é o baseline) e `ollama`
  (modelo aberto local, padrão `qwen2.5-coder:3b`; se o SQL falhar na trava ou na execução, o erro volta ao
  modelo para uma correção). `auto` tenta regras e cai no Ollama.
- **Benchmark** (`perguntas.py`, `benchmark.py`): 46 perguntas com SQL de referência escrito à mão; mede **acerto por
  execução** (o resultado do SQL gerado é igual ao da referência, ignorando nomes de coluna e ordem das linhas).

## Como rodar
```bash
pip install -e ".[dev]"
analista-dados-bcb coletar                       # cria bcb.duckdb (~20 s)
analista-dados-bcb perguntar Qual a Selic atual?
analista-dados-bcb perguntar --motor ollama Qual banco cobra menos no cheque especial?   # precisa do Ollama
analista-dados-bcb benchmark --saida resultados-regras.md
pytest
```
Tudo gratuito: APIs abertas do BCB, DuckDB e modelo aberto local. Nada de API paga.

## Números medidos (09/10/2026, no meu PC)
| Medida | Valor |
|---|---|
| Linhas coletadas | 3.414 (SGS) · 109 (reclamações) · 865 (juros mensal) · 3.129 (juros semanal) |
| Tempo da coleta | 17 a 20 s |
| Testes | 56 passando (`pytest`), 29 deles da trava (9 SQLs legítimos aceitos, 18 maliciosos ou inválidos recusados, mais a 2ª camada) |
| Benchmark, motor `regras` | **38 de 46 (82,6%)**: reclamações 11/14, juros 14/16, séries 13/14, cruzando tabelas 0/2 |

Fonte dos números: execução local do `analista-dados-bcb coletar`, `pytest` e `benchmark` em 09/10/2026.

## Limites honestos
- **O benchmark foi escrito por mim, junto com as regras.** Os 82,6% do baseline são otimistas: as regras foram
  ajustadas olhando perguntas parecidas. Ele serve de piso e de régua, não de prova de generalização.
- **O motor `ollama` está implementado e testado com modelo simulado, mas eu ainda não medi o acerto dele**
  (não havia Ollama instalado na máquina em que construí). Rode `benchmark --motor ollama` e compare.
- O baseline **responde errado com confiança** quando reconhece só parte da pergunta (ex.: "bancos acima de 50"
  vira o top 5; as falhas r13, j13 e s11 são assim). Por isso a resposta sempre mostra o SQL usado.
- A API de reclamações só entrega o **período mais recente**; o histórico se forma coletando de novo a cada
  trimestre (o coletor não apaga períodos antigos). Hoje o banco tem só 2026/T2 (bancos) e 2026/S1 (consórcios).
- Juros mensais da API são só de financiamento imobiliário; as demais modalidades vêm em janelas semanais
  (guardo as 4 últimas semanas).
- O índice de reclamações é o do BCB (reclamações procedentes por milhão de clientes) e **não cobre todos os
  bancos do mesmo jeito**: "demais bancos" tem outliers enormes (um valor passa de 1 milhão).
- A trava de texto é conservadora e pode recusar SQL legítimo e raro; a 2ª camada (somente leitura, sem acesso
  externo) vale mesmo se a 1ª falhar.

## Estrutura
```
src/analista_dados_bcb/  coleta.py  db.py  trava.py  regras.py  llm.py  responder.py  benchmark.py  perguntas.py  cli.py
tests/                   trava, coleta (API simulada), regras, respostas, benchmark
```

Licença MIT.
