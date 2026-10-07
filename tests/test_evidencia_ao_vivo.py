from pathlib import Path

import pytest
import requests

from verdade_ou_fake import evidencia

XML = (Path(__file__).parent / "fixtures" / "pubmed_resposta.xml").read_text(encoding="utf-8")


class _Resposta:
    def __init__(self, json_=None, text="", erro_http=False, json_invalido=False):
        self._json = json_
        self.text = text
        self._erro_http = erro_http
        self._json_invalido = json_invalido

    def raise_for_status(self):
        if self._erro_http:
            raise requests.HTTPError("500")

    def json(self):
        if self._json_invalido:
            raise ValueError("json invalido")
        return self._json


def _esearch(ids):
    return _Resposta(json_={"esearchresult": {"idlist": ids}})


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(evidencia, "_aguardar_vez", lambda: None)


@pytest.fixture
def rede(monkeypatch):
    estado = {"gets": [], "posts": [], "ids": ["1", "2"], "xml": XML}

    def get(url, params=None, **kwargs):
        estado["gets"].append({"url": url, "params": params, **kwargs})
        ids = estado["ids"]
        if callable(ids):
            ids = ids(params["term"])
        return _esearch(ids)

    def post(url, data=None, **kwargs):
        estado["posts"].append({"url": url, "data": data, **kwargs})
        return _Resposta(text=estado["xml"])

    monkeypatch.setattr(evidencia.requests, "get", get)
    monkeypatch.setattr(evidencia.requests, "post", post)
    return estado


def _citacao(xml):
    return evidencia.ET.fromstring(xml)


def test_buscar_pmids_devolve_lista_de_ids(rede):
    rede["ids"] = ["10", "20", "30"]
    assert evidencia.buscar_pmids("dengue") == ["10", "20", "30"]


def test_buscar_pmids_envia_termo_retmax_e_ordenacao(rede):
    evidencia.buscar_pmids("dengue vaccine", retmax=4)
    chamada = rede["gets"][0]
    assert chamada["url"].endswith("esearch.fcgi")
    assert chamada["params"]["term"] == "dengue vaccine"
    assert chamada["params"]["retmax"] == 4
    assert chamada["params"]["sort"] == "relevance"
    assert chamada["params"]["db"] == "pubmed"
    assert chamada["params"]["tool"] == evidencia.NOME_FERRAMENTA


def test_buscar_pmids_inclui_chave_e_email_do_ambiente(rede, monkeypatch):
    monkeypatch.setenv("NCBI_API_KEY", "abc")
    monkeypatch.setenv("NCBI_EMAIL", "a@b.c")
    evidencia.buscar_pmids("x")
    assert rede["gets"][0]["params"]["api_key"] == "abc"
    assert rede["gets"][0]["params"]["email"] == "a@b.c"


def test_buscar_pmids_levanta_em_erro_http(monkeypatch):
    monkeypatch.setattr(evidencia.requests, "get", lambda *a, **k: _Resposta(erro_http=True))
    with pytest.raises(requests.HTTPError):
        evidencia.buscar_pmids("x")


def test_buscar_pmids_aguarda_a_vez_antes_de_chamar(rede, monkeypatch):
    ordem = []
    monkeypatch.setattr(evidencia, "_aguardar_vez", lambda: ordem.append("espera"))
    original = evidencia.requests.get
    monkeypatch.setattr(
        evidencia.requests, "get", lambda *a, **k: (ordem.append("get"), original(*a, **k))[1]
    )
    evidencia.buscar_pmids("x")
    assert ordem == ["espera", "get"]


def test_baixar_artigos_com_lista_vazia_nao_chama_a_rede(rede):
    assert evidencia.baixar_artigos([]) == []
    assert rede["posts"] == []


def test_baixar_artigos_parseia_a_resposta_do_efetch(rede):
    artigos = evidencia.baixar_artigos(["33473311", "34145166"])
    assert [a.pmid for a in artigos] == ["33473311", "34145166"]
    assert artigos[0].tipos_estudo == ["Journal Article", "Systematic Review", "Meta-Analysis"]
    assert artigos[1].resumo == "Trial background. No significant difference was found."


