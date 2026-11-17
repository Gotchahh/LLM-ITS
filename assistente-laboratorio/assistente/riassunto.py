"""Riassunto della cronologia: dove tagliare, trascrizione dei messaggi, messaggi per il modello, prompt con riassunto.

Le istruzioni del riassunto sono un file di configurazione (vedi `config.leggi_riassunto`).
"""

import json

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage

INTRODUZIONE_RIASSUNTO = "Riassunto della conversazione precedente (i turni più vecchi):"


def punto_di_taglio(messaggi: list[AnyMessage], turni: int) -> int:
    """Indice del primo messaggio da conservare: la domanda che apre il turno `turni` posizioni prima di quello in
    corso. 0 se non c'è nulla da tagliare. Il taglio cade sempre prima di una domanda dell'utente, quindi una
    richiesta di strumento e il suo risultato (sempre nello stesso turno) non vengono mai separati."""
    domande = [i for i, messaggio in enumerate(messaggi) if isinstance(messaggio, HumanMessage)]
    if len(domande) <= turni:
        return 0
    return domande[-(turni + 1)]


def trascrivi(messaggi: list[AnyMessage]) -> str:
    """Trascrizione testuale, una riga per messaggio (e per richiesta di strumento), per il modello senza strumenti."""
    righe = []
    for messaggio in messaggi:
        if isinstance(messaggio, HumanMessage):
            righe.append(f"Utente: {messaggio.text}")
        elif isinstance(messaggio, ToolMessage):
            righe.append(f"Strumento {messaggio.name}: {messaggio.text}")
        elif isinstance(messaggio, AIMessage):
            if messaggio.text.strip():
                righe.append(f"Assistente: {messaggio.text}")
            for richiesta in messaggio.tool_calls:
                argomenti = json.dumps(richiesta["args"], ensure_ascii=False)
                righe.append(f"Assistente chiede lo strumento {richiesta['name']} {argomenti}")
    return "\n".join(righe)


def messaggi_per_il_riassunto(istruzioni: str, precedente: str, trascrizione: str) -> list[AnyMessage]:
    """Prompt del riassunto: le istruzioni e un solo messaggio con il riassunto precedente e la trascrizione."""
    return [
        SystemMessage(istruzioni),
        HumanMessage(
            f"Riassunto precedente:\n{precedente or 'nessuno'}\n\nConversazione da riassumere:\n{trascrizione}"
        ),
    ]


def messaggi_di_sistema(prompt: str, riassunto: str) -> list[SystemMessage]:
    """Il prompt di sistema e, se c'è, il riassunto in un secondo messaggio di sistema.

    Per l'agente: con tutti gli strumenti associati gemma ignorava il riassunto dentro il prompt (in coda o in testa)
    e lo usava in un messaggio separato (prova del 17/11/2026).
    """
    if not riassunto:
        return [SystemMessage(prompt)]
    return [SystemMessage(prompt), SystemMessage(f"{INTRODUZIONE_RIASSUNTO}\n{riassunto}")]


def con_riassunto(prompt: str, riassunto: str) -> str:
    """Il prompt di sistema con il riassunto in coda (per il router, che ha un prompt breve); invariato se non c'è."""
    if not riassunto:
        return prompt
    return f"{prompt}\n\n{INTRODUZIONE_RIASSUNTO}\n{riassunto}"
