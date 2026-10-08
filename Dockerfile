FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/home/app/servico/src \
    HF_HOME=/home/app/cache/huggingface \
    FASTEMBED_CACHE_PATH=/home/app/cache/fastembed \
    VOF_BANCO=/home/app/banco/vof.db \
    PORT=7860

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /home/app/servico /home/app/banco /home/app/cache \
    && chown -R app:app /home/app
WORKDIR /home/app/servico

COPY requirements.txt .
RUN pip install -r requirements.txt

USER app
COPY --chown=app:app dados/base/ dados/base/
COPY --chown=app:app dados/vocabulario_seed.csv dados/
COPY --chown=app:app src/ src/
COPY --chown=app:app scripts/__init__.py scripts/constroi_base.py scripts/
RUN python scripts/constroi_base.py

COPY --chown=app:app scripts/atualiza_destaques.py scripts/
COPY --chown=app:app web/ web/
COPY --chown=app:app modelos/cards/ modelos/cards/

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/saude' % os.environ.get('PORT', '7860'), timeout=4)"

CMD ["sh", "-c", "exec uvicorn verdade_ou_fake.api:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
