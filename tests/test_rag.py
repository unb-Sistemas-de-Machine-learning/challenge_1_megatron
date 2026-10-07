import asyncio

from tests.apoio_rag import (
    ALEGACAO_IVERMECTINA,
    REDACAO_CONTESTADA,
    LLMFalso,
    criar_servico,
)
from verdade_ou_fake import rag
from verdade_ou_fake.tipos import Artigo, Noticia


def coletar(servico, entrada):
    async def rodar():
        return [evento async for evento in rag.analisar(servico, entrada)]

    return asyncio.run(rodar())


def do_tipo(eventos, tipo):
    return [e for e in eventos if e["tipo"] == tipo]


def test_alegacao_contestada_cita_apenas_fontes_existentes():
    servico = criar_servico(LLMFalso(ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA))
    eventos = coletar(servico, "Ivermectina cura covid-19")

    veredito = do_tipo(eventos, "veredito")[-1]
    assert veredito["codigo"] == "CONTESTADA"
    assert veredito["confianca"] == "alta"
    assert veredito["resumo"] == "Os estudos não mostram benefício."

    texto = "".join(e["texto"] for e in do_tipo(eventos, "texto"))
    assert "[1]" in texto and "[2]" in texto
    assert "[9]" not in texto
    assert "VEREDITO" not in texto and "---" not in texto

    fim = do_tipo(eventos, "fim")[0]
    assert fim["citadas"] == [1, 2]
    assert fim["modelo"] == "modelo-a"
    assert fim["do_cache"] is False
    assert isinstance(fim["consulta_id"], int)


def test_fontes_cobrem_todos_os_conceitos_da_alegacao():
    servico = criar_servico(LLMFalso(ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA))
    fontes = do_tipo(coletar(servico, "Ivermectina cura covid-19"), "fontes")[0]["fontes"]
    assert [f["n"] for f in fontes] == [1, 2]
    assert all("vermectin" in f["titulo"] for f in fontes)
    assert fontes[0]["forca"] == "forte"
    assert fontes[1]["forca"] == "moderada"


def test_veredito_sem_citacao_e_rebaixado_para_inconclusiva():
    redacao = "VEREDITO: APOIADA\nCONFIANCA: alta\nRESUMO: Funciona.\n---\nFunciona muito bem."
    servico = criar_servico(LLMFalso(ALEGACAO_IVERMECTINA, redacao))
    eventos = coletar(servico, "Ivermectina cura covid-19")
    vereditos = do_tipo(eventos, "veredito")
    assert vereditos[0]["codigo"] == "APOIADA"
    assert vereditos[-1]["codigo"] == "INCONCLUSIVA"
    assert vereditos[-1]["confianca"] == "baixa"
    assert "rebaixado" in do_tipo(eventos, "fim")[0]["aviso"]


def test_confianca_limitada_quando_so_ha_estudo_isolado_citado():
    redacao = "VEREDITO: CONTESTADA\nCONFIANCA: alta\nRESUMO: Não.\n---\nSem benefício [2]."
    servico = criar_servico(LLMFalso(ALEGACAO_IVERMECTINA, redacao))
    eventos = coletar(servico, "Ivermectina cura covid-19")
    assert do_tipo(eventos, "veredito")[-1]["confianca"] == "media"


def test_cabecalho_fora_do_formato_vira_inconclusiva():
    servico = criar_servico(LLMFalso(ALEGACAO_IVERMECTINA, "Não sei responder a isso."))
    veredito = do_tipo(coletar(servico, "Ivermectina cura covid-19"), "veredito")[-1]
    assert veredito["codigo"] == "INCONCLUSIVA"


def test_texto_fora_de_saude_nao_busca_nem_redige():
    falso = LLMFalso({"saude": False, "alegacao": "Novo ministro", "consulta_en": "new minister"}, "x")
    servico = criar_servico(falso)
    eventos = coletar(servico, "O presidente anunciou o novo ministro da economia")
    assert do_tipo(eventos, "veredito")[-1]["codigo"] == "FORA_DO_ESCOPO"
    assert do_tipo(eventos, "fontes") == []
    assert not any(chamada.get("stream") for chamada in falso.chamadas)


