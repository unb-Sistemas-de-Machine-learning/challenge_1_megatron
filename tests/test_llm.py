import asyncio
import json

import httpx
import pytest

from verdade_ou_fake.llm import ClienteLLM, LLMIndisponivel, _ler_sse, _sem_pensamento

MENSAGENS = [{"role": "user", "content": "oi"}]


def _resposta_json(conteudo):
    return httpx.Response(200, json={"choices": [{"message": {"content": conteudo}}]})


def _sse(*pedacos, fim=True):
    linhas = [f"data: {json.dumps({'choices': [{'delta': {'content': p}}]})}\n\n" for p in pedacos]
    if fim:
        linhas.append("data: [DONE]\n\n")
    return httpx.Response(
        200, content="".join(linhas).encode(), headers={"content-type": "text/event-stream"}
    )


def _cliente(manipulador, modelos=("m1", "m2")):
    return ClienteLLM(
        "https://llm.exemplo/v1", "chave", list(modelos), transporte=httpx.MockTransport(manipulador)
    )


def _por_modelo(respostas, chamadas=None):
    def manipulador(requisicao):
        corpo = json.loads(requisicao.content)
        if chamadas is not None:
            chamadas.append(corpo)
        return respostas[corpo["model"]]

    return manipulador


async def _coletar(gerador):
    return [pedaco async for pedaco in gerador]


async def _gerar(*pedacos):
    for p in pedacos:
        yield p


def _transmitir(cliente):
    async def rodar():
        try:
            return await _coletar(cliente.transmitir(MENSAGENS))
        finally:
            await cliente.fechar()

    return asyncio.run(rodar())


def _completar(cliente, **kwargs):
    async def rodar():
        try:
            return await cliente.completar(MENSAGENS, **kwargs)
        finally:
            await cliente.fechar()

    return asyncio.run(rodar())


def test_completar_devolve_o_conteudo():
    cliente = _cliente(lambda r: _resposta_json("  resposta  "))
    assert _completar(cliente) == "resposta"


def test_completar_envia_autorizacao_e_corpo_esperado():
    vistas = []

    def manipulador(requisicao):
        vistas.append(requisicao)
        return _resposta_json("ok")

    _completar(_cliente(manipulador), max_tokens=77)
    corpo = json.loads(vistas[0].content)
    assert vistas[0].headers["authorization"] == "Bearer chave"
    assert vistas[0].url.path.endswith("/chat/completions")
    assert corpo["model"] == "m1"
    assert corpo["max_tokens"] == 77
    assert corpo["messages"] == MENSAGENS
    assert "response_format" not in corpo


def test_completar_envia_response_format_quando_formato_json():
    chamadas = []
    _completar(_cliente(_por_modelo({"m1": _resposta_json("{}")}, chamadas)), formato_json=True)
    assert chamadas[0]["response_format"] == {"type": "json_object"}


def test_completar_remove_bloco_de_pensamento():
    cliente = _cliente(lambda r: _resposta_json("<think>raciocinio\nlongo</think>\n\nVeredito"))
    assert _completar(cliente) == "Veredito"


