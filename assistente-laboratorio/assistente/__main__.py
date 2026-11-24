"""Punto di ingresso: `python -m assistente`."""

import logging
import os
import sys
from pathlib import Path

from assistente.calendario import crea_strumenti_calendario
from assistente.cli import crea_indicatore_attesa, esegui_chat, prepara_terminale
from assistente.client_mcp import (
    ErroreMCP,
    carica_strumenti_mcp,
    leggi_elenco_prompt,
    leggi_preferenze_mcp,
    richiedi_prompt,
)
from assistente.config import (
    ErroreConfigurazione,
    carica_configurazione,
    configura_log,
    leggi_ambito,
    leggi_revisore,
    leggi_riassunto,
    leggi_file_env,
)
from assistente.convertitore import crea_strumento_convertitore
from assistente.grafo import costruisci_grafo
from assistente.modello import (
    ErroreServer,
    crea_modello,
    crea_modello_riassunto,
    crea_modello_router,
    leggi_modelli_disponibili,
    verifica_modello,
)
from assistente.note import crea_strumenti_note, servizio_raggiungibile
from assistente.preferenze import blocco_preferenze, carica_preferenze
from assistente.prompt import carica_prompt
from assistente.strumenti import crea_strumento_orologio

logger = logging.getLogger("assistente")


def main() -> int:
    """Legge la configurazione, controlla il server e il modello, carica gli strumenti MCP, legge le preferenze
    dell'utente dalla resource MCP e l'elenco dei prompt MCP, poi avvia la chat.

    Restituisce 1 se la configurazione non è valida, LM Studio non è raggiungibile
    o un server MCP degli strumenti non parte. Preferenze non disponibili: valori predefiniti e WARNING, la chat parte.
    Elenco dei prompt non disponibile: WARNING, la chat parte con i comandi /prompt disattivati.
    """
    prepara_terminale(sys.stdin, sys.stdout, sys.stderr)
    try:
        ambiente = {**leggi_file_env(Path(".env")), **os.environ}
        config = carica_configurazione(ambiente)
        configura_log(config.livello_log)
        ambito = leggi_ambito(config.ambito_file)
        revisore = leggi_revisore(config.revisore_file)
        riassunto = leggi_riassunto(config.riassunto_file)
        verifica_modello(config.modello, leggi_modelli_disponibili(config.base_url))
        strumenti_mcp = carica_strumenti_mcp()
    except (ErroreConfigurazione, ErroreServer, ErroreMCP) as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1
    preferenze = carica_preferenze(leggi_preferenze_mcp, config.fuso)
    elenco_prompt = carica_prompt(leggi_elenco_prompt)
    if not servizio_raggiungibile(config.note_url):
        logger.warning(
            "servizio note non raggiungibile a %s: gli strumenti delle note risponderanno con un errore",
            config.note_url,
        )
    strumenti = [
        crea_strumento_orologio(config.fuso),
        *crea_strumenti_calendario(config.fuso),
        crea_strumento_convertitore(),
        *crea_strumenti_note(config.note_url, config.fuso),
        *strumenti_mcp,
    ]
    grafo = costruisci_grafo(
        crea_modello(config), strumenti, ambito, crea_modello_router(config), revisore, config.revisioni_max,
        riassunto_istruzioni=riassunto,
        riassunto_soglia=config.riassunto_soglia,
        riassunto_turni=config.riassunto_turni,
        modello_riassunto=crea_modello_riassunto(config),
        preferenze=blocco_preferenze(preferenze),
    )
    esegui_chat(
        grafo,
        config.base_url,
        attesa=crea_indicatore_attesa(sys.stdin, sys.stdout),
        livello_log=config.livello_log,
        elenco_prompt=elenco_prompt,
        richiedi_prompt=richiedi_prompt,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