def test_sem_estudos_responde_nao_verificavel_e_nunca_falso():
    alegacao = {
        "saude": True,
        "alegacao": "Chá de boldo cura gripe",
        "consulta_en": "boldo tea for influenza",
        "pubmed": "boldo AND influenza",
    }
    falso = LLMFalso(alegacao, REDACAO_CONTESTADA)
    eventos = coletar(criar_servico(falso), "Chá de boldo cura gripe em dois dias")
    assert do_tipo(eventos, "veredito")[-1]["codigo"] == "NAO_VERIFICAVEL"
    assert do_tipo(eventos, "fontes")[0]["fontes"] == []
    assert "não significa que a alegação seja falsa" in "".join(
        e["texto"] for e in do_tipo(eventos, "texto")
    )
    assert not any(chamada.get("stream") for chamada in falso.chamadas)


def test_busca_ao_vivo_amplia_a_base_quando_a_cobertura_e_fraca():
    alegacao = {
        "saude": True,
        "alegacao": "Vitamina D previne gripe",
        "consulta_en": "vitamin for influenza prevention",
        "pubmed": "vitamin AND influenza",
    }
    pedidos = []

    def ao_vivo(termo):
        pedidos.append(termo)
        return [
            Artigo("77", "Vitamin D and influenza: systematic review",
                   "Vitamin supplementation slightly reduced influenza.", ["Systematic Review"], 2023),
            Artigo("78", "Vitamin D trial in influenza season",
                   "Vitamin had no effect on influenza incidence.", ["Randomized Controlled Trial"], 2020),
        ]  # fmt: skip

    redacao = "VEREDITO: EXAGERADA\nCONFIANCA: media\nRESUMO: Efeito pequeno.\n---\nEfeito pequeno [1]."
    servico = criar_servico(LLMFalso(alegacao, redacao), buscar_ao_vivo=ao_vivo)
    eventos = coletar(servico, "Vitamina D previne gripe")

    assert pedidos == ["vitamin AND influenza"]
    assert "Ampliando a busca no PubMed" in [e["texto"] for e in do_tipo(eventos, "etapa")]
    assert len(do_tipo(eventos, "fontes")[0]["fontes"]) == 2
    assert servico.banco.total_documentos() == 5
    assert servico.banco.metricas()["com_busca_ao_vivo"] == 1


def test_segunda_consulta_igual_vem_do_cache_sem_chamar_o_llm():
    falso = LLMFalso(ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA)
    servico = criar_servico(falso)
    primeira = coletar(servico, "Ivermectina cura covid-19")
    chamadas = len(falso.chamadas)
    segunda = coletar(servico, "  ivermectina   CURA covid-19 ")

    assert len(falso.chamadas) == chamadas
    fim = do_tipo(segunda, "fim")[0]
    assert fim["do_cache"] is True
    assert fim["citadas"] == [1, 2]
    assert fim["consulta_id"] != do_tipo(primeira, "fim")[0]["consulta_id"]
    assert do_tipo(segunda, "veredito")[-1] == do_tipo(primeira, "veredito")[-1]
    assert servico.banco.metricas()["respondidas_do_cache"] == 1


def test_sem_llm_usa_o_vocabulario_e_lista_as_fontes():
    servico = criar_servico(None)
    eventos = coletar(servico, "Dizem que a ivermectina cura a covid em três dias")
    assert do_tipo(eventos, "alegacao")[0]["texto"] == "Ivermectina trata covid"
    assert len(do_tipo(eventos, "fontes")[0]["fontes"]) == 2
    assert do_tipo(eventos, "veredito")[-1]["codigo"] == "INCONCLUSIVA"
    assert do_tipo(eventos, "fim")[0]["aviso"].startswith("Modo degradado")


def test_resposta_degradada_nao_entra_no_cache():
    servico = criar_servico(LLMFalso(None, None, status=429))
    coletar(servico, "Ivermectina cura covid-19")
    segunda = coletar(servico, "Ivermectina cura covid-19")
    assert do_tipo(segunda, "fim")[0]["do_cache"] is False


def test_json_invalido_do_llm_cai_no_vocabulario():
    servico = criar_servico(LLMFalso(None, REDACAO_CONTESTADA))
    eventos = coletar(servico, "Ivermectina cura covid-19")
    assert do_tipo(eventos, "alegacao")[0]["texto"] == "Ivermectina trata covid"
    assert do_tipo(eventos, "veredito")[-1]["codigo"] == "CONTESTADA"


def test_link_e_extraido_uma_vez_e_guardado():
    extracoes = []

    def extrair(url):
        extracoes.append(url)
        return Noticia(url, "Ivermectina cura covid, diz médico", "Texto da matéria sobre covid.", "x.com")

    servico = criar_servico(LLMFalso(ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA), extrair_noticia=extrair)
    eventos = coletar(servico, "https://x.com/materia")
    assert do_tipo(eventos, "alegacao")[0]["titulo_noticia"] == "Ivermectina cura covid, diz médico"
    coletar(servico, "https://x.com/materia")
    assert extracoes == ["https://x.com/materia"]


