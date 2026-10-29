import duckdb
import pytest

from analista_dados_bcb import db


def test_conectar_cria_todas_as_tabelas(tmp_path):
    con = db.conectar(str(tmp_path / "x.duckdb"))
    existentes = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    assert set(db.TABELAS) <= existentes


def test_esquema_texto_descreve_cada_tabela():
    for tabela in db.TABELAS:
        assert f"{tabela}(" in db.ESQUEMA_TEXTO


def test_conectar_duas_vezes_nao_apaga_dados(tmp_path):
    caminho = str(tmp_path / "x.duckdb")
    con = db.conectar(caminho)
    con.execute("INSERT INTO serie_sgs VALUES (432, 'selic_meta', '2026-10-01', 15.0)")
    con.close()
    con = db.conectar(caminho)
    assert con.execute("SELECT count(*) FROM serie_sgs").fetchone()[0] == 1


def test_somente_leitura_bloqueia_escrita(tmp_path):
    caminho = str(tmp_path / "x.duckdb")
    db.conectar(caminho).close()
    con = db.conectar(caminho, somente_leitura=True)
    assert con.execute("SELECT count(*) FROM serie_sgs").fetchone()[0] == 0
    with pytest.raises(duckdb.Error):
        con.execute("INSERT INTO serie_sgs VALUES (432, 'selic_meta', '2026-10-01', 15.0)")
