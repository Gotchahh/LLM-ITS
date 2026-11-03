FROM python:3.14.7-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY assistente/ assistente/
COPY calcolatrice_mcp/ calcolatrice_mcp/

CMD ["python", "-m", "assistente"]
