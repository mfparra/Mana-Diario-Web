"""Laço do agendador. Por enquanto só registra em log (Fase 0)."""

import logging
import signal
import threading

log = logging.getLogger("mana.agendador")


def executar(intervalo_s: int = 3600) -> None:
    parar = threading.Event()
    for sinal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sinal, lambda *_: parar.set())
    log.info("Agendador iniciado (laço vazio).")
    while not parar.wait(intervalo_s):
        log.info("Agendador vivo.")
    log.info("Agendador encerrado.")
