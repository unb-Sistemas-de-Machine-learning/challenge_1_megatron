from pathlib import Path

from verdade_ou_fake.evidencia import (
    classificar_forca,
    montar_evidencia,
    montar_query,
    parsear_artigos,
)
from verdade_ou_fake.tipos import Alegacao, Artigo

FIXTURES = Path(__file__).parent / "fixtures"


def carregar_xml() -> str:
    return (FIXTURES / "pubmed_resposta.xml").read_text(encoding="utf-8")


def artigo(tipos: list[str]) -> Artigo:
    return Artigo(pmid="1", titulo="t", resumo="r", tipos_estudo=tipos, ano=2020)


def test_monta_query_com_os_termos_em_ingles():
    alegacao = Alegacao(
        medicamento_pt="ivermectina",
        medicamento_en="Ivermectin",
        condicao_pt="covid-19",
        condicao_en="COVID-19",
    )
    assert montar_query(alegacao) == '"Ivermectin"[MeSH Terms] AND "COVID-19"[MeSH Terms]'


def test_parseia_os_dois_artigos_da_resposta():
    artigos = parsear_artigos(carregar_xml())
    assert len(artigos) == 2
    assert artigos[0].pmid == "33473311"
    assert artigos[0].ano == 2021


def test_parseia_titulo_e_tipos_de_estudo():
    artigos = parsear_artigos(carregar_xml())
    assert "Ivermectin" in artigos[0].titulo
    assert "Meta-Analysis" in artigos[0].tipos_estudo
    assert artigos[1].tipos_estudo == ["Randomized Controlled Trial"]


def test_junta_as_secoes_do_resumo():
    artigos = parsear_artigos(carregar_xml())
    assert "Trial background." in artigos[1].resumo
    assert "No significant difference was found." in artigos[1].resumo


def test_xml_vazio_devolve_lista_vazia():
    assert parsear_artigos("<PubmedArticleSet></PubmedArticleSet>") == []


def test_revisao_sistematica_e_forca_forte():
    assert classificar_forca([artigo(["Systematic Review"])]) == "forte"
    assert classificar_forca([artigo(["Meta-Analysis"])]) == "forte"


def test_ensaio_randomizado_e_forca_moderada():
    assert classificar_forca([artigo(["Randomized Controlled Trial"])]) == "moderada"


def test_demais_tipos_sao_forca_fraca():
    assert classificar_forca([artigo(["Case Reports"])]) == "fraca"


def test_sem_artigos_a_forca_e_nenhuma():
    assert classificar_forca([]) == "nenhuma"


def test_a_forca_e_a_do_melhor_artigo_encontrado():
    artigos = [artigo(["Case Reports"]), artigo(["Systematic Review"])]
    assert classificar_forca(artigos) == "forte"


def test_evidencia_sem_artigos_e_nao_cobre():
    evidencia = montar_evidencia([])
    assert evidencia.cobertura == "nao_cobre"
    assert evidencia.forca == "nenhuma"


def test_evidencia_com_artigos_e_encontrada():
    evidencia = montar_evidencia(parsear_artigos(carregar_xml()))
    assert evidencia.cobertura == "encontrada"
    assert evidencia.forca == "forte"
    assert len(evidencia.artigos) == 2