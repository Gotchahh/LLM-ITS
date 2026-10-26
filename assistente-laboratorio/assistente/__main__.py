"""Punto di ingresso: `python -m assistente`."""

from assistente.cli import esegui_chat
from assistente.grafo import costruisci_grafo_fisso


def main() -> None:
    esegui_chat(costruisci_grafo_fisso())


if __name__ == "__main__":
    main()
