import json
import time

import numpy as np
import pytest

from verdade_ou_fake.banco import Banco


def _doc(id_externo="1", fonte="pubmed", titulo="Titulo", texto="Texto do resumo", **extra):
    return {
        "fonte": fonte,
        "id_externo": id_externo,
        "titulo": titulo,
        "texto": texto,
        "url": f"https://exemplo.org/{id_externo}",
        **extra,
    }


def _vetores(n, dim=4):
    return np.tile(np.arange(1, dim + 1, dtype=np.float32), (n, 1)) * np.arange(1, n + 1)[:, None]


@pytest.fixture
def banco():
    b = Banco(":memory:")
    yield b
    b.fechar()


def _consulta(banco, **campos):
    base = {"chave": "k", "tipo_entrada": "texto", "eventos": [{"tipo": "fim"}]}
    base.update(campos)
    return banco.registrar_consulta(**base)


def test_inserir_devolve_quantidade_de_novos(banco):
    assert banco.inserir_documentos([_doc("1"), _doc("2")], _vetores(2)) == 2
    assert banco.total_documentos() == 2


def test_inserir_ignora_duplicata_por_fonte_e_id_externo(banco):
    banco.inserir_documentos([_doc("1")], _vetores(1))
    inseridos = banco.inserir_documentos([_doc("1", titulo="Outro"), _doc("2")], _vetores(2))
    assert inseridos == 1
    assert banco.total_documentos() == 2
    assert banco.obter_documentos([1])[0].titulo == "Titulo"


def test_mesmo_id_externo_em_fontes_diferentes_nao_e_duplicata(banco):
    docs = [_doc("1", fonte="pubmed"), _doc("1", fonte="outra")]
    assert banco.inserir_documentos(docs, _vetores(2)) == 2


def test_duplicata_nao_cria_entrada_extra_no_indice_fts(banco):
    banco.inserir_documentos([_doc("1", texto="ivermectina")], _vetores(1))
    banco.inserir_documentos([_doc("1", texto="ivermectina")], _vetores(1))
    assert banco.buscar_texto('"ivermectina"', 10) == [1]


def test_inserir_com_tamanhos_diferentes_levanta_erro(banco):
    with pytest.raises(ValueError):
        banco.inserir_documentos([_doc("1"), _doc("2")], _vetores(1))


def test_inserir_guarda_origem_informada(banco):
    banco.inserir_documentos([_doc("1")], _vetores(1), origem="ao_vivo")
    assert banco.metricas()["documentos_por_origem"] == {"ao_vivo": 1}


def test_ids_existentes_filtra_por_fonte(banco):
    banco.inserir_documentos([_doc("1"), _doc("2"), _doc("9", fonte="outra")], _vetores(3))
    assert banco.ids_existentes("pubmed") == {"1", "2"}
    assert banco.ids_existentes("inexistente") == set()


def test_total_documentos_de_banco_vazio_e_zero(banco):
    assert banco.total_documentos() == 0


def test_carregar_embeddings_de_banco_vazio(banco):
    ids, matriz = banco.carregar_embeddings()
    assert ids.shape == (0,)
    assert matriz.shape[0] == 0


def test_carregar_embeddings_preserva_formato_ordem_e_valores(banco):
    vetores = _vetores(3)
    banco.inserir_documentos([_doc("a"), _doc("b"), _doc("c")], vetores)
    ids, matriz = banco.carregar_embeddings()
    assert ids.tolist() == [1, 2, 3]
    assert matriz.shape == (3, 4)
    assert matriz.dtype == np.float32
    np.testing.assert_allclose(matriz, vetores)


def test_buscar_texto_ordena_por_relevancia(banco):
    docs = [
        _doc("1", titulo="Dieta", texto="alimentacao saudavel"),
        _doc("2", titulo="Ivermectina", texto="ivermectina em covid"),
        _doc("3", titulo="Outro", texto="menciona ivermectina uma vez no meio de varias outras palavras"),
    ]
    banco.inserir_documentos(docs, _vetores(3))
    resultado = banco.buscar_texto('"ivermectina"', 10)
    assert resultado[0] == 2
    assert set(resultado) == {2, 3}


def test_buscar_texto_respeita_limite(banco):
    banco.inserir_documentos([_doc(str(i), texto="febre") for i in range(5)], _vetores(5))
    assert len(banco.buscar_texto('"febre"', 2)) == 2


def test_buscar_texto_ignora_acentos(banco):
    banco.inserir_documentos([_doc("1", texto="inflamação aguda")], _vetores(1))
    assert banco.buscar_texto('"inflamacao"', 10) == [1]


