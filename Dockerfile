FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app code + prebuilt synthetic databases
COPY shared/ ./shared/
COPY servers/ ./servers/
COPY data/ ./data/
COPY host.py .

# remove any local .env that may have been copied (keys come from ACA secrets)
RUN rm -f ./data/.env

EXPOSE 8000

# MCP_SERVER (equity|credit|portfolio) is set per Container App at deploy time.
CMD ["python", "host.py"]
