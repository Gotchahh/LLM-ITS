"""Punto di ingresso: `python -m assistente`."""

import os
import sys
from pathlib import Path

from assistente.calendario import crea_strumenti_calendario
from assistente.cli import crea_indicatore_attesa, esegui_chat, prepara_terminale
from assistente.client_mcp import ErroreMCP, carica_strumenti_mcp
from assistente.config import (
    ErroreConfigurazione,
    carica_configurazione,
    configura_log,
    leggi_file_env,
)
from assistente.convertitore import crea_strumento_convertitore
from assistente.grafo import costruisci_grafo
from assistente.modello import (
    ErroreServer,
    crea_modello,
    leggi_modelli_disponibili,
    verifica_modello,
)
from assistente.strumenti import crea_strumento_orologio


def main() -> int:
    """Legge la configurazione, controlla il server e il modello, carica gli strumenti MCP, poi avvia la chat.

    Restituisce 1 se la configurazione non è valida, LM Studio non è raggiungibile
    o il server MCP della calcolatrice non parte.
    """
    prepara_terminale(sys.stdin, sys.stdout, sys.stderr)
    try:
        ambiente = {**leggi_file_env(Path(".env")), **os.environ}
        config = carica_configurazione(ambiente)
        configura_log(config.livello_log)
        verifica_modello(config.modello, leggi_modelli_disponibili(config.base_url))
        strumenti_mcp = carica_strumenti_mcp()
    except (ErroreConfigurazione, ErroreServer, ErroreMCP) as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1
    strumenti = [
        crea_strumento_orologio(config.fuso),
        *crea_strumenti_calendario(config.fuso),
        crea_strumento_convertitore(),
        *strumenti_mcp,
    ]
    grafo = costruisci_grafo(crea_modello(config), strumenti)
    esegui_chat(
        grafo,
        config.base_url,
        attesa=crea_indicatore_attesa(sys.stdin, sys.stdout),
        livello_log=config.livello_log,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