def test_completar_com_conteudo_nulo_devolve_vazio():
    cliente = _cliente(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": None}}]}))
    assert _completar(cliente) == ""


def test_completar_tenta_proximo_modelo_apos_429_e_registra_ultimo_modelo():
    chamadas = []
    cliente = _cliente(
        _por_modelo({"m1": httpx.Response(429), "m2": _resposta_json("do segundo")}, chamadas)
    )
    assert _completar(cliente) == "do segundo"
    assert [c["model"] for c in chamadas] == ["m1", "m2"]
    assert cliente.ultimo_modelo == "m2"


@pytest.mark.parametrize("status", [404, 408, 413, 500, 502, 503, 504])
def test_completar_tenta_proximo_modelo_em_erros_recuperaveis(status):
    cliente = _cliente(_por_modelo({"m1": httpx.Response(status), "m2": _resposta_json("ok")}))
    assert _completar(cliente) == "ok"


def test_completar_tenta_proximo_modelo_quando_corpo_nao_e_json():
    cliente = _cliente(_por_modelo({"m1": httpx.Response(200, content=b"nao e json"), "m2": _resposta_json("ok")}))
    assert _completar(cliente) == "ok"


def test_completar_tenta_proximo_modelo_quando_resposta_nao_tem_choices():
    cliente = _cliente(_por_modelo({"m1": httpx.Response(200, json={"choices": []}), "m2": _resposta_json("ok")}))
    assert _completar(cliente) == "ok"


def test_completar_tenta_proximo_modelo_em_erro_de_conexao():
    def manipulador(requisicao):
        if json.loads(requisicao.content)["model"] == "m1":
            raise httpx.ConnectError("sem rede")
        return _resposta_json("ok")

    assert _completar(_cliente(manipulador)) == "ok"


def test_completar_levanta_apos_tentar_todos_quando_erro_e_de_autenticacao():
    chamadas = []
    cliente = _cliente(_por_modelo({"m1": httpx.Response(401), "m2": httpx.Response(401)}, chamadas))
    with pytest.raises(LLMIndisponivel):
        _completar(cliente)
    assert [c["model"] for c in chamadas] == ["m1", "m2"]


def test_completar_levanta_quando_todos_os_modelos_falham():
    cliente = _cliente(lambda r: httpx.Response(429))
    with pytest.raises(LLMIndisponivel):
        _completar(cliente)
    assert cliente.ultimo_modelo is None


def test_completar_com_lista_de_modelos_vazia_levanta():
    cliente = _cliente(lambda r: _resposta_json("ok"), modelos=())
    with pytest.raises(LLMIndisponivel):
        _completar(cliente)


def test_completar_tenta_primeiro_o_modelo_preferido():
    chamadas = []
    cliente = _cliente(
        _por_modelo({"m1": _resposta_json("a"), "m2": _resposta_json("b")}, chamadas),
    )
    assert _completar(cliente, modelo="m2") == "b"
    assert [c["model"] for c in chamadas] == ["m2"]
    assert cliente.ultimo_modelo == "m2"


def test_completar_com_modelo_preferido_fora_da_lista_usa_a_lista_como_reserva():
    chamadas = []
    cliente = _cliente(
        _por_modelo(
            {"extra": httpx.Response(429), "m1": _resposta_json("a"), "m2": _resposta_json("b")},
            chamadas,
        )
    )
    assert _completar(cliente, modelo="extra") == "a"
    assert [c["model"] for c in chamadas] == ["extra", "m1"]


def test_completar_com_preferido_que_falha_nao_repete_o_modelo():
    chamadas = []
    cliente = _cliente(
        _por_modelo({"m1": _resposta_json("a"), "m2": httpx.Response(429)}, chamadas)
    )
    assert _completar(cliente, modelo="m2") == "a"
    assert [c["model"] for c in chamadas] == ["m2", "m1"]


def test_transmitir_junta_os_pedacos_do_sse():
    cliente = _cliente(lambda r: _sse("Ol", "á, ", "mundo"))
    pedacos = _transmitir(cliente)
    assert "".join(pedacos) == "Olá, mundo"


def test_transmitir_envia_stream_verdadeiro():
    chamadas = []
    _transmitir(_cliente(_por_modelo({"m1": _sse("x")}, chamadas)))
    assert chamadas[0]["stream"] is True
    assert chamadas[0]["model"] == "m1"


def test_transmitir_registra_ultimo_modelo():
    cliente = _cliente(lambda r: _sse("x"))
    _transmitir(cliente)
    assert cliente.ultimo_modelo == "m1"


def test_transmitir_ignora_linhas_que_nao_sao_data_e_json_invalido():
    corpo = (
        ": comentario keep-alive\n"
        "event: mensagem\n"
        "data: {json quebrado\n"
        'data: {"choices": []}\n'
        'data: {"choices":[{"delta":{}}]}\n'
        'data: {"choices":[{"delta":{"content":"A"}}]}\n'
        "\n"
        'data: {"choices":[{"delta":{"content":"B"}}]}\n'
        "data: [DONE]\n"
        'data: {"choices":[{"delta":{"content":"depois do fim"}}]}\n'
    )
    cliente = _cliente(lambda r: httpx.Response(200, content=corpo.encode()))
    assert "".join(_transmitir(cliente)) == "AB"


def test_transmitir_aceita_data_sem_espaco_depois_dos_dois_pontos():
    corpo = 'data:{"choices":[{"delta":{"content":"ok"}}]}\ndata:[DONE]\n'
    cliente = _cliente(lambda r: httpx.Response(200, content=corpo.encode()))
    assert _transmitir(cliente) == ["ok"]


def test_transmitir_cai_para_o_proximo_modelo_em_429():
    chamadas = []
    cliente = _cliente(_por_modelo({"m1": httpx.Response(429), "m2": _sse("do ", "segundo")}, chamadas))
    assert "".join(_transmitir(cliente)) == "do segundo"
    assert [c["model"] for c in chamadas] == ["m1", "m2"]
    assert cliente.ultimo_modelo == "m2"


def test_transmitir_remove_pensamento_inteiro_em_um_pedaco():
    cliente = _cliente(lambda r: _sse("<think>raciocinio</think>\n\nResposta"))
    assert "".join(_transmitir(cliente)) == "Resposta"


def test_transmitir_remove_pensamento_com_tag_partida_em_varios_pedacos():
    cliente = _cliente(lambda r: _sse("<th", "ink>racio", "cinio</thi", "nk>\n", "\nRespo", "sta"))
    assert "".join(_transmitir(cliente)) == "Resposta"


def test_transmitir_texto_que_comeca_com_menor_que_passa_intacto():
    cliente = _cliente(lambda r: _sse("<", "b>negrito</b> e <", "i>x"))
    assert "".join(_transmitir(cliente)) == "<b>negrito</b> e <i>x"


def test_transmitir_com_corpo_sem_conteudo_devolve_vazio():
    cliente = _cliente(lambda r: httpx.Response(200, content=b"data: [DONE]\n"))
    assert _transmitir(cliente) == []


def test_transmitir_com_corpo_totalmente_vazio_devolve_vazio():
    cliente = _cliente(lambda r: httpx.Response(200, content=b""))
    assert _transmitir(cliente) == []


def test_transmitir_levanta_quando_todos_os_modelos_falham():
    cliente = _cliente(lambda r: httpx.Response(503))
    with pytest.raises(LLMIndisponivel):
        _transmitir(cliente)


def test_transmitir_levanta_quando_erro_de_conexao_em_todos():
    def manipulador(requisicao):
        raise httpx.ConnectError("sem rede")

    with pytest.raises(LLMIndisponivel):
        _transmitir(_cliente(manipulador))


def test_transmitir_aceita_resposta_sem_quebra_de_linha_final():
    corpo = 'data: {"choices":[{"delta":{"content":"fim"}}]}'
    cliente = _cliente(lambda r: httpx.Response(200, content=corpo.encode()))
    assert _transmitir(cliente) == ["fim"]


def test_ler_sse_extrai_apenas_conteudo_de_texto():
    async def rodar():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200,
                    content=(
                        'data: {"choices":[{"delta":{"role":"assistant"}}]}\n'
                        'data: {"choices":[{"delta":{"content":""}}]}\n'
                        'data: {"choices":[{"delta":{"content":"x"}}]}\n'
                        'data: {"choices":[{"delta":null}]}\n'
                    ).encode(),
                )
            )
        ) as http:
            resposta = await http.get("https://x.org")
            return await _coletar(_ler_sse(resposta))

    assert asyncio.run(rodar()) == ["x"]


