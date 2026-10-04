import hashlib
from pathlib import Path

from prepara_fakerecogna import (
    filtrar_categoria_saude,
    impressao_digital_parquet,
    ler_fakerecogna,
    reextrair_textos,
    taxa_de_extracao,
)

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


from verdade_ou_fake.tipos import Noticia


def _extrator_falso_com_sucesso(url: str):
    return Noticia(url=url, titulo="t", texto="corpo da notícia recuperado", dominio="exemplo.invalid")


def _extrator_falso_que_sempre_falha(url: str):
    return None


def _extrator_falso_parcial(url: str):
    if "cancer" in url:
        return None
    return Noticia(url=url, titulo="t", texto="corpo recuperado", dominio="exemplo.invalid")


def test_reextrai_texto_e_monta_schema_compativel():
    df = filtrar_categoria_saude(ler_fakerecogna(FIXTURE))
    resultado = reextrair_textos(df, extrair=_extrator_falso_com_sucesso)
    assert list(resultado.columns) == ["id_par", "texto", "rotulo", "categoria", "fonte"]
    assert len(resultado) == 3
    assert set(resultado["fonte"]) == {"fakerecogna"}
    assert set(resultado["categoria"]) == {"saúde"}


def test_descarta_linhas_cuja_extracao_falha():
    df = filtrar_categoria_saude(ler_fakerecogna(FIXTURE))
    resultado = reextrair_textos(df, extrair=_extrator_falso_que_sempre_falha)
    assert len(resultado) == 0


def test_extracao_parcial_mantem_so_as_que_tiveram_sucesso():
    df = filtrar_categoria_saude(ler_fakerecogna(FIXTURE))
    resultado = reextrair_textos(df, extrair=_extrator_falso_parcial)
    assert len(resultado) == 2


def test_taxa_de_extracao_calcula_percentual():
    assert taxa_de_extracao(total=4, sucesso=3) == 0.75
    assert taxa_de_extracao(total=4, sucesso=0) == 0.0


def test_taxa_de_extracao_com_total_zero_nao_divide_por_zero():
    assert taxa_de_extracao(total=0, sucesso=0) == 0.0


def test_mapeia_classe_fakerecogna_para_rotulo_do_projeto():
    df = filtrar_categoria_saude(ler_fakerecogna(FIXTURE))
    resultado = reextrair_textos(df, extrair=_extrator_falso_com_sucesso)
    # Classe 0.0 (fake) -> rotulo 1 (desinformação); Classe 1.0 (real) -> rotulo 0
    linha_vacina = df[df["URL"].str.contains("vacina-autismo")].iloc[0]
    assert linha_vacina["Classe"] == 0.0
    linha_campanha = df[df["URL"].str.contains("campanha-vacinacao")].iloc[0]
    assert linha_campanha["Classe"] == 1.0
    assert set(resultado["rotulo"]) == {0, 1}


def test_impressao_digital_e_deterministica():
    assert impressao_digital_parquet(FIXTURE) == impressao_digital_parquet(FIXTURE)


def test_impressao_digital_muda_se_o_arquivo_mudar(tmp_path):
    copia = tmp_path / "fakerecogna.parquet"
    copia.write_bytes(FIXTURE.read_bytes() + b"\x00")
    assert impressao_digital_parquet(copia) != impressao_digital_parquet(FIXTURE)
