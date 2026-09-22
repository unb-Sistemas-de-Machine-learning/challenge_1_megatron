from pathlib import Path

from verdade_ou_fake.vocabulario import carregar_vocabulario, extrair_alegacao, normalizar

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"


def test_normalizar_remove_acento_e_caixa():
    assert normalizar("Hipertensão") == "hipertensao"
    assert normalizar("COVID-19") == "covid-19"


def test_carregar_separa_medicamentos_de_condicoes():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    assert "medicamento" in vocabulario
    assert "condicao" in vocabulario
    assert ("ivermectina", "Ivermectin") in vocabulario["medicamento"]
    assert ("covid-19", "COVID-19") in vocabulario["condicao"]


def test_extrai_o_par_quando_ambos_aparecem():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    texto = "Estudo aponta que a ivermectina cura covid-19 em dois dias."
    alegacao = extrair_alegacao(texto, vocabulario)
    assert alegacao is not None
    assert alegacao.medicamento_en == "Ivermectin"
    assert alegacao.condicao_en == "COVID-19"


def test_encontra_termos_com_acento_e_maiuscula():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    texto = "Nova pesquisa sobre Metformina no tratamento da Hipertensão."
    alegacao = extrair_alegacao(texto, vocabulario)
    assert alegacao is not None
    assert alegacao.medicamento_en == "Metformin"
    assert alegacao.condicao_en == "Hypertension"


def test_devolve_none_quando_falta_o_medicamento():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    texto = "Casos de dengue aumentam na região metropolitana."
    assert extrair_alegacao(texto, vocabulario) is None


def test_devolve_none_quando_falta_a_condicao():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    texto = "Preço da dipirona sobe 12% nas farmácias."
    assert extrair_alegacao(texto, vocabulario) is None


def test_nao_casa_termo_dentro_de_outra_palavra():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    texto = "O zincógrafo é uma máquina antiga usada contra a dengue."
    assert extrair_alegacao(texto, vocabulario) is None