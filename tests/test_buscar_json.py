import io

import pytest

from analista_dados_bcb import coleta


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_tenta_de_novo_e_devolve_o_json(monkeypatch):
    chamadas = []

    def urlopen(url, timeout):
        chamadas.append(url)
        if len(chamadas) < 3:
            raise TimeoutError("lento")
        return _Resp(b'[{"valor": 1}]')

    monkeypatch.setattr(coleta.urllib.request, "urlopen", urlopen)
    assert coleta.buscar_json("http://x/y") == [{"valor": 1}]
    assert len(chamadas) == 3


def test_json_quebrado_conta_como_tentativa_e_esgota(monkeypatch):
    monkeypatch.setattr(coleta.urllib.request, "urlopen", lambda url, timeout: _Resp(b"<html>erro</html>"))
    with pytest.raises(RuntimeError, match="falha ao buscar http://x/y"):
        coleta.buscar_json("http://x/y", tentativas=2)


def test_erro_de_programacao_nao_e_engolido(monkeypatch):
    def bug(url, timeout):
        raise KeyError("bug")

    monkeypatch.setattr(coleta.urllib.request, "urlopen", bug)
    with pytest.raises(KeyError):
        coleta.buscar_json("http://x/y")
