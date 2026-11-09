FROM python:3.14.7-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY assistente/ assistente/
COPY calcolatrice_mcp/ calcolatrice_mcp/
COPY note_api/ note_api/

CMD ["python", "-m", "assistente"]