def test_buscar_texto_com_expressao_vazia_devolve_lista_vazia(banco):
    banco.inserir_documentos([_doc("1")], _vetores(1))
    assert banco.buscar_texto("", 10) == []


@pytest.mark.parametrize("expressao", ['"aberta', "AND OR", "((", "a NEAR/ b", "*"])
def test_buscar_texto_com_expressao_invalida_nao_levanta(banco, expressao):
    banco.inserir_documentos([_doc("1")], _vetores(1))
    assert isinstance(banco.buscar_texto(expressao, 10), list)


def test_obter_documentos_preserva_ordem_pedida(banco):
    banco.inserir_documentos([_doc("a"), _doc("b"), _doc("c")], _vetores(3))
    assert [d.id_externo for d in banco.obter_documentos([3, 1, 2])] == ["c", "a", "b"]


def test_obter_documentos_omite_ids_inexistentes(banco):
    banco.inserir_documentos([_doc("a")], _vetores(1))
    assert [d.id for d in banco.obter_documentos([99, 1, 50])] == [1]


def test_obter_documentos_com_lista_vazia(banco):
    assert banco.obter_documentos([]) == []


def test_obter_documentos_desserializa_tipos_e_ano(banco):
    banco.inserir_documentos(
        [_doc("1", tipos=["Systematic Review", "Meta-Analysis"], ano=2021), _doc("2")],
        _vetores(2),
    )
    primeiro, segundo = banco.obter_documentos([1, 2])
    assert primeiro.tipos == ["Systematic Review", "Meta-Analysis"]
    assert primeiro.ano == 2021
    assert segundo.tipos == []
    assert segundo.ano is None


def test_obter_documentos_preserva_texto_com_acentos(banco):
    banco.inserir_documentos([_doc("1", titulo="Ação", tipos=["Revisão"])], _vetores(1))
    doc = banco.obter_documentos([1])[0]
    assert doc.titulo == "Ação"
    assert doc.tipos == ["Revisão"]


def test_registrar_consulta_devolve_ids_crescentes(banco):
    assert _consulta(banco) == 1
    assert _consulta(banco) == 2


def test_buscar_cache_devolve_eventos_da_consulta(banco):
    _consulta(banco, eventos=[{"tipo": "token", "texto": "oi"}])
    assert banco.buscar_cache("k", 3600) == [{"tipo": "token", "texto": "oi"}]


def test_buscar_cache_sem_registro_devolve_none(banco):
    assert banco.buscar_cache("k", 3600) is None


def test_buscar_cache_ignora_respostas_que_vieram_do_cache(banco):
    _consulta(banco, do_cache=1)
    assert banco.buscar_cache("k", 3600) is None


def test_buscar_cache_ignora_outra_chave(banco):
    _consulta(banco, chave="outra")
    assert banco.buscar_cache("k", 3600) is None


def test_buscar_cache_ignora_consulta_sem_eventos(banco):
    banco.registrar_consulta(chave="k", tipo_entrada="texto")
    assert banco.buscar_cache("k", 3600) is None


def test_buscar_cache_respeita_validade(banco):
    _consulta(banco, criado_em=1.0)
    assert banco.buscar_cache("k", 3600) is None


def test_buscar_cache_devolve_a_mais_recente(banco):
    agora = time.time()
    _consulta(banco, criado_em=agora - 100, eventos=[{"v": "antiga"}])
    _consulta(banco, criado_em=agora - 10, eventos=[{"v": "nova"}])
    _consulta(banco, criado_em=agora - 50, eventos=[{"v": "meio"}])
    assert banco.buscar_cache("k", 3600) == [{"v": "nova"}]


def test_registrar_consulta_aceita_eventos_ja_serializados(banco):
    _consulta(banco, eventos=json.dumps([{"a": 1}]))
    assert banco.buscar_cache("k", 3600) == [{"a": 1}]


def test_registrar_feedback_atualiza_consulta_existente(banco):
    cid = _consulta(banco)
    assert banco.registrar_feedback(cid, 1) is True
    assert banco.metricas()["feedback_positivo"] == 1


def test_registrar_feedback_de_id_inexistente_devolve_false(banco):
    assert banco.registrar_feedback(999, 1) is False


def test_registrar_feedback_pode_ser_corrigido(banco):
    cid = _consulta(banco)
    banco.registrar_feedback(cid, 1)
    banco.registrar_feedback(cid, -1)
    m = banco.metricas()
    assert (m["feedback_positivo"], m["feedback_negativo"]) == (0, 1)


