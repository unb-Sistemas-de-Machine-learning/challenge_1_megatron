from pathlib import Path

from prepara_fakerecogna import filtrar_categoria_saude, ler_fakerecogna

FIXTURE = Path(__file__).parent / "fixtures" / "fakerecogna_mini.parquet"


def test_le_o_parquet_com_as_colunas_esperadas():
    df = ler_fakerecogna(FIXTURE)
    assert list(df.columns) == ["Titulo", "Noticia", "Categoria", "URL", "Classe"]
    assert len(df) == 4


def test_filtra_apenas_categoria_saude():
    df = ler_fakerecogna(FIXTURE)
    saude = filtrar_categoria_saude(df)
    assert len(saude) == 3
    assert set(saude["Categoria"]) == {"saúde"}


def test_filtra_preserva_classe_original():
    df = ler_fakerecogna(FIXTURE)
    saude = filtrar_categoria_saude(df)
    assert sorted(saude["Classe"].tolist()) == [0.0, 0.0, 1.0]
