from verdade_ou_fake.classificador import (
    carregar,
    construir_modelo,
    prever_risco,
    salvar,
    treinar,
)

TEXTOS = [
    "URGENTE!!! Médicos escondem cura milagrosa da covid-19 com ivermectina",
    "COMPARTILHE! Remédio secreto cura diabetes em 3 dias sem efeito colateral",
    "ATENÇÃO: a indústria não quer que você saiba dessa cura natural do câncer",
    "MILAGRE! Vitamina C elimina qualquer vírus, dizem especialistas ocultos",
    "Estudo publicado avalia eficácia da metformina no controle do diabetes tipo 2",
    "Pesquisa da universidade analisa uso de dexametasona em pacientes internados",
    "Ensaio clínico randomizado investiga efeito da losartana na hipertensão",
    "Revisão sistemática reúne dados sobre tratamento da asma em crianças",
]
ROTULOS = [1, 1, 1, 1, 0, 0, 0, 0]


def test_modelo_tem_vetorizador_e_classificador():
    modelo = construir_modelo()
    assert "tfidf" in modelo.named_steps
    assert "classificador" in modelo.named_steps


def test_treina_e_aprende_o_conjunto():
    modelo = treinar(TEXTOS, ROTULOS)
    assert modelo.score(TEXTOS, ROTULOS) == 1.0


def test_risco_fica_entre_zero_e_um():
    modelo = treinar(TEXTOS, ROTULOS)
    risco = prever_risco(modelo, "URGENTE! Cura milagrosa escondida pelos médicos")
    assert 0.0 <= risco <= 1.0


def test_texto_sensacionalista_tem_risco_maior_que_texto_sobrio():
    modelo = treinar(TEXTOS, ROTULOS)
    sensacionalista = prever_risco(
        modelo, "URGENTE!!! COMPARTILHE: cura milagrosa secreta que a indústria esconde"
    )
    sobrio = prever_risco(
        modelo, "Estudo publicado avalia a eficácia do tratamento em ensaio clínico"
    )
    assert sensacionalista > sobrio


def test_salva_e_carrega_preservando_a_previsao(tmp_path):
    modelo = treinar(TEXTOS, ROTULOS)
    caminho = tmp_path / "modelo.joblib"
    salvar(modelo, caminho)

    recarregado = carregar(caminho)
    texto = "Cura milagrosa da diabetes revelada"
    assert prever_risco(recarregado, texto) == prever_risco(modelo, texto)