def test_metricas_de_banco_vazio(banco):
    assert banco.metricas() == {
        "consultas": 0,
        "respondidas_do_cache": 0,
        "com_busca_ao_vivo": 0,
        "feedback_positivo": 0,
        "feedback_negativo": 0,
        "citacoes_validas_media": None,
        "latencia_ms_p50": None,
        "latencia_ms_p95": None,
        "vereditos": {},
        "documentos_por_origem": {},
    }


def test_metricas_contam_consultas_cache_e_busca_ao_vivo(banco):
    _consulta(banco, do_cache=0, busca_ao_vivo=1)
    _consulta(banco, do_cache=1)
    _consulta(banco, do_cache=1)
    m = banco.metricas()
    assert m["consultas"] == 3
    assert m["respondidas_do_cache"] == 2
    assert m["com_busca_ao_vivo"] == 1


def test_metricas_contam_vereditos_incluindo_ausente(banco):
    _consulta(banco, veredito="provavelmente_falso")
    _consulta(banco, veredito="provavelmente_falso")
    _consulta(banco, veredito="sem_evidencia")
    _consulta(banco)
    assert banco.metricas()["vereditos"] == {
        "provavelmente_falso": 2,
        "sem_evidencia": 1,
        "sem_veredito": 1,
    }


def test_metricas_percentis_usam_so_consultas_geradas(banco):
    for ms in range(100, 1100, 100):
        _consulta(banco, latencia_ms=ms)
    _consulta(banco, latencia_ms=1, do_cache=1)
    m = banco.metricas()
    assert m["latencia_ms_p50"] == 600
    assert m["latencia_ms_p95"] == 1000


def test_metricas_percentil_com_uma_unica_latencia(banco):
    _consulta(banco, latencia_ms=250)
    m = banco.metricas()
    assert m["latencia_ms_p50"] == m["latencia_ms_p95"] == 250


def test_metricas_media_de_citacoes_ignora_cache_e_nulos(banco):
    _consulta(banco, citacoes_validas=2)
    _consulta(banco, citacoes_validas=3)
    _consulta(banco, citacoes_validas=9, do_cache=1)
    _consulta(banco)
    assert banco.metricas()["citacoes_validas_media"] == 2.5


def test_metricas_contam_feedback_positivo_e_negativo(banco):
    ids = [_consulta(banco) for _ in range(3)]
    banco.registrar_feedback(ids[0], 1)
    banco.registrar_feedback(ids[1], 1)
    banco.registrar_feedback(ids[2], -1)
    m = banco.metricas()
    assert (m["feedback_positivo"], m["feedback_negativo"]) == (2, 1)


def test_metricas_agrupam_documentos_por_origem(banco):
    banco.inserir_documentos([_doc("1"), _doc("2")], _vetores(2))
    banco.inserir_documentos([_doc("3")], _vetores(1), origem="ao_vivo")
    assert banco.metricas()["documentos_por_origem"] == {"lote": 2, "ao_vivo": 1}


def test_obter_pagina_inexistente_devolve_none(banco):
    assert banco.obter_pagina("https://x.org") is None


def test_guardar_e_obter_pagina(banco):
    banco.guardar_pagina("https://x.org", "Titulo", "Corpo")
    assert banco.obter_pagina("https://x.org") == ("Titulo", "Corpo")


def test_guardar_pagina_substitui_a_anterior(banco):
    banco.guardar_pagina("https://x.org", "Velho", "A")
    banco.guardar_pagina("https://x.org", "Novo", "B")
    assert banco.obter_pagina("https://x.org") == ("Novo", "B")


def test_banco_em_arquivo_persiste_entre_conexoes(tmp_path):
    caminho = tmp_path / "sub" / "vof.db"
    primeiro = Banco(caminho)
    primeiro.inserir_documentos([_doc("1", texto="ivermectina")], _vetores(1))
    primeiro.guardar_pagina("https://x.org", "T", "C")
    primeiro.fechar()

    segundo = Banco(caminho)
    assert segundo.total_documentos() == 1
    assert segundo.buscar_texto('"ivermectina"', 5) == [1]
    assert segundo.obter_pagina("https://x.org") == ("T", "C")
    segundo.fechar()


def test_reabrir_banco_nao_apaga_nem_duplica_dados(tmp_path):
    caminho = tmp_path / "vof.db"
    for _ in range(2):
        b = Banco(caminho)
        b.inserir_documentos([_doc("1")], _vetores(1))
        b.fechar()
    b = Banco(caminho)
    assert b.total_documentos() == 1
    b.fechar()
