FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y tesseract-ocr libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/adharaai
COPY adharaai/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY adharaai/ ./

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
