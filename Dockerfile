FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# Bash supervises process groups; setsid comes from util-linux.
RUN apt-get update && apt-get install -y --no-install-recommends bash util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY api/requirements.txt /app/api/requirements.txt
COPY web/requirements.txt /app/web/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt -r web/requirements.txt
COPY api/ /app/api/
COPY web/ /app/web/
COPY start-render.sh /app/start-render.sh
RUN chmod +x /app/start-render.sh \
    && useradd --create-home fulbacho && chown -R fulbacho:fulbacho /app
USER fulbacho
ENV ENVIRONMENT=production
CMD ["/app/start-render.sh"]
