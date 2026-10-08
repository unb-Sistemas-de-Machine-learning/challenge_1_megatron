#!/usr/bin/env bash
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
ROTULO="${ROTULO:?defina ROTULO, o prefixo do endereço público (ex.: verdade-ou-fake-megatron)}"
GRUPO="${GRUPO:-verdade-ou-fake}"
LOCAL="${LOCAL:-brazilsouth}"
VM="${VM:-vof}"
TAMANHO="${TAMANHO:-Standard_B1s}"
USUARIO=vof
DOMINIO="${ROTULO}.${LOCAL}.cloudapp.azure.com"
IMAGEM=verdade-ou-fake:rag
CHAVE="${CHAVE:-$HOME/.ssh/vof_azure}"
OPCOES_SSH="-i ${CHAVE} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
SSH="ssh ${OPCOES_SSH} ${USUARIO}@${DOMINIO}"

test -f "${RAIZ}/.env" || { echo "Crie o .env com LLM_API_KEY antes de publicar."; exit 1; }

test -f "$CHAVE" || ssh-keygen -q -t ed25519 -N "" -C "deploy verdade-ou-fake" -f "$CHAVE"

az group create --name "$GRUPO" --location "$LOCAL" --output none
if ! az vm show --resource-group "$GRUPO" --name "$VM" --output none 2>/dev/null; then
  az vm create --resource-group "$GRUPO" --name "$VM" --image Ubuntu2204 --size "$TAMANHO" \
    --admin-username "$USUARIO" --ssh-key-values "${CHAVE}.pub" --public-ip-sku Standard \
    --public-ip-address-dns-name "$ROTULO" --custom-data "${RAIZ}/deploy/cloud-init.yml" --output none
  az vm open-port --resource-group "$GRUPO" --name "$VM" --port 80,443 --priority 900 --output none
fi

until $SSH "docker compose version" >/dev/null 2>&1; do sleep 10; done

docker build -t "$IMAGEM" "$RAIZ"
docker save "$IMAGEM" | gzip | $SSH "gunzip | docker load"

$SSH "mkdir -p servico"
scp ${OPCOES_SSH} "${RAIZ}/deploy/docker-compose.yml" "${RAIZ}/deploy/Caddyfile" "${USUARIO}@${DOMINIO}:servico/"
grep -v '^#' "${RAIZ}/.env" | grep -v '^$' | $SSH "cat > servico/.env && echo DOMINIO=${DOMINIO} >> servico/.env && chmod 600 servico/.env"
$SSH "cd servico && docker compose up -d --remove-orphans && docker image prune -f >/dev/null"

echo "Publicado em https://${DOMINIO}"
