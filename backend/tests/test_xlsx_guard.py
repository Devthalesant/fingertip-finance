"""Raio-x do xlsx antes de abrir (ADR 0004, camada 1).

Cada teste fabrica um arquivo malicioso a partir do extrato sintético. Nada é baixado
da internet: o "ataque" é montado aqui, com o mínimo para acionar a barreira.
"""

import io
import secrets
import zipfile

import pytest

from app.parsers import xlsx_guard
from app.parsers.xlsx_guard import (
    MAX_UNCOMPRESSED_BYTES,
    MAX_UPLOAD_BYTES,
    UnsafeFile,
    inspect_xlsx,
)
from sample_data.b3_format import write_movement_statement
from sample_data.scenario import movement_rows


@pytest.fixture(scope="module")
def valid(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    path = tmp_path_factory.mktemp("xlsx") / "movimentacao.xlsx"
    return write_movement_statement(movement_rows(), path).read_bytes()


def rezip(
    data: bytes,
    add: dict[str, bytes] | None = None,
    drop: tuple[str, ...] = (),
    **zip_options: object,
) -> bytes:
    """O mesmo xlsx com peças a mais ou a menos."""
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as src,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, **zip_options) as dst,
    ):
        for info in src.infolist():
            if info.filename not in drop:
                dst.writestr(info.filename, src.read(info.filename))
        for name, content in (add or {}).items():
            dst.writestr(name, content)
    return out.getvalue()


def reason(data: bytes) -> str:
    with pytest.raises(UnsafeFile) as caught:
        inspect_xlsx(data)
    return caught.value.reason


def test_synthetic_statement_passes(valid: bytes) -> None:
    inspect_xlsx(valid)


def test_not_a_zip() -> None:
    assert reason(b"Entrada/Saida;Data;Movimentacao\n") == "not_xlsx"


def test_polyglot_with_junk_before_the_zip(valid: bytes) -> None:
    # O leitor de zip acha o índice no fim e aceitaria; a assinatura no início, não.
    assert reason(b"GIF89a" + valid) == "not_xlsx"


def test_zip_header_but_broken() -> None:
    assert reason(b"PK\x03\x04" + b"\x00" * 100) == "not_xlsx"


def test_too_big_to_even_look(valid: bytes) -> None:
    assert reason(valid + b"\x00" * MAX_UPLOAD_BYTES) == "too_big"


def test_zip_bomb_by_total_size(valid: bytes) -> None:
    # Zeros comprimem ~1000:1: poucos KB no envio, dezenas de MB ao abrir.
    bomb = rezip(valid, add={"xl/worksheets/sheet2.xml": b"\x00" * (MAX_UNCOMPRESSED_BYTES + 1)})
    assert len(bomb) < MAX_UPLOAD_BYTES
    assert reason(bomb) == "zip_bomb"


def test_too_big_when_opened_even_with_normal_ratio(
    valid: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Texto variado comprime pouco (taxa normal), mas o total aberto passa do teto.
    monkeypatch.setattr(xlsx_guard, "MAX_UNCOMPRESSED_BYTES", 200_000)
    varied = secrets.token_hex(100_000).encode()
    assert reason(rezip(valid, add={"xl/worksheets/sheet2.xml": varied})) == "zip_bomb"


def test_zip_bomb_by_ratio(valid: bytes) -> None:
    # Pequena no total, mas com taxa de compressão que nenhuma planilha tem.
    assert reason(rezip(valid, add={"xl/worksheets/sheet2.xml": b" " * 2_000_000})) == "zip_bomb"


@pytest.mark.parametrize(
    "name",
    [
        "xl/vbaProject.bin",  # macro
        "xl/externalLinks/externalLink1.xml",  # puxa dados de fora
        "xl/embeddings/oleObject1.bin",  # objeto embutido
        "xl/media/inner.zip",  # zip dentro do zip
        "xl/activeX/activeX1.xml",
    ],
)
def test_dangerous_parts(valid: bytes, name: str) -> None:
    assert reason(rezip(valid, add={name: b"<x/>"})) == "unexpected_part"


@pytest.mark.parametrize("name", ["../fora.xml", "/abs.xml", "xl\\..\\fora.xml", "C:/x.xml"])
def test_strange_paths(valid: bytes, name: str) -> None:
    assert reason(rezip(valid, add={name: b"<x/>"})) == "unexpected_part"


def test_duplicate_part_names(valid: bytes) -> None:
    # Dois "workbook.xml": cada leitor poderia abrir um diferente.
    out = io.BytesIO(rezip(valid))
    with pytest.warns(UserWarning), zipfile.ZipFile(out, "a") as z:
        z.writestr("xl/workbook.xml", b"<outro/>")
    assert reason(out.getvalue()) == "unexpected_part"


def test_too_many_parts(valid: bytes) -> None:
    many = {f"xl/worksheets/sheet{i}.xml": b"<x/>" for i in range(2, 200)}
    assert reason(rezip(valid, add=many)) == "too_many_parts"


def test_missing_workbook(valid: bytes) -> None:
    assert reason(rezip(valid, drop=("xl/workbook.xml",))) == "not_xlsx"


def test_encrypted_part(valid: bytes) -> None:
    # Liga o bit "criptografado" no índice central de cada peça (offset 8 da entrada).
    data = bytearray(valid)
    start = data.find(b"PK\x01\x02")
    assert start != -1
    while start != -1:
        data[start + 8] |= 0x01
        start = data.find(b"PK\x01\x02", start + 4)
    assert reason(bytes(data)) == "unexpected_part"


def test_reason_message_is_friendly(valid: bytes) -> None:
    with pytest.raises(UnsafeFile) as caught:
        inspect_xlsx(b"nada")
    assert "xlsx" in str(caught.value)
