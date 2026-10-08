import asyncio
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake import destaques  # noqa: E402
from verdade_ou_fake.api import criar_servico  # noqa: E402
from verdade_ou_fake.config import Config, carregar_env  # noqa: E402


async def main() -> None:
    carregar_env()
    servico = criar_servico(Config())
    if servico.llm is None:
        sys.exit("Configure LLM_API_KEY: os destaques precisam do LLM.")
    prontos = await destaques.atualizar(servico)
    for item in servico.banco.listar_destaques():
        print(f"{item['veredito']:<16} {item['origem']:<16} +{item['novos_artigos']} | {item['alegacao']}")
    print(f"{prontos} destaques prontos")
    await servico.llm.fechar()


if __name__ == "__main__":
    asyncio.run(main())
