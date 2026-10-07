from collections.abc import Callable
from pathlib import Path

from verdade_ou_fake.model_card import validar_modelo_para_producao

ARQUIVO_PESOS = "model.safetensors"


class ModeloIndisponivel(RuntimeError):
    pass


def _baixar_do_hub(**kwargs) -> str:
    from huggingface_hub import snapshot_download

    return snapshot_download(**kwargs)


def localizar_modelo(
    origem: str,
    revisao: str | None = None,
    baixar: Callable[..., str] = _baixar_do_hub,
) -> Path:
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
    except Exception as erro:
        raise ModeloIndisponivel(f"Falha ao baixar o modelo `{origem}` do Hub: {erro}") from erro


def preparar_modelo_de_producao(
    origem: str,
    caminho_card: Path,
    revisao: str | None = None,
    baixar: Callable[..., str] = _baixar_do_hub,
) -> Path:
    diretorio = localizar_modelo(origem, revisao=revisao, baixar=baixar)
    pesos = diretorio / ARQUIVO_PESOS
    if not pesos.exists():
        raise ModeloIndisponivel(f"Pesos `{ARQUIVO_PESOS}` ausentes em `{diretorio}`.")

    ok, motivo = validar_modelo_para_producao(caminho_card, pesos)
    if not ok:
        raise ModeloIndisponivel(motivo)
    return diretorio
