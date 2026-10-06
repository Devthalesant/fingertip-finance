"""Quarentena: o leitor roda num processo separado, com prazo e teto de memória (ADR 0004).

As funções "sabotadas" ficam no nível do módulo porque o processo filho as importa pelo
nome (não dá para mandar uma função criada dentro do teste).
"""

import sys
import time
from pathlib import Path

import pytest

from app.parsers.b3_movimentacao import parse_movement_statement
from app.parsers.quarantine import QuarantineFailed, parse_in_quarantine
from app.parsers.xlsx_guard import UnsafeFile
from sample_data.b3_format import write_movement_statement
from sample_data.scenario import movement_rows


def sleeps_forever(data: bytes) -> list:
    time.sleep(60)
    return []


def eats_memory(data: bytes) -> list:
    hog = []
    while True:
        hog.append(bytearray(50 * 1024 * 1024))


def breaks(data: bytes) -> list:
    raise ValueError("Linha 7 do extrato inválida: número esperado, veio 'DADO DO USUÁRIO'")


def forges_hashes(data: bytes) -> list:
    from dataclasses import replace

    return [
        replace(r, row_hash="forjado", content_hash="forjado")
        for r in parse_movement_statement(data)
    ]


class Forged:
    """Linha forjada: número da linha e células fora do formato combinado."""

    row_number = 2
    payload = {"Entrada/Saída": ["lista", "no", "lugar", "de", "texto"]}


def returns_garbage(data: bytes) -> list:
    return [Forged()]


def dies(data: bytes) -> list:
    import os

    os._exit(3)


@pytest.fixture(scope="module")
def statement(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    path = tmp_path_factory.mktemp("q") / "movimentacao.xlsx"
    return write_movement_statement(movement_rows(), path).read_bytes()


def test_same_rows_as_reading_directly(statement: bytes) -> None:
    assert parse_in_quarantine(statement) == parse_movement_statement(statement)


def test_hashes_are_recomputed_outside_the_quarantine(statement: bytes) -> None:
    # Nada calculado lá dentro é aceito pronto: só o texto das células atravessa.
    assert parse_in_quarantine(statement, parse=forges_hashes) == parse_movement_statement(
        statement
    )


def test_unsafe_file_is_refused_before_the_quarantine() -> None:
    # O raio-x roda antes: arquivo ruim nem chega a abrir um processo.
    with pytest.raises(UnsafeFile):
        parse_in_quarantine(b"nada", parse=sleeps_forever)


def test_slow_reading_is_killed(statement: bytes) -> None:
    started = time.monotonic()
    with pytest.raises(QuarantineFailed) as caught:
        parse_in_quarantine(statement, parse=sleeps_forever, timeout=1)
    assert caught.value.reason == "timeout"
    assert time.monotonic() - started < 10


@pytest.mark.skipif(sys.platform != "linux", reason="teto de memória só vale no Linux")
def test_memory_hog_is_stopped(statement: bytes) -> None:
    with pytest.raises(QuarantineFailed) as caught:
        parse_in_quarantine(statement, parse=eats_memory, memory_bytes=300 * 1024 * 1024)
    assert caught.value.reason in {"memory", "crashed"}


def test_reading_error_does_not_echo_file_content(statement: bytes) -> None:
    with pytest.raises(QuarantineFailed) as caught:
        parse_in_quarantine(statement, parse=breaks)
    assert caught.value.reason == "invalid"
    # A mensagem da tela é fixa; o conteúdo da planilha não volta nem no detalhe do log.
    assert "DADO DO USUÁRIO" not in str(caught.value)
    assert "DADO DO USUÁRIO" not in caught.value.detail


def test_forged_answer_is_invalid(statement: bytes) -> None:
    with pytest.raises(QuarantineFailed) as caught:
        parse_in_quarantine(statement, parse=returns_garbage)
    assert caught.value.reason == "invalid"


def test_crashed_process_is_reported(statement: bytes) -> None:
    with pytest.raises(QuarantineFailed) as caught:
        parse_in_quarantine(statement, parse=dies)
    assert caught.value.reason == "crashed"


def test_quarantine_writes_nothing_to_disk(statement: bytes, tmp_path: Path, monkeypatch) -> None:
    # Pasta temporária vazia para o processo filho: se ele gravasse algo, apareceria aqui.
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    parse_in_quarantine(statement)
    assert list(tmp_path.iterdir()) == []
