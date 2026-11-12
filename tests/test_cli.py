from analista_dados_bcb import benchmark, cli, coleta, llm, responder


def test_coletar_imprime_contagens(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(coleta, "coletar_tudo", lambda con: {"serie_sgs": 10, "juros_semanal": 3})
    assert cli.main(["--banco", str(tmp_path / "b.duckdb"), "coletar"]) == 0
    saida = capsys.readouterr().out
    assert "serie_sgs: 10 linhas" in saida and "juros_semanal: 3 linhas" in saida


def test_perguntar_devolve_codigo_conforme_o_resultado(monkeypatch, capsys):
    ok = responder.Resposta("p", "regras", sql="SELECT 1", colunas=["x"], linhas=[(1,)])
    monkeypatch.setattr(responder, "perguntar", lambda banco, pergunta, motor, modelo: ok)
    assert cli.main(["perguntar", "qual", "a", "selic"]) == 0
    assert "SELECT 1" in capsys.readouterr().out

    ruim = responder.Resposta("p", "regras", erro="sem regra")
    monkeypatch.setattr(responder, "perguntar", lambda banco, pergunta, motor, modelo: ruim)
    assert cli.main(["perguntar", "algo"]) == 1
    assert "Não consegui responder: sem regra" in capsys.readouterr().out


def test_benchmark_ollama_fora_do_ar_devolve_2(monkeypatch, capsys):
    monkeypatch.setattr(llm, "ollama_disponivel", lambda: False)
    assert cli.main(["benchmark", "--motor", "ollama"]) == 2
    assert "Ollama não está rodando" in capsys.readouterr().out


def test_benchmark_grava_md_e_html(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "rodar", lambda banco, motor, modelo: ["itens"])
    monkeypatch.setattr(benchmark, "resumo", lambda itens: "Acerto: 1/1")
    monkeypatch.setattr(benchmark, "pagina_html", lambda itens, motor: "<html>demo</html>")
    md, html = tmp_path / "r.md", tmp_path / "r.html"
    assert cli.main(["benchmark", "--saida", str(md), "--html", str(html)]) == 0
    assert "# Benchmark (regras)" in md.read_text(encoding="utf-8")
    assert "Acerto: 1/1" in md.read_text(encoding="utf-8")
    assert html.read_text(encoding="utf-8") == "<html>demo</html>"
