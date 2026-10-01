FROM python:3.12-slim
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
ENV PYTHONPATH=/srv/backend \
    OSOKAI_HOST=0.0.0.0 \
    OSOKAI_PORT=8765 \
    OSOKAI_DATA_DIR=/data \
    OSOKAI_WS_DIR=/data/workspace
VOLUME ["/data"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,json; d=json.load(urllib.request.urlopen('http://127.0.0.1:8765/ready', timeout=4)); assert d.get('ok') is True, d"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
