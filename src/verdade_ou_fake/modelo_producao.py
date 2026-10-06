"""Localiza o classificador de risco servido pelo app e confere o model card.

Os pesos do BERTimbau (~420 MB) não vão para o git. Em desenvolvimento eles
ficam em `modelos/bertimbau/`; em produção são baixados de um repositório do
Hugging Face Hub. Nos dois casos o app só serve o modelo se o card versionado
em `modelos/cards/bertimbau.json` estiver em `status: producao` e o hash dos
pesos bater com o registrado: o card no git é o registro do que pode ir ao ar,
o Hub é só o armazenamento.
"""

from collections.abc import Callable
from pathlib import Path

from verdade_ou_fake.model_card import validar_modelo_para_producao

# O card registra o hash só dos pesos: é o arquivo que muda a cada treino, e
# não depende de arquivos auxiliares que o Hub acrescenta (README, .gitattributes).
ARQUIVO_PESOS = "model.safetensors"


class ModeloIndisponivel(RuntimeError):
    """O modelo não pode ser servido; a mensagem explica o motivo."""


def _baixar_do_hub(**kwargs) -> str:
    from huggingface_hub import snapshot_download

    return snapshot_download(**kwargs)


def localizar_modelo(
    origem: str,
    revisao: str | None = None,
    baixar: Callable[..., str] = _baixar_do_hub,
) -> Path:
    """Devolve o diretório local do modelo.

    `origem` é um diretório local ou um id de repositório do Hub
    (`usuario/nome`). Um id do Hub é baixado para o cache do
    huggingface_hub — downloads seguintes reutilizam o cache.
    """
    caminho = Path(origem)
    if caminho.is_dir():
        return caminho

    if origem.count("/") != 1 or origem.startswith((".", "/")):
        raise ModeloIndisponivel(
            f"Modelo não encontrado em `{origem}`. Rode `python scripts/treina_bert.py` "
            "ou aponte VOF_MODELO_RISCO para um repositório do Hugging Face Hub."
        )

    try:
        return Path(
            baixar(repo_id=origem, revision=revisao, ignore_patterns=["_checkpoints/*"])
        )
    except Exception as erro:  # rede, repo privado sem token, repo inexistente...
        raise ModeloIndisponivel(f"Falha ao baixar o modelo `{origem}` do Hub: {erro}") from erro


def preparar_modelo_de_producao(
    origem: str,
    caminho_card: Path,
    revisao: str | None = None,
    baixar: Callable[..., str] = _baixar_do_hub,
) -> Path:
    """Localiza o modelo e só o devolve se o model card autorizar servi-lo."""
    diretorio = localizar_modelo(origem, revisao=revisao, baixar=baixar)
    pesos = diretorio / ARQUIVO_PESOS
    if not pesos.exists():
        raise ModeloIndisponivel(f"Pesos `{ARQUIVO_PESOS}` ausentes em `{diretorio}`.")

    ok, motivo = validar_modelo_para_producao(caminho_card, pesos)
    if not ok:
        raise ModeloIndisponivel(motivo)
    return diretorio
