import hashlib
import json
import math
from pathlib import Path


def calcular_hash_artefato(caminho: Path) -> str:
    caminho = Path(caminho)
    hash_ = hashlib.sha256()
    if caminho.is_dir():
        for arquivo in sorted(caminho.rglob("*")):
            if arquivo.is_file():
                hash_.update(arquivo.relative_to(caminho).as_posix().encode("utf-8"))
                hash_.update(arquivo.read_bytes())
    else:
        hash_.update(caminho.read_bytes())
    return hash_.hexdigest()


def montar_card(
    nome: str,
    tipo: str,
    commit: str,
    dados: dict,
    metricas: dict,
    limiar_aprovacao: dict,
    artefato_hash: str,
    treinado_em: str,
    treinado_por: str,
    status: str = "staging",
) -> dict:
    return {
        "nome": nome,
        "versao": f"{treinado_em[:10]}-{commit[:7]}",
        "tipo": tipo,
        "commit": commit,
        "dados": dados,
        "metricas": metricas,
        "limiar_aprovacao": limiar_aprovacao,
        "status": status,
        "artefato_hash_sha256": artefato_hash,
        "treinado_em": treinado_em,
        "treinado_por": treinado_por,
    }


def salvar_card(card: dict, caminho: Path) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(card, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def carregar_card(caminho: Path) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def aprovar_gate(card: dict) -> bool:
    metricas = card["metricas"]
    limiar = card["limiar_aprovacao"]

    if metricas["f1_macro_same_source"] < limiar["f1_macro_same_source_minimo"]:
        return False

    quedas = [
        metricas["f1_macro_same_source"] - valor_cross
        for chave, valor_cross in metricas.items()
        if chave.startswith("f1_macro_cross_source") and valor_cross is not None
    ]
    queda_maxima = limiar["queda_maxima_cross_source"]
    if any(
        queda > queda_maxima and not math.isclose(queda, queda_maxima, abs_tol=1e-9)
        for queda in quedas
    ):
        return False

    return True


def validar_modelo_para_producao(caminho_card: Path, caminho_artefato: Path) -> tuple[bool, str]:
    caminho_card = Path(caminho_card)
    if not caminho_card.exists():
        return False, f"Model card não encontrado em {caminho_card}."

    card = carregar_card(caminho_card)

    if card["status"] != "producao":
        return False, f"Model card tem status '{card['status']}', esperado 'producao'."

    hash_atual = calcular_hash_artefato(caminho_artefato)
    if hash_atual != card["artefato_hash_sha256"]:
        return False, (
            "Hash do artefato em disco não corresponde ao registrado no model card — "
            "o modelo pode ter sido retreinado sem atualizar o card, ou está corrompido."
        )

    return True, ""
