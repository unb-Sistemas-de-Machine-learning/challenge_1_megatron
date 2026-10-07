import pandas as pd
import pytest

from treina_modelo import avaliar_cross_source

DF_DUAS_FONTES = pd.DataFrame({
    "id_par": ["1", "2", "3", "4"],
    "texto": ["a", "b", "c", "d"],
    "rotulo": [1, 0, 1, 0],
    "fonte": ["fakebr", "fakebr", "fakerecogna", "fakerecogna"],
})

DF_SO_FAKEBR = pd.DataFrame({
    "id_par": ["1", "2"],
    "texto": ["a", "b"],
    "rotulo": [1, 0],
    "fonte": ["fakebr", "fakebr"],
})


def _treinar_fn_falso(textos, rotulos):
    return {"treinado_com": len(textos)}


def _metrica_fn_falsa(modelo, textos, rotulos):
    return 0.7


def test_avalia_nas_duas_direcoes_quando_ambas_fontes_presentes():
    resultado = avaliar_cross_source(DF_DUAS_FONTES, _treinar_fn_falso, _metrica_fn_falsa)
    assert resultado["fakebr_para_fakerecogna"] == 0.7
    assert resultado["fakerecogna_para_fakebr"] == 0.7


def test_devolve_none_quando_falta_uma_fonte():
    resultado = avaliar_cross_source(DF_SO_FAKEBR, _treinar_fn_falso, _metrica_fn_falsa)
    assert resultado["fakebr_para_fakerecogna"] is None
    assert resultado["fakerecogna_para_fakebr"] is None


def test_treina_so_com_os_dados_da_fonte_de_origem():
    chamadas = []

    def treinar_fn_espiao(textos, rotulos):
        chamadas.append(len(textos))
        return {}

    avaliar_cross_source(DF_DUAS_FONTES, treinar_fn_espiao, _metrica_fn_falsa)
    assert chamadas == [2, 2]