def _filtrar(*pedacos):
    return asyncio.run(_coletar(_sem_pensamento(_gerar(*pedacos))))


def test_sem_pensamento_remove_bloco_e_espaco_seguinte():
    assert _filtrar("<think>a</think>  \n  Texto") == ["Texto"]


def test_sem_pensamento_passa_pedacos_seguintes_sem_alterar():
    assert _filtrar("<think>a</think>Ini", " meio", " fim") == ["Ini", " meio", " fim"]


def test_sem_pensamento_tag_partida_letra_por_letra():
    pedacos = list("<think>pensando</think>Ok")
    assert "".join(_filtrar(*pedacos)) == "Ok"


def test_sem_pensamento_tag_de_fechamento_partida():
    assert "".join(_filtrar("<think>a<", "/", "think", ">Ok")) == "Ok"


def test_sem_pensamento_texto_normal_passa_intacto():
    assert _filtrar("Olá", " mundo") == ["Olá", " mundo"]


def test_sem_pensamento_ignora_espaco_inicial_antes_da_tag():
    assert "".join(_filtrar("  <think>a</think>Ok")) == "Ok"


def test_sem_pensamento_menor_que_que_nao_e_think_passa_intacto():
    assert "".join(_filtrar("<", "b>x")) == "<b>x"
    assert "".join(_filtrar("<thin", "g>x")) == "<thing>x"


def test_sem_pensamento_menor_que_isolado_no_fim_do_fluxo_nao_se_perde():
    assert "".join(_filtrar("<")) == "<"
    assert "".join(_filtrar("<thi")) == "<thi"


def test_sem_pensamento_tag_think_so_nao_e_removida_no_meio_do_texto():
    assert "".join(_filtrar("Antes <think>x</think> depois")) == "Antes <think>x</think> depois"


def test_sem_pensamento_fluxo_vazio_devolve_vazio():
    assert _filtrar() == []


def test_sem_pensamento_bloco_sem_fechamento_nao_vaza_o_raciocinio():
    assert "".join(_filtrar("<think>raciocinio sem fim")) == ""


def test_sem_pensamento_resposta_vazia_apos_bloco():
    assert _filtrar("<think>a</think>") == []


def test_sem_pensamento_descarta_pedacos_so_de_espaco_logo_apos_o_bloco():
    assert _filtrar("<think>a</think>", "\n", "\n", "Ok", " fim") == ["Ok", " fim"]
