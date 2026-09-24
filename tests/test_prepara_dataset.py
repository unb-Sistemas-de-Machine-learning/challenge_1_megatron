import shutil
from pathlib import Path

import pandas as pd
import pytest

from prepara_dataset import (
    completar_pares,
    filtrar_saude,
    impressao_digital,
    ler_fakebr,
    termos_de_saude,
    verificar_integridade,
)

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"
FAKEBR_MINI = Path(__file__).parent / "fixtures" / "fakebr_mini"


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


def test_ler_fakebr_devolve_uma_linha_por_noticia():
    corpus = ler_fakebr(FAKEBR_MINI)
    assert len(corpus) == 6
    assert list(corpus.columns) == ["id_par", "texto", "rotulo", "categoria"]


def test_ler_fakebr_marca_falsa_como_1_e_verdadeira_como_0():
    corpus = ler_fakebr(FAKEBR_MINI).set_index(["id_par", "rotulo"])
    assert "URGENTE" in corpus.loc[("1", 1), "texto"]
    assert corpus.loc[("1", 0), "texto"].startswith("Estudo avalia")


def test_ler_fakebr_remove_bom_e_normaliza_quebra_de_linha():
    corpus = ler_fakebr(FAKEBR_MINI)
    verdadeira = corpus[(corpus["id_par"] == "1") & (corpus["rotulo"] == 0)].iloc[0]
    assert not verdadeira["texto"].startswith("\ufeff")
    assert "\r" not in verdadeira["texto"]


def test_ler_fakebr_traz_a_categoria_dos_metadados():
    corpus = ler_fakebr(FAKEBR_MINI)
    categorias = dict(zip(corpus["id_par"], corpus["categoria"]))
    assert categorias["1"] == "sociedade_cotidiano"
    assert categorias["2"] == "politica"


def test_ler_fakebr_le_categoria_quando_o_autor_esta_em_branco():
    # Nos metadados, a 1ª linha é o autor e às vezes vem só com espaço.
    corpus = ler_fakebr(FAKEBR_MINI)
    verdadeira = corpus[(corpus["id_par"] == "2") & (corpus["rotulo"] == 0)].iloc[0]
    assert verdadeira["categoria"] == "politica"


def test_ler_fakebr_aceita_noticia_sem_metadados():
    # No Fake.br real, os pares 697 e 1468 não têm arquivo de metadados.
    corpus = ler_fakebr(FAKEBR_MINI)
    sem_meta = corpus[corpus["id_par"] == "3"]
    assert len(sem_meta) == 2
    assert set(sem_meta["categoria"]) == {"desconhecida"}


def test_impressao_digital_e_deterministica():
    assert impressao_digital(FAKEBR_MINI) == impressao_digital(FAKEBR_MINI)


def test_impressao_digital_muda_se_um_texto_mudar(tmp_path):
    copia = tmp_path / "fakebr"
    shutil.copytree(FAKEBR_MINI, copia)
    original = impressao_digital(copia)
    (copia / "size_normalized_texts" / "fake" / "2.txt").write_text("alterado", encoding="utf-8")
    assert impressao_digital(copia) != original


def test_impressao_digital_ignora_arquivos_fora_do_corpus(tmp_path):
    copia = tmp_path / "fakebr"
    shutil.copytree(FAKEBR_MINI, copia)
    original = impressao_digital(copia)
    (copia / "README.md").write_text("qualquer coisa", encoding="utf-8")
    assert impressao_digital(copia) == original


def test_verificar_integridade_aceita_o_corpus_esperado():
    verificar_integridade(FAKEBR_MINI, impressao_digital(FAKEBR_MINI))


def test_verificar_integridade_recusa_corpus_diferente():
    with pytest.raises(ValueError, match="impressão digital"):
        verificar_integridade(FAKEBR_MINI, "0" * 64)


def test_completar_pares_traz_a_outra_metade_do_par():
    corpus = ler_fakebr(FAKEBR_MINI)
    so_a_falsa = corpus[(corpus["id_par"] == "1") & (corpus["rotulo"] == 1)]
    resultado = completar_pares(so_a_falsa, corpus)
    assert sorted(resultado["rotulo"]) == [0, 1]
    assert set(resultado["id_par"]) == {"1"}


def test_recorte_do_fakebr_mini_fica_balanceado():
    corpus = ler_fakebr(FAKEBR_MINI)
    recorte = filtrar_saude(corpus, "texto", termos_de_saude(CAMINHO_VOCABULARIO))
    resultado = completar_pares(recorte, corpus)
    assert resultado["rotulo"].value_counts().to_dict() == {1: 1, 0: 1}