def test_baixar_artigos_envia_ids_por_post(rede):
    evidencia.baixar_artigos(["1", "2", "3"])
    chamada = rede["posts"][0]
    assert chamada["url"].endswith("efetch.fcgi")
    assert chamada["data"]["id"] == "1,2,3"
    assert chamada["data"]["retmode"] == "xml"


def test_baixar_artigos_levanta_em_erro_http(monkeypatch):
    monkeypatch.setattr(evidencia.requests, "post", lambda *a, **k: _Resposta(erro_http=True))
    with pytest.raises(requests.HTTPError):
        evidencia.baixar_artigos(["1"])


def test_ao_vivo_devolve_artigos_com_resumo(rede):
    artigos = evidencia.buscar_artigos_ao_vivo("ivermectin covid")
    assert [a.pmid for a in artigos] == ["33473311", "34145166"]


def test_ao_vivo_primeira_busca_usa_filtro_de_estudos_fortes(rede):
    evidencia.buscar_artigos_ao_vivo("ivermectin covid", retmax=6)
    termo = rede["gets"][0]["params"]["term"]
    assert termo.startswith("(ivermectin covid) AND ")
    assert "systematic review[pt]" in termo
    assert rede["gets"][0]["params"]["retmax"] == 6


def test_ao_vivo_nao_repete_busca_quando_o_filtro_encontra(rede):
    evidencia.buscar_artigos_ao_vivo("x")
    assert len(rede["gets"]) == 1


def test_ao_vivo_sem_resultado_filtrado_tenta_sem_filtro(rede):
    rede["ids"] = lambda termo: [] if "systematic review" in termo else ["1"]
    artigos = evidencia.buscar_artigos_ao_vivo("raro")
    assert [g["params"]["term"] for g in rede["gets"]][1] == "raro"
    assert len(artigos) == 2
    assert rede["posts"][0]["data"]["id"] == "1"


def test_ao_vivo_sem_nenhum_resultado_devolve_vazio_sem_baixar(rede):
    rede["ids"] = []
    assert evidencia.buscar_artigos_ao_vivo("raro") == []
    assert len(rede["gets"]) == 2
    assert rede["posts"] == []


def test_ao_vivo_descarta_artigos_sem_resumo(rede):
    rede["xml"] = """<PubmedArticleSet>
      <PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
        <ArticleTitle>Sem resumo</ArticleTitle></Article></MedlineCitation></PubmedArticle>
      <PubmedArticle><MedlineCitation><PMID>2</PMID><Article>
        <ArticleTitle>Com resumo</ArticleTitle>
        <Abstract><AbstractText>Texto.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle>
    </PubmedArticleSet>"""
    assert [a.pmid for a in evidencia.buscar_artigos_ao_vivo("x")] == ["2"]


@pytest.mark.parametrize(
    "erro",
    [requests.ConnectionError("fora"), requests.Timeout("lento"), requests.HTTPError("503")],
)
def test_ao_vivo_erro_de_rede_na_busca_vira_lista_vazia(monkeypatch, erro):
    def get(*a, **k):
        raise erro

    monkeypatch.setattr(evidencia.requests, "get", get)
    assert evidencia.buscar_artigos_ao_vivo("x") == []


def test_ao_vivo_erro_de_rede_no_download_vira_lista_vazia(rede, monkeypatch):
    def post(*a, **k):
        raise requests.ConnectionError("fora")

    monkeypatch.setattr(evidencia.requests, "post", post)
    assert evidencia.buscar_artigos_ao_vivo("x") == []


def test_ao_vivo_resposta_com_formato_inesperado_vira_lista_vazia(monkeypatch):
    monkeypatch.setattr(
        evidencia.requests, "get", lambda *a, **k: _Resposta(json_={"erro": "limite"})
    )
    assert evidencia.buscar_artigos_ao_vivo("x") == []


