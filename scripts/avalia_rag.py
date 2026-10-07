import argparse
import asyncio
import json
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake import rag  # noqa: E402
from verdade_ou_fake.api import criar_servico  # noqa: E402
from verdade_ou_fake.base import construir  # noqa: E402
from verdade_ou_fake.config import Config, carregar_env  # noqa: E402

CONJUNTO = RAIZ / "dados" / "avaliacao" / "alegacoes.json"
SAIDA = RAIZ / "dados" / "avaliacao" / "resultado_rag.json"
AFIRMATIVOS = {"APOIADA", "CONTESTADA", "EXAGERADA"}


async def avaliar_caso(servico: rag.Servico, caso: dict) -> dict:
    inicio = time.monotonic()
    primeiro_texto = None
    veredito = {}
    fontes = []
    fim = {}
    async for evento in rag.analisar(servico, caso["alegacao"]):
        if evento["tipo"] == "texto" and primeiro_texto is None:
            primeiro_texto = time.monotonic() - inicio
        elif evento["tipo"] == "veredito":
            veredito = evento
        elif evento["tipo"] == "fontes":
            fontes = evento["fontes"]
        elif evento["tipo"] == "fim":
            fim = evento
    return {
        "alegacao": caso["alegacao"],
        "esperado": caso["esperado"],
        "obtido": veredito.get("codigo"),
        "confianca": veredito.get("confianca"),
        "acertou": veredito.get("codigo") in caso["esperado"],
        "fontes": len(fontes),
        "citadas": len(fim.get("citadas", [])),
        "modelo": fim.get("modelo"),
        "aviso": fim.get("aviso"),
        "primeiro_texto_s": round(primeiro_texto, 2) if primeiro_texto is not None else None,
        "total_s": round(time.monotonic() - inicio, 2),
    }


def resumir(casos: list[dict]) -> dict:
    afirmativos = [c for c in casos if c["obtido"] in AFIRMATIVOS]
    tempos = sorted(c["total_s"] for c in casos)
    primeiros = sorted(c["primeiro_texto_s"] for c in casos if c["primeiro_texto_s"] is not None)
    return {
        "casos": len(casos),
        "acuracia_do_veredito": round(sum(c["acertou"] for c in casos) / len(casos), 3),
        "afirmativos_com_citacao_valida": round(
            sum(c["citadas"] > 0 for c in afirmativos) / len(afirmativos), 3
        )
        if afirmativos
        else None,
        "casos_com_fontes": sum(c["fontes"] > 0 for c in casos),
        "respostas_degradadas": sum(bool(c["aviso"] and "degradado" in c["aviso"]) for c in casos),
        "total_s_mediana": round(statistics.median(tempos), 2),
        "total_s_p95": tempos[min(len(tempos) - 1, int(0.95 * len(tempos)))],
        "primeiro_texto_s_mediana": round(statistics.median(primeiros), 2) if primeiros else None,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int)
    parser.add_argument("--pausa", type=float, default=2.0)
    args = parser.parse_args()

    carregar_env()
    casos = json.loads(CONJUNTO.read_text(encoding="utf-8"))[: args.limite]
    with tempfile.TemporaryDirectory() as pasta:
        config = Config(banco=Path(pasta) / "avaliacao.db")
        servico = criar_servico(config)
        construir(servico.banco, servico.embutir, config.base_jsonl)
        if servico.llm is None:
            sys.exit("Configure LLM_API_KEY: sem LLM não há veredito para avaliar.")

        resultados = []
        for caso in casos:
            resultado = await avaliar_caso(servico, caso)
            resultados.append(resultado)
            marca = "ok " if resultado["acertou"] else "ERRO"
            print(
                f"{marca} {resultado['obtido']:<16} {resultado['total_s']:>5.1f}s "
                f"{resultado['citadas']} cit. | {caso['alegacao']}",
                flush=True,
            )
            await asyncio.sleep(args.pausa)
        await servico.llm.fechar()

    relatorio = {
        "data": date.today().isoformat(),
        "modelos": config.llm_modelos,
        "base_sha256": servico.versao_base,
        "resumo": resumir(resultados),
        "casos": resultados,
    }
    SAIDA.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(relatorio["resumo"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
