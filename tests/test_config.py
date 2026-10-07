from pathlib import Path

import pytest

from verdade_ou_fake.config import RAIZ, Config

VARIAVEIS = [
    "VOF_BANCO",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "GROQ_API_KEY",
    "LLM_MODELOS",
    "LLM_MODELO_RAPIDO",
    "VOF_MODELO_EMBEDDING",
    "VOF_SIMILARIDADE_MINIMA",
    "VOF_CACHE_HORAS",
    "VOF_LIMITE_POR_MINUTO",
    "VOF_BUSCA_AO_VIVO",
]


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    for nome in VARIAVEIS:
        monkeypatch.delenv(nome, raising=False)


def test_valores_padrao():
    c = Config()
    assert c.banco == RAIZ / "dados" / "vof.db"
    assert c.llm_base_url == "https://api.groq.com/openai/v1"
    assert c.llm_api_key == ""
    assert c.llm_modelos == [
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-120b",
        "llama-3.1-8b-instant",
    ]
    assert c.llm_modelo_rapido == "llama-3.1-8b-instant"
    assert c.modelo_embedding == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert c.fontes_por_resposta == 5
    assert c.similaridade_minima == 0.45
    assert c.cache_horas == 168
    assert c.limite_por_minuto == 12
    assert c.busca_ao_vivo is True


def test_llm_inativo_sem_chave():
    assert Config().llm_ativo is False


def test_llm_ativo_com_llm_api_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "segredo")
    c = Config()
    assert c.llm_api_key == "segredo"
    assert c.llm_ativo is True


def test_llm_ativo_com_groq_api_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq")
    c = Config()
    assert c.llm_api_key == "groq"
    assert c.llm_ativo is True


def test_llm_api_key_tem_precedencia_sobre_groq_api_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "nova")
    monkeypatch.setenv("GROQ_API_KEY", "antiga")
    assert Config().llm_api_key == "nova"


def test_llm_api_key_vazia_cai_para_groq_api_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "groq")
    assert Config().llm_api_key == "groq"


def test_llm_inativo_com_chave_mas_sem_modelos(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODELOS", " , ,")
    c = Config()
    assert c.llm_modelos == []
    assert c.llm_ativo is False


def test_modelos_ignoram_espacos_e_virgulas_sobrando(monkeypatch):
    monkeypatch.setenv("LLM_MODELOS", " a/b ,, c ,  d,")
    assert Config().llm_modelos == ["a/b", "c", "d"]


def test_modelos_preservam_ordem_de_prioridade(monkeypatch):
    monkeypatch.setenv("LLM_MODELOS", "z,a,m")
    assert Config().llm_modelos == ["z", "a", "m"]


def test_base_url_perde_barra_final(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1/")
    assert Config().llm_base_url == "http://localhost:11434/v1"


def test_base_url_perde_varias_barras_finais(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1///")
    assert Config().llm_base_url == "http://localhost:11434/v1"


def test_banco_vem_do_ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("VOF_BANCO", str(tmp_path / "x.db"))
    assert Config().banco == Path(tmp_path / "x.db")


def test_modelo_rapido_e_modelo_de_embedding_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv("LLM_MODELO_RAPIDO", "rapido")
    monkeypatch.setenv("VOF_MODELO_EMBEDDING", "outro/modelo")
    c = Config()
    assert c.llm_modelo_rapido == "rapido"
    assert c.modelo_embedding == "outro/modelo"


def test_similaridade_minima_lida_do_ambiente_depois_da_importacao(monkeypatch):
    monkeypatch.setenv("VOF_SIMILARIDADE_MINIMA", "0.7")
    assert Config().similaridade_minima == 0.7


def test_cache_horas_lido_do_ambiente_depois_da_importacao(monkeypatch):
    monkeypatch.setenv("VOF_CACHE_HORAS", "24")
    assert Config().cache_horas == 24


def test_limite_por_minuto_lido_do_ambiente_depois_da_importacao(monkeypatch):
    monkeypatch.setenv("VOF_LIMITE_POR_MINUTO", "3")
    assert Config().limite_por_minuto == 3


def test_busca_ao_vivo_pode_ser_desligada_depois_da_importacao(monkeypatch):
    monkeypatch.setenv("VOF_BUSCA_AO_VIVO", "0")
    assert Config().busca_ao_vivo is False


def test_busca_ao_vivo_continua_ligada_com_outro_valor(monkeypatch):
    monkeypatch.setenv("VOF_BUSCA_AO_VIVO", "1")
    assert Config().busca_ao_vivo is True


def test_instancias_criadas_em_momentos_diferentes_leem_o_ambiente_de_cada_momento(monkeypatch):
    primeira = Config()
    monkeypatch.setenv("VOF_CACHE_HORAS", "1")
    segunda = Config()
    assert primeira.cache_horas == 168
    assert segunda.cache_horas == 1


def test_config_e_imutavel():
    with pytest.raises(AttributeError):
        Config().cache_horas = 1
