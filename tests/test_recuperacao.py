import numpy as np
import pytest

from verdade_ou_fake.banco import Banco
from verdade_ou_fake.recuperacao import Recuperador, montar_expressao_fts

VOCABULARIO = [
    "febre", "dengue", "vacina", "alho", "ivermectina", "covid", "pressao", "hipertensao",
    "diabetes", "insulina", "cha", "gripe",
]


def embutir(textos):
    linhas = []
    for texto in textos:
        palavras = texto.lower().split()
        v = np.array([palavras.count(p) for p in VOCABULARIO], dtype=np.float32)
        norma = np.linalg.norm(v)
        linhas.append(v / norma if norma else v)
    return np.vstack(linhas).astype(np.float32)


def _doc(id_externo, titulo, texto, tipos=None):
    return {
        "fonte": "pubmed",
        "id_externo": id_externo,
        "titulo": titulo,
        "texto": texto,
        "url": f"https://exemplo.org/{id_externo}",
        "tipos": tipos or [],
    }


def _popular(banco, docs):
    banco.inserir_documentos(docs, embutir([d["titulo"] + " " + d["texto"] for d in docs]))


@pytest.fixture
def banco():
    b = Banco(":memory:")
    yield b
    b.fechar()


def test_base_vazia_devolve_lista_vazia(banco):
    assert Recuperador(banco, embutir).buscar("febre dengue") == []


def test_documento_semanticamente_mais_proximo_vem_primeiro(banco):
    _popular(
        banco,
        [
            _doc("1", "alho", "alho alho pressao"),
            _doc("2", "dengue", "febre dengue febre"),
            _doc("3", "insulina", "diabetes insulina"),
        ],
    )
    trechos = Recuperador(banco, embutir).buscar("dengue febre")
    assert trechos[0].documento.id_externo == "2"


def test_similaridade_e_cosseno_entre_consulta_e_documento(banco):
    _popular(banco, [_doc("1", "dengue", "febre")])
    trecho = Recuperador(banco, embutir).buscar("dengue")[0]
    esperado = float(embutir(["dengue"])[0] @ embutir(["dengue febre"])[0])
    assert trecho.similaridade == pytest.approx(esperado, abs=1e-5)


def test_documento_so_lexical_entra_com_similaridade_calculada(banco):
    docs = [_doc(str(i), "gripe", "gripe febre") for i in range(40)]
    docs.append(_doc("raro", "tratamento", "ivermectina dengue xyzzyx"))
    _popular(banco, docs)
    trechos = Recuperador(banco, embutir).buscar("gripe dengue", termos_lexicais="xyzzyx", k=50)
    alvo = next(t for t in trechos if t.documento.id_externo == "raro")
    esperado = float(embutir(["gripe dengue"])[0] @ embutir(["tratamento ivermectina dengue xyzzyx"])[0])
    assert esperado > 0
    assert alvo.similaridade == pytest.approx(esperado, abs=1e-5)


def test_documento_so_lexical_sem_afinidade_tem_similaridade_zero(banco):
    docs = [_doc(str(i), "gripe", "gripe") for i in range(40)]
    docs.append(_doc("raro", "alho", "alho xyzzyx"))
    _popular(banco, docs)
    trechos = Recuperador(banco, embutir).buscar("gripe", termos_lexicais="xyzzyx", k=50)
    alvo = next(t for t in trechos if t.documento.id_externo == "raro")
    assert alvo.similaridade == pytest.approx(0.0, abs=1e-6)


def test_busca_lexical_resgata_documento_fora_dos_candidatos_vetoriais(banco):
    docs = [_doc(str(i), "gripe", "gripe") for i in range(40)]
    docs.append(_doc("raro", "alho", "alho xyzzyx"))
    _popular(banco, docs)
    recuperador = Recuperador(banco, embutir)
    sem = recuperador.buscar("gripe", termos_lexicais="gripe", k=50)
    com = recuperador.buscar("gripe", termos_lexicais="xyzzyx", k=50)
    assert "raro" not in {t.documento.id_externo for t in sem}
    assert "raro" in {t.documento.id_externo for t in com}


def test_bonus_de_revisao_sistematica_desempata(banco):
    _popular(
        banco,
        [
            _doc("estudo", "dengue", "dengue febre", tipos=["Journal Article"]),
            _doc("revisao", "dengue", "dengue febre", tipos=["Systematic Review"]),
        ],
    )
    trechos = Recuperador(banco, embutir).buscar("dengue febre")
    assert [t.documento.id_externo for t in trechos] == ["revisao", "estudo"]
    assert trechos[0].pontuacao > trechos[1].pontuacao


def test_bonus_de_meta_analise_vale_mais_que_o_de_ensaio_randomizado(banco):
    _popular(
        banco,
        [
            _doc("ensaio", "dengue", "dengue febre", tipos=["Randomized Controlled Trial"]),
            _doc("meta", "dengue", "dengue febre", tipos=["Meta-Analysis"]),
            _doc("comum", "dengue", "dengue febre"),
        ],
    )
    ordem = [t.documento.id_externo for t in Recuperador(banco, embutir).buscar("dengue febre")]
    assert ordem == ["meta", "ensaio", "comum"]


