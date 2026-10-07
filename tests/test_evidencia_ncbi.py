from verdade_ou_fake import evidencia


class _Resposta:
    def __init__(self, json_=None, text=""):
        self._json = json_
        self.text = text

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def _capturar_chamadas(monkeypatch):
    chamadas = []

    def get_falso(url, params=None, **kwargs):
        chamadas.append(params)
        return _Resposta(json_={"esearchresult": {"idlist": ["1"]}})

    def post_falso(url, data=None, **kwargs):
        chamadas.append(data)
        return _Resposta(text="<PubmedArticleSet/>")

    monkeypatch.setattr(evidencia.requests, "get", get_falso)
    monkeypatch.setattr(evidencia.requests, "post", post_falso)
    monkeypatch.setattr(evidencia, "_aguardar_vez", lambda: None)
    return chamadas


def test_sem_variaveis_de_ambiente_identifica_so_a_ferramenta(monkeypatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    monkeypatch.delenv("NCBI_EMAIL", raising=False)
    chamadas = _capturar_chamadas(monkeypatch)

    evidencia.baixar_artigos(evidencia.buscar_pmids("ivermectin"))

    assert len(chamadas) == 2
    for params in chamadas:
        assert params["tool"] == evidencia.NOME_FERRAMENTA
        assert "api_key" not in params
        assert "email" not in params


def test_repassa_api_key_e_email_do_ambiente(monkeypatch):
    monkeypatch.setenv("NCBI_API_KEY", "chave-secreta")
    monkeypatch.setenv("NCBI_EMAIL", "equipe@exemplo.com")
    chamadas = _capturar_chamadas(monkeypatch)

    evidencia.baixar_artigos(evidencia.buscar_pmids("ivermectin"))

    for params in chamadas:
        assert params["api_key"] == "chave-secreta"
        assert params["email"] == "equipe@exemplo.com"


def test_intervalo_minimo_depende_da_chave(monkeypatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    sem_chave = evidencia._intervalo_minimo()
    monkeypatch.setenv("NCBI_API_KEY", "x")
    com_chave = evidencia._intervalo_minimo()

    assert sem_chave >= 1 / 3
    assert com_chave >= 1 / 10
    assert com_chave < sem_chave


def test_aguardar_vez_espaca_requisicoes_consecutivas(monkeypatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    relogio = [100.0]
    esperas = []
    monkeypatch.setattr(evidencia.time, "monotonic", lambda: relogio[0])
    monkeypatch.setattr(evidencia.time, "sleep", lambda s: esperas.append(s) or relogio.__setitem__(0, relogio[0] + s))
    monkeypatch.setattr(evidencia, "_ultima_requisicao", 0.0)

    evidencia._aguardar_vez()
    evidencia._aguardar_vez()

    assert esperas and abs(esperas[-1] - evidencia._intervalo_minimo()) < 1e-9
