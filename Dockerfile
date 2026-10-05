# Imagem do app para produção (Hugging Face Spaces, SDK Docker, ou qualquer
# host de contêiner). Os pesos do BERTimbau NÃO entram na imagem: são baixados
# do Hugging Face Hub na inicialização (VOF_MODELO_RISCO).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/app/.cache/huggingface

# O Hugging Face Spaces executa o contêiner com o UID 1000.
RUN useradd --create-home --uid 1000 app
WORKDIR /home/app/servico

COPY requirements.txt .
RUN pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

USER app
COPY --chown=app src/ src/
# Baixa o modelo de NLI da Camada 2c no build, não na primeira requisição.
RUN python -c "import sys; sys.path.insert(0, 'src'); from verdade_ou_fake.suporte import carregar_modelo_nli; carregar_modelo_nli()"

COPY --chown=app app.py .
COPY --chown=app dados/vocabulario_seed.csv dados/
COPY --chown=app modelos/cards/ modelos/cards/

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=5m \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