def test_ao_vivo_json_invalido_vira_lista_vazia(monkeypatch):
    monkeypatch.setattr(
        evidencia.requests, "get", lambda *a, **k: _Resposta(json_invalido=True)
    )
    assert evidencia.buscar_artigos_ao_vivo("x") == []


def test_ao_vivo_xml_malformado_vira_lista_vazia(rede):
    rede["xml"] = "<PubmedArticleSet><PubmedArticle>"
    assert evidencia.buscar_artigos_ao_vivo("x") == []


def test_ano_cai_para_pubdate_quando_falta_date_completed():
    citacao = _citacao(
        "<MedlineCitation><Article><Journal><JournalIssue><PubDate><Year>2023</Year></PubDate>"
        "</JournalIssue></Journal></Article></MedlineCitation>"
    )
    assert evidencia._ano_de_publicacao(citacao) == 2023


def test_ano_prefere_date_completed_a_pubdate():
    citacao = _citacao(
        "<MedlineCitation><DateCompleted><Year>2021</Year></DateCompleted>"
        "<Article><Journal><JournalIssue><PubDate><Year>2023</Year></PubDate>"
        "</JournalIssue></Journal></Article></MedlineCitation>"
    )
    assert evidencia._ano_de_publicacao(citacao) == 2021


def test_ano_cai_para_article_date_quando_so_ela_existe():
    citacao = _citacao(
        "<MedlineCitation><Article><ArticleDate><Year>2024</Year></ArticleDate>"
        "</Article></MedlineCitation>"
    )
    assert evidencia._ano_de_publicacao(citacao) == 2024


def test_ano_ignora_valor_nao_numerico_e_usa_o_proximo():
    citacao = _citacao(
        "<MedlineCitation><DateCompleted><Year>abc</Year></DateCompleted>"
        "<Article><Journal><JournalIssue><PubDate><Year>2020</Year></PubDate>"
        "</JournalIssue></Journal></Article></MedlineCitation>"
    )
    assert evidencia._ano_de_publicacao(citacao) == 2020


def test_ano_ausente_devolve_none():
    assert evidencia._ano_de_publicacao(_citacao("<MedlineCitation/>")) is None


def test_pubdate_com_medline_date_sem_year_devolve_none():
    citacao = _citacao(
        "<MedlineCitation><Article><Journal><JournalIssue><PubDate>"
        "<MedlineDate>2019 Jan-Feb</MedlineDate></PubDate></JournalIssue></Journal></Article>"
        "</MedlineCitation>"
    )
    assert evidencia._ano_de_publicacao(citacao) is None


def test_parsear_usa_ano_do_pubdate_de_artigo_recente():
    xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>9</PMID><Article>
      <Journal><JournalIssue><PubDate><Year>2025</Year></PubDate></JournalIssue></Journal>
      <ArticleTitle>Recente</ArticleTitle>
      <Abstract><AbstractText>Texto.</AbstractText></Abstract>
      </Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
    assert evidencia.parsear_artigos(xml)[0].ano == 2025


def test_resumo_com_marcacao_interna_nao_e_cortado():
    xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>9</PMID><Article>
      <ArticleTitle>Efeito em <i>E. coli</i> e CO<sub>2</sub> elevado</ArticleTitle>
      <Abstract><AbstractText Label="RESULTS">A cepa <i>E. coli</i> cresceu 10<sup>3</sup> vezes mais.</AbstractText>
      <AbstractText Label="CONCLUSION">Sem efeito em <b>humanos</b>.</AbstractText></Abstract>
      </Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
    artigo = evidencia.parsear_artigos(xml)[0]
    assert artigo.resumo == "A cepa E. coli cresceu 103 vezes mais. Sem efeito em humanos."
    assert artigo.titulo == "Efeito em E. coli e CO2 elevado"


def test_resumo_que_comeca_com_marcacao_nao_fica_vazio():
    xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>9</PMID><Article>
      <ArticleTitle>T</ArticleTitle>
      <Abstract><AbstractText><i>Streptococcus</i> foi isolado.</AbstractText></Abstract>
      </Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
    assert evidencia.parsear_artigos(xml)[0].resumo == "Streptococcus foi isolado."