def test_link_ilegivel_devolve_erro_amigavel():
    eventos = coletar(criar_servico(None), "https://x.com/paywall")
    assert [e["tipo"] for e in eventos] == ["etapa", "erro"]
    assert "Cole o texto" in eventos[-1]["mensagem"]


def test_sinal_de_estilo_e_emitido_quando_ha_classificador():
    servico = criar_servico(
        LLMFalso(ALEGACAO_IVERMECTINA, REDACAO_CONTESTADA), calcular_estilo=lambda texto: 0.8312
    )
    assert do_tipo(coletar(servico, "Ivermectina cura covid-19"), "estilo") == [
        {"tipo": "estilo", "risco": 0.831}
    ]


def test_filtro_de_citacoes_trata_colchete_partido_entre_pedacos():
    filtro = rag.FiltroDeCitacoes(3)
    saida = filtro.alimentar("efeito [") + filtro.alimentar("1, 7] e [") + filtro.alimentar("3")
    saida += filtro.alimentar("] fim") + filtro.encerrar()
    assert saida == "efeito [1] e [3] fim"
    assert filtro.citadas == {1, 3}


def test_filtro_de_citacoes_preserva_colchete_que_nao_e_citacao():
    filtro = rag.FiltroDeCitacoes(2)
    saida = filtro.alimentar("dose [mg/kg] alta [2]") + filtro.encerrar()
    assert saida == "dose [mg/kg] alta [2]"


def test_cabecalho_aceita_variacoes_de_formatacao():
    resultado = rag.interpretar_cabecalho("**VEREDITO:** Exagerada\nConfiança: Média\nRESUMO: ok")
    assert (resultado.codigo, resultado.confianca, resultado.resumo) == ("EXAGERADA", "media", "ok")


def test_resposta_sem_separador_ainda_entrega_o_corpo():
    redacao = "VEREDITO: CONTESTADA\nCONFIANCA: alta\nRESUMO: Não funciona.\n\nA meta-análise não viu efeito [1]."
    eventos = coletar(criar_servico(LLMFalso(ALEGACAO_IVERMECTINA, redacao)), "Ivermectina cura covid-19")
    texto = "".join(e["texto"] for e in do_tipo(eventos, "texto"))
    assert texto == "A meta-análise não viu efeito [1]."
    assert do_tipo(eventos, "veredito")[-1]["codigo"] == "CONTESTADA"
    assert do_tipo(eventos, "fim")[0]["citadas"] == [1]


def test_resposta_so_com_cabecalho_ganha_texto_padrao_e_registra_o_modelo():
    redacao = "VEREDITO: INCONCLUSIVA\nCONFIANCA: baixa\nRESUMO: Estudos limitados."
    eventos = coletar(criar_servico(LLMFalso(ALEGACAO_IVERMECTINA, redacao)), "Ivermectina cura covid-19")
    assert "".join(e["texto"] for e in do_tipo(eventos, "texto")) == rag.SEM_DETALHE
    assert do_tipo(eventos, "fim")[0]["modelo"] == "modelo-a"


def test_cabecalho_longo_sem_separador_nao_vaza_para_o_corpo():
    cabecalho, corpo = rag.separar_cabecalho("**VEREDITO:** APOIADA\nCONFIANÇA: media\nRESUMO: ok\nTexto [2].")
    assert corpo == "Texto [2]."
    assert "RESUMO" in cabecalho


def test_conceitos_ignoram_termos_genericos_do_vocabulario():
    assert rag._conceitos("Vitamin D AND Influenza, Human") == [["vitamin"], ["influenza"]]


def test_trecho_do_resumo_preserva_o_inicio_e_a_conclusao():
    texto = "INICIO " + "x" * 3000 + " CONCLUSAO"
    trecho = rag.trecho_do_resumo(texto)
    assert trecho.startswith("INICIO") and trecho.endswith("CONCLUSAO")
    assert len(trecho) < 1200
    assert rag.trecho_do_resumo("curto") == "curto"


def test_fora_de_saude_com_campos_vazios_ainda_e_fora_do_escopo():
    falso = LLMFalso({"saude": False, "alegacao": "", "consulta_en": "", "pubmed": ""}, "x")
    eventos = coletar(criar_servico(falso), "O governo anunciou hoje o novo ministro da economia")
    assert do_tipo(eventos, "veredito")[-1]["codigo"] == "FORA_DO_ESCOPO"