def test_k_limita_quantidade_de_resultados(banco):
    _popular(banco, [_doc(str(i), "dengue", f"dengue febre {i}") for i in range(10)])
    recuperador = Recuperador(banco, embutir)
    assert len(recuperador.buscar("dengue", k=3)) == 3
    assert len(recuperador.buscar("dengue", k=50)) == 10


def test_resultados_vem_em_ordem_decrescente_de_pontuacao(banco):
    _popular(
        banco,
        [_doc("1", "dengue", "dengue"), _doc("2", "gripe", "gripe febre"), _doc("3", "alho", "alho")],
    )
    pontuacoes = [t.pontuacao for t in Recuperador(banco, embutir).buscar("dengue febre")]
    assert pontuacoes == sorted(pontuacoes, reverse=True)


def test_matriz_e_recarregada_quando_documentos_novos_chegam(banco):
    _popular(banco, [_doc("1", "alho", "alho")])
    recuperador = Recuperador(banco, embutir)
    assert [t.documento.id_externo for t in recuperador.buscar("dengue")] == ["1"]
    _popular(banco, [_doc("2", "dengue", "dengue febre")])
    trechos = recuperador.buscar("dengue")
    assert trechos[0].documento.id_externo == "2"
    assert len(trechos) == 2


def test_base_vazia_que_recebe_documentos_passa_a_devolver_resultados(banco):
    recuperador = Recuperador(banco, embutir)
    assert recuperador.buscar("dengue") == []
    _popular(banco, [_doc("1", "dengue", "dengue")])
    assert len(recuperador.buscar("dengue")) == 1


def test_consulta_so_com_pontuacao_nao_levanta(banco):
    _popular(banco, [_doc("1", "dengue", "dengue")])
    assert isinstance(Recuperador(banco, embutir).buscar('"(--) AND NOT'), list)


def test_expressao_remove_palavras_vazias_e_curtas():
    assert montar_expressao_fts("o tratamento de dengue em uma pessoa") == (
        '"tratamento" OR "dengue" OR "pessoa"'
    )


def test_expressao_remove_palavras_vazias_em_ingles():
    assert montar_expressao_fts("does ivermectin treat covid") == '"ivermectin" OR "covid"'


def test_expressao_deduplica_ignorando_caixa():
    assert montar_expressao_fts("Dengue dengue DENGUE febre") == '"dengue" OR "febre"'


def test_expressao_limita_quantidade_de_termos():
    texto = " ".join(f"termo{i}" for i in range(30))
    expressao = montar_expressao_fts(texto)
    assert expressao.count(" OR ") == 11
    assert expressao.startswith('"termo0"')


def test_expressao_respeita_maximo_informado():
    assert montar_expressao_fts("alfa beta gama delta", maximo_termos=2) == '"alfa" OR "beta"'


def test_expressao_de_texto_sem_termos_uteis_e_vazia():
    assert montar_expressao_fts("o a de ?? !!") == ""
    assert montar_expressao_fts("") == ""


def test_expressao_mantem_hifen_interno_e_tira_hifen_das_pontas():
    assert montar_expressao_fts("covid-19 --febre--") == '"covid-19" OR "febre"'


@pytest.mark.parametrize(
    "texto",
    [
        'ivermectina "cura" (covid) AND febre',
        "dengue OR gripe NOT vacina",
        "NEAR(febre dengue) NOT AND OR",
        "febre* ^dengue {gripe} [covid] :insulina",
        "covid-19 -vacina +alho",
        "'aspas simples' e \"aspas duplas\" sem fechar\"",
        "operadores AND OR NOT em maiusculas",
    ],
)
def test_expressao_e_aceita_pelo_fts5(banco, texto):
    _popular(banco, [_doc("1", "titulo", "febre dengue covid-19 alho")])
    expressao = montar_expressao_fts(texto)
    banco._con.execute(
        "SELECT rowid FROM documentos_fts WHERE documentos_fts MATCH ?", (expressao,)
    ).fetchall()


def test_operadores_em_maiusculas_sao_tratados_como_termos_literais(banco):
    _popular(banco, [_doc("1", "titulo", "febre"), _doc("2", "titulo", "dengue")])
    expressao = montar_expressao_fts("FEBRE OR DENGUE")
    assert expressao == '"febre" OR "dengue"'
    assert sorted(banco.buscar_texto(expressao, 10)) == [1, 2]


def test_palavra_not_em_maiusculas_nao_exclui_documentos(banco):
    _popular(banco, [_doc("1", "titulo", "febre dengue")])
    expressao = montar_expressao_fts("FEBRE NOT DENGUE")
    assert banco.buscar_texto(expressao, 10) == [1]
