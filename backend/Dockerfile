FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

RUN mkdir -p /app/data

RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

CMD ["sh", "./start.sh"]
