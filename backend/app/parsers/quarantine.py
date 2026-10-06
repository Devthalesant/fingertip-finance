"""Quarentena: o arquivo enviado é lido num processo separado (ADR 0004, camada 3).

Protege até contra um bug do openpyxl que ninguém conhece ainda: se a leitura travar,
inchar ou derrubar o processo, só a "sala" separada cai; a API responde "arquivo
inválido" e segue de pé. O raio-x (xlsx_guard) roda antes, aqui mesmo, porque só lê o
índice do zip.

Os bytes vão e as linhas voltam por um cano (Pipe), sem passar pelo disco. A volta é
JSON com o texto das células, nunca pickle: se um arquivo dominasse o processo filho, um
pickle envenenado executaria código na API. A API confere o texto de novo
(`rows_from_payloads`) e recalcula os hashes. O teto de memória usa `resource.setrlimit`,
que só é confiável no Linux (servidor e CI); no macOS vale só o prazo.
"""

import json
import multiprocessing
import sys
from collections.abc import Callable
from multiprocessing.connection import Connection

from app.parsers.b3_movimentacao import (
    MovementRow,
    parse_movement_statement,
    rows_from_payloads,
)
from app.parsers.xlsx_guard import inspect_xlsx

TIMEOUT_SECONDS = 10
MEMORY_BYTES = 512 * 1024 * 1024
# Teto da resposta do filho: 50 mil linhas de texto curto cabem com folga.
MAX_RESULT_BYTES = 64 * 1024 * 1024
# spawn: o filho começa limpo, sem herdar conexões do banco nem o estado da API.
_context = multiprocessing.get_context("spawn")

Parser = Callable[[bytes], list[MovementRow]]
_CHILD_REASONS = {"invalid", "memory"}

MESSAGE = "O arquivo não pôde ser lido como extrato de movimentação da B3."


class QuarantineFailed(ValueError):
    """Leitura recusada. `reason` e `detail` vão para o log; a mensagem, para a tela."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(MESSAGE)
        self.reason = reason  # invalid, timeout, memory, crashed
        self.detail = detail  # nunca conteúdo do arquivo


def parse_in_quarantine(
    data: bytes,
    parse: Parser = parse_movement_statement,
    timeout: float = TIMEOUT_SECONDS,
    memory_bytes: int = MEMORY_BYTES,
) -> list[MovementRow]:
    inspect_xlsx(data)
    receiver, sender = _context.Pipe(duplex=False)
    process = _context.Process(
        target=_worker, args=(parse, data, sender, memory_bytes), daemon=True
    )
    process.start()
    sender.close()  # no pai, só o filho escreve; fechar aqui faz o recv ver o fim
    try:
        if not receiver.poll(timeout):
            raise QuarantineFailed("timeout", f"mais de {timeout}s")
        try:
            message = receiver.recv_bytes(MAX_RESULT_BYTES)
        except EOFError:
            process.join(1)
            raise QuarantineFailed("crashed", f"código de saída {process.exitcode}") from None
        except OSError:
            raise QuarantineFailed("crashed", "resposta grande demais") from None
    finally:
        receiver.close()
        if process.is_alive():
            process.kill()
        process.join(1)
    # Tudo o que vem do filho é tratado como não confiável, até o formato da resposta.
    try:
        status, payload = json.loads(message)
        if status == "ok":
            return rows_from_payloads((number, cells) for number, cells in payload)
    except Exception as exc:  # resposta fora do formato = leitura inválida
        raise QuarantineFailed("invalid", type(exc).__name__) from None
    reason = status if status in _CHILD_REASONS else "invalid"
    detail = payload if isinstance(payload, str) else ""
    raise QuarantineFailed(reason, detail[:100])


def _worker(parse: Parser, data: bytes, sender: Connection, memory_bytes: int) -> None:
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    try:
        rows = parse(data)
        outcome = ["ok", [[r.row_number, r.payload] for r in rows]]
    except MemoryError:
        outcome = ["memory", "teto de memória"]
    except Exception as exc:  # qualquer falha de leitura vira "inválido"
        # Só o tipo do erro: a mensagem pode trazer células da planilha.
        outcome = ["invalid", type(exc).__name__]
    try:
        sender.send_bytes(json.dumps(outcome).encode())
    finally:
        sender.close()
