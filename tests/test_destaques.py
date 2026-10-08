import asyncio
from datetime import date

from tests.apoio_rag import ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA, LLMFalso, criar_servico
from verdade_ou_fake import destaques
from verdade_ou_fake.config import Config
from verdade_ou_fake.tipos import Artigo

RSS = """<rss><channel>
<item><title>Ivermectina volta a circular em grupos - Portal X</title>
<link>https://news.google.com/rss/articles/a1</link><source url="https://x.com">Portal X</source></item>
<item><title>Sem fonte declarada</title><link>https://news.google.com/rss/articles/a2</link></item>
<item><title>Link inseguro</title><link>javascript:alert(1)</link></item>
</channel></rss>"""

REDACAO_INCONCLUSIVA = "VEREDITO: INCONCLUSIVA\nCONFIANCA: media\nRESUMO: Pouco estudo.\n---\nPouco [1]."


def servico_com(llm, **config):
    return criar_servico(llm, config=Config(destaques_pausa=0, **config))


def atualizar(servico, temas_da_planilha=(), manchetes=(), noticias=()):
    return asyncio.run(
        destaques.atualizar(
            servico,
            ler=lambda url: list(temas_da_planilha),
            manchetes=lambda: list(manchetes),
            buscar_noticias=lambda tema: list(noticias),
        )
    )


def test_planilha_usa_a_coluna_de_alegacao_e_ignora_linhas_curtas_e_repetidas():
    csv_ = "Data,Alegação,Obs\n,Ivermectina cura covid-19,x\n,oi,\n,Ivermectina   cura covid-19,\n,Vitamina D previne gripe,\n"
    assert destaques.parsear_planilha(csv_) == ["Ivermectina cura covid-19", "Vitamina D previne gripe"]


def test_planilha_sem_cabecalho_conhecido_usa_a_primeira_coluna():
    assert destaques.parsear_planilha("assunto\nMetformina cura o câncer\n") == ["Metformina cura o câncer"]


def test_planilha_descarta_temas_com_data_fora_da_semana():
    csv_ = "data,tema\n01/10/2026,Tema da semana atual\n10/09/2026,Tema antigo demais\n2026-10-07,Tema em formato ISO\ninválida,Tema com data ilegível\n"
    assert destaques.parsear_planilha(csv_, hoje=date(2026, 10, 7)) == [
        "Tema da semana atual",
        "Tema em formato ISO",
        "Tema com data ilegível",
    ]


def test_planilha_vazia_devolve_lista_vazia():
    assert destaques.parsear_planilha("") == []


def test_rss_extrai_titulo_sem_o_veiculo_e_descarta_link_inseguro():
    assert destaques.parsear_rss(RSS, 5) == [
        {"titulo": "Ivermectina volta a circular em grupos", "url": "https://news.google.com/rss/articles/a1", "fonte": "Portal X"},
        {"titulo": "Sem fonte declarada", "url": "https://news.google.com/rss/articles/a2", "fonte": ""},
    ]
    assert len(destaques.parsear_rss(RSS, 1)) == 1
    assert destaques.parsear_rss("isto não é xml", 5) == []


def test_tema_da_planilha_alimenta_a_base_e_vira_destaque_com_noticias():
    artigos = [Artigo("900", "Ivermectin covid new trial", "Ivermectin had no effect on covid.", ["Randomized Controlled Trial"], 2026)]
    servico = servico_com(
        LLMFalso(ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA),
        planilha_csv="https://planilha",
        destaques_automaticos=False,
    )
    servico.buscar_ao_vivo = lambda termo: artigos
    noticia = {"titulo": "Boato volta", "url": "https://news.google.com/x", "fonte": "G1"}

    assert atualizar(servico, temas_da_planilha=["Ivermectina cura covid-19"], noticias=[noticia]) == 1

    [item] = servico.banco.listar_destaques()
    assert item["alegacao"] == "Ivermectina cura covid-19"
    assert item["origem"] == "curadoria"
    assert item["veredito"] == "CONTESTADA"
    assert item["noticias"] == [noticia]
    assert item["novos_artigos"] == 1
    assert servico.banco.metricas()["documentos_por_origem"]["destaque"] == 1


def test_tema_da_planilha_aparece_mesmo_com_veredito_inconclusivo():
    servico = servico_com(
        LLMFalso(ALEGACAO_IVERMECTINA, REDACAO_INCONCLUSIVA),
        planilha_csv="https://planilha",
        destaques_automaticos=False,
    )
    assert atualizar(servico, temas_da_planilha=["Ivermectina cura covid-19"]) == 1


class LLMDeManchetes(LLMFalso):
    def __call__(self, request):
        import json

        import httpx

        corpo = json.loads(request.content)
        if "manchetes de saúde" in corpo["messages"][0]["content"]:
            self.chamadas.append(corpo)
            conteudo = json.dumps({"alegacoes": ["Ivermectina cura covid-19"]})
            return httpx.Response(200, json={"choices": [{"message": {"content": conteudo}}]})
        return super().__call__(request)


def test_tema_automatico_so_aparece_com_veredito_afirmativo_de_confianca_alta():
    fraco = servico_com(LLMDeManchetes(ALEGACAO_IVERMECTINA, REDACAO_INCONCLUSIVA))
    assert atualizar(fraco, manchetes=["Ivermectina cura covid, diz post"]) == 0
    assert fraco.banco.listar_destaques() == []

    forte = servico_com(LLMDeManchetes(ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA))
    assert atualizar(forte, manchetes=["Ivermectina cura covid, diz post"]) == 1
    assert forte.banco.listar_destaques()[0]["origem"] == "google_noticias"


def test_atualizacao_sem_nenhum_tema_pronto_preserva_os_destaques_anteriores():
    servico = servico_com(
        LLMFalso(ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA),
        planilha_csv="https://planilha",
        destaques_automaticos=False,
    )
    atualizar(servico, temas_da_planilha=["Ivermectina cura covid-19"])
    assert atualizar(servico, temas_da_planilha=[]) == 0
    assert len(servico.banco.listar_destaques()) == 1


def test_tema_fora_de_saude_e_descartado():
    falso = LLMFalso({"saude": False, "alegacao": "", "consulta_en": "", "pubmed": ""}, "x")
    servico = servico_com(falso, planilha_csv="https://planilha", destaques_automaticos=False)
    assert atualizar(servico, temas_da_planilha=["O novo ministro da economia tomou posse"]) == 0


def test_respeita_o_maximo_de_temas():
    servico = servico_com(
        LLMFalso(ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA),
        planilha_csv="https://planilha",
        destaques_automaticos=False,
        destaques_maximo=2,
    )
    temas = [f"Ivermectina cura covid-19 variante {i}" for i in range(5)]
    assert atualizar(servico, temas_da_planilha=temas) == 2
