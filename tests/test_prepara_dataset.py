from pathlib import Path

import pandas as pd

from prepara_dataset import filtrar_saude, termos_de_saude

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"


def test_termos_de_saude_inclui_medicamentos_e_condicoes():
    termos = termos_de_saude(CAMINHO_VOCABULARIO)
    assert "ivermectina" in termos
    assert "diabetes" in termos


def test_mantem_apenas_as_linhas_com_termo_de_saude():
    df = pd.DataFrame(
        {
            "texto": [
                "A ivermectina foi testada contra a covid-19.",
                "Prefeitura anuncia obras na avenida principal.",
                "Novo estudo sobre metformina e diabetes.",
            ],
            "rotulo": [1, 0, 0],
        }
    )
    resultado = filtrar_saude(df, "texto", termos_de_saude(CAMINHO_VOCABULARIO))
    assert len(resultado) == 2
    assert "obras na avenida" not in " ".join(resultado["texto"])


def test_preserva_as_demais_colunas():
    df = pd.DataFrame({"texto": ["Estudo sobre dengue e dipirona."], "rotulo": [1]})
    resultado = filtrar_saude(df, "texto", termos_de_saude(CAMINHO_VOCABULARIO))
    assert list(resultado.columns) == ["texto", "rotulo"]
    assert resultado.iloc[0]["rotulo"] == 1


def test_casa_ignorando_acento_e_caixa():
    df = pd.DataFrame({"texto": ["Tratamento da HIPERTENSÃO com Losartana."], "rotulo": [0]})
    resultado = filtrar_saude(df, "texto", termos_de_saude(CAMINHO_VOCABULARIO))
    assert len(resultado) == 1


def test_dataframe_sem_saude_devolve_vazio():
    df = pd.DataFrame({"texto": ["Time vence por 3 a 0."], "rotulo": [0]})
    resultado = filtrar_saude(df, "texto", termos_de_saude(CAMINHO_VOCABULARIO))
    assert len(resultado) == 0