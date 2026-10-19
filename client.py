"""Client minimo per il server locale di LM Studio.

Scheletro da completare con Claude Code (slide 19-22):
configurazione, messaggi, payload e chiamata HTTP.
Import e gestione degli errori sono gia' presenti: conservarli.
"""

import os

import requests
from dotenv import load_dotenv

# --- Configurazione -------------------------------------------------------
load_dotenv(".env", override=False)
base_url = os.environ["LM_BASE_URL"].rstrip("/")
model = os.environ["LM_MODEL"]

# --- Messaggi -------------------------------------------------------------
SYSTEM = "Rispondi in italiano."

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

    # --- Payload ----------------------------------------------------------
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": domanda},
        ],
        "temperature": 0.2,
        "max_tokens": 180,
        "reasoning_effort": "none",
        "stream": False,
    }

    # --- Chiamata ---------------------------------------------------------
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            timeout=(5, 120),
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        print(text)
    except requests.exceptions.Timeout:
        print("Attesa scaduta: controllare server, carico e tempi.")
    except requests.exceptions.ConnectionError:
        print("Connessione fallita: controllare server, URL e porta.")
    except requests.exceptions.HTTPError:
        print("Errore HTTP:", response.status_code, response.text)
