"""Versiona treino, métricas e artefato de modelo em JSON, no git.

Substitui o .joblib solto em disco sem metadata associada: cada treino
produz um card em `modelos/cards/<nome>.json` com hash de integridade,
métricas (incluindo cross-source, para detectar viés de fonte) e o gate de
aprovação que decide se o modelo pode ser promovido a produção.
"""

import hashlib
import json
import math
from pathlib import Path


def calcular_hash_artefato(caminho: Path) -> str:
    """SHA-256 do conteúdo do artefato do modelo (arquivo ou diretório)."""
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
    """Monta o dicionário do model card a partir dos dados de um treino."""
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
    """Serializa o model card em disco, formatado para diff legível."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(card, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def carregar_card(caminho: Path) -> dict:
    """Carrega um model card salvo por `salvar_card`."""
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def aprovar_gate(card: dict) -> bool:
    """Decide se o modelo pode ser promovido a produção.

    Duas condições: o F1 same-source precisa atingir o mínimo configurado, e a
    queda do F1 para o F1 cross-source (quando calculado) não pode exceder o
    limiar — essa segunda condição é o que detecta viés de fonte: um modelo
    que decorou o portal de origem tem F1 alto na mesma fonte e baixo na
    fonte oposta. Métricas cross-source ausentes (None) não reprovam o gate
    por omissão -- só avalia a condição quando o dado existe.
    """
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
    """Confere que o artefato em disco corresponde ao model card de produção.

    Usado por `app.py` antes de carregar o modelo: evita servir silenciosamente
    um modelo desatualizado (card trocado sem retreinar) ou corrompido (hash
    não bate). Retorna (True, "") em sucesso, (False, motivo) em falha.
    """
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
