FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

# Pillow card rendering can use the bundled Myanmar font with complex shaping.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libraqm0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 botuser

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=botuser:botuser . .

USER botuser

EXPOSE 7860

# Liveness only: this does not call Telegram or mutate the database.
HEALTHCHECK --interval=60s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '7860') + '/', timeout=4).close()"

CMD ["python", "bot.py"]
