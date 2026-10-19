"""Client minimo per il server locale di LM Studio.

Legge una domanda dal terminale, la invia al modello configurato in .env
e stampa la risposta in streaming. Ogni domanda e' una richiesta indipendente.
Uscita con "esci" o Ctrl+C.
"""

import json
import os

import requests
from dotenv import load_dotenv

# --- Configurazione -------------------------------------------------------
load_dotenv(".env", override=False)
base_url = os.environ["LM_BASE_URL"].rstrip("/")
model = os.environ["LM_MODEL"]

# --- Messaggi -------------------------------------------------------------
SYSTEM = "Rispondi in italiano."


# --- Chiamata in streaming ------------------------------------------------
def invia(messages):
    """Invia i messaggi, stampa la risposta a frammenti e la restituisce intera."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 180,
        "reasoning_effort": "none",
        "stream": True,
    }
    testo = ""
    with requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        stream=True,
        timeout=(5, 120),
    ) as response:
        response.raise_for_status()
        for riga in response.iter_lines():
            riga = riga.decode("utf-8")
            if not riga.startswith("data: "):
                continue
            dati = riga[len("data: "):]
            if dati == "[DONE]":
                break
            delta = json.loads(dati)["choices"][0]["delta"]
            frammento = delta.get("content") or ""
            print(frammento, end="", flush=True)
            testo += frammento
    print()
    return testo


# --- Ciclo delle domande --------------------------------------------------
# Ogni domanda e' una richiesta indipendente: nessuna cronologia.
while True:
    try:
        domanda = input("Tu> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break
    if domanda.lower() == "esci":
        break
    if not domanda:
        continue

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": domanda},
    ]
    try:
        invia(messages)
    except requests.exceptions.Timeout:
        print("Attesa scaduta: controllare server, carico e tempi.")
    except requests.exceptions.ConnectionError:
        print("Connessione fallita: controllare server, URL e porta.")
    except requests.exceptions.HTTPError as e:
        print("Errore HTTP:", e.response.status_code, e.response.text)
