"""Punto di ingresso: `python -m assistente`."""

import os
import sys
from pathlib import Path

from assistente.cli import esegui_chat
from assistente.config import (
    ErroreConfigurazione,
    carica_configurazione,
    configura_log,
    leggi_file_env,
)
from assistente.grafo import costruisci_grafo
from assistente.modello import (
    ErroreServer,
    crea_modello,
    leggi_modelli_disponibili,
    verifica_modello,
)


def main() -> int:
    """Legge la configurazione, controlla il server e il modello, poi avvia la chat.

    Restituisce 1 se la configurazione non è valida o LM Studio non è raggiungibile.
    """
    ambiente = {**leggi_file_env(Path(".env")), **os.environ}
    try:
        config = carica_configurazione(ambiente)
        configura_log(config.livello_log)
        verifica_modello(config.modello, leggi_modelli_disponibili(config.base_url))
    except (ErroreConfigurazione, ErroreServer) as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1
    grafo = costruisci_grafo(crea_modello(config), strumenti=[])
    esegui_chat(grafo, config.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
