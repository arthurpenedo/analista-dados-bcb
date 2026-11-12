import io
import json

from analista_dados_bcb import llm


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_chamar_ollama_envia_temperatura_zero_e_le_a_resposta(monkeypatch):
    visto = {}

    def falso(req, timeout):
        visto["corpo"] = json.loads(req.data)
        visto["url"] = req.full_url
        return _Resp(json.dumps({"response": "SELECT 1"}).encode())

    monkeypatch.setattr(llm.urllib.request, "urlopen", falso)
    assert llm.chamar_ollama("pergunta", "modelo-x") == "SELECT 1"
    assert visto["url"] == llm.OLLAMA
    assert visto["corpo"]["model"] == "modelo-x"
    assert visto["corpo"]["options"]["temperature"] == 0
    assert visto["corpo"]["stream"] is False


def test_ollama_disponivel_true_quando_responde(monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda url, timeout: _Resp(b"{}"))
    assert llm.ollama_disponivel() is True


def test_ollama_disponivel_false_quando_recusa_ou_resposta_quebrada(monkeypatch):
    def recusa(url, timeout):
        raise ConnectionRefusedError

    monkeypatch.setattr(llm.urllib.request, "urlopen", recusa)
    assert llm.ollama_disponivel() is False

    def quebrada(url, timeout):
        raise llm.http.client.IncompleteRead(b"")

    monkeypatch.setattr(llm.urllib.request, "urlopen", quebrada)
    assert llm.ollama_disponivel() is False
