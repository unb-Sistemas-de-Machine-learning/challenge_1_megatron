import json

from fastapi.testclient import TestClient

from tests.apoio_rag import ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA, LLMFalso, criar_servico
from verdade_ou_fake import api


def cliente(servico, monkeypatch):
    monkeypatch.setattr(api, "_aquecer", lambda servico: None)
    api.app.state.servico = servico
    return TestClient(api.app)


def eventos_de(resposta):
    return [json.loads(l[6:]) for l in resposta.text.split("\n") if l.startswith("data: ")]


def test_analisar_transmite_eventos_ate_o_fim(monkeypatch):
    servico = criar_servico(LLMFalso(ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA))
    with cliente(servico, monkeypatch) as http:
        resposta = http.post("/api/analisar", json={"entrada": "Ivermectina cura covid-19"})
        assert resposta.status_code == 200
        assert resposta.headers["content-type"].startswith("text/event-stream")
        eventos = eventos_de(resposta)
        assert eventos[-1]["tipo"] == "fim"
        assert any(e["tipo"] == "veredito" and e["codigo"] == "CONTESTADA" for e in eventos)

        consulta_id = eventos[-1]["consulta_id"]
        assert http.post("/api/feedback", json={"consulta_id": consulta_id, "valor": 1}).json() == {"ok": True}
        assert http.post("/api/feedback", json={"consulta_id": 9999, "valor": 1}).status_code == 404
        assert http.post("/api/feedback", json={"consulta_id": consulta_id, "valor": 5}).status_code == 422

        metricas = http.get("/api/metricas").json()
        assert metricas["consultas"] == 1
        assert metricas["feedback_positivo"] == 1
        assert metricas["vereditos"] == {"CONTESTADA": 1}


def test_entrada_curta_demais_e_recusada(monkeypatch):
    with cliente(criar_servico(None), monkeypatch) as http:
        assert http.post("/api/analisar", json={"entrada": "oi"}).status_code == 422


def test_saude_informa_base_e_llm(monkeypatch):
    with cliente(criar_servico(None), monkeypatch) as http:
        corpo = http.get("/api/saude").json()
        assert corpo["status"] == "ok"
        assert corpo["documentos"] == 3
        assert corpo["llm"] is False
        assert corpo["modelos"] == []


def test_limite_de_requisicoes_por_cliente(monkeypatch):
    with cliente(criar_servico(None), monkeypatch) as http:
        api.app.state.limite = api.LimiteDeRequisicoes(2)
        codigos = [
            http.post("/api/analisar", json={"entrada": "Ivermectina cura covid-19"}).status_code
            for _ in range(3)
        ]
        assert codigos == [200, 200, 429]


def test_erro_inesperado_vira_evento_de_erro(monkeypatch):
    async def explode(servico, entrada):
        raise RuntimeError("falha")
        yield

    monkeypatch.setattr(api.rag, "analisar", explode)
    with cliente(criar_servico(None), monkeypatch) as http:
        eventos = eventos_de(http.post("/api/analisar", json={"entrada": "Ivermectina cura covid"}))
        assert eventos == [{"tipo": "erro", "mensagem": "Erro interno ao analisar. Tente de novo."}]
