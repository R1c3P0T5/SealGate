FROM python:3.11-slim
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download YuNet face detection model at build time
COPY scripts/download_models.py scripts/download_models.py
RUN python scripts/download_models.py

COPY . .

CMD ["python", "worker.py"]
