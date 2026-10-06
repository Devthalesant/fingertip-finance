"""POST /imports/b3-movements: upload do extrato, com as barreiras do ADR 0004.

O upload passa pela quarentena de verdade (um processo por envio): estes testes são os
mais lentos da API, e é de propósito.
"""

import asyncio
import io
import zipfile
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.limits import BodySizeLimit
from app.api.routes import imports as imports_route
from app.api.routes.imports import clean_file_name
from app.models import AppUser, ImportFile, RawRow
from app.parsers.xlsx_guard import MAX_UPLOAD_BYTES
from sample_data.b3_format import write_movement_statement
from sample_data.scenario import movement_rows
from tests.api import bearer, make_token

URL = "/imports/b3-movements"
STORY_ROWS = len(movement_rows())
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def owner(db_session: Session) -> AppUser:
    user = AppUser(email="demo@example.com")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def story(tmp_path: Path) -> bytes:
    return write_movement_statement(movement_rows(), tmp_path / "movimentacao.xlsx").read_bytes()


def upload(
    client: TestClient,
    data: bytes,
    name: str = "movimentacao.xlsx",
    email: str = "demo@example.com",
    sub: str = "g-1",
):
    return client.post(
        URL,
        files={"file": (name, data, XLSX)},
        headers=bearer(make_token(email, sub=sub)),
    )


def imports_of(session: Session, user: AppUser) -> list[ImportFile]:
    return list(session.scalars(select(ImportFile).where(ImportFile.user_id == user.id)))


def test_upload_lands_in_the_database(
    client: TestClient, owner: AppUser, story: bytes, db_session: Session
) -> None:
    response = upload(client, story)
    assert response.status_code == 200
    assert response.json() == {
        "file_name": "movimentacao.xlsx",
        "already_imported": False,
        "new_rows": STORY_ROWS,
        "skipped_rows": 0,
        "ledger_entries": STORY_ROWS,
        "suspected_duplicates": [],
    }
    assert [f.file_name for f in imports_of(db_session, owner)] == ["movimentacao.xlsx"]


def test_same_file_twice(client: TestClient, owner: AppUser, story: bytes) -> None:
    upload(client, story)
    again = upload(client, story).json()
    assert again["already_imported"] is True
    assert again["new_rows"] == 0


def test_changed_row_comes_back_as_suspect(
    client: TestClient, owner: AppUser, tmp_path: Path
) -> None:
    rows = movement_rows()
    i = next(i for i in range(10, 20) if rows[i].amount is not None)
    changed = replace(rows[i], amount=rows[i].amount + Decimal("0.01"))
    first = write_movement_statement(rows[:20], tmp_path / "a.xlsx").read_bytes()
    second = write_movement_statement([*rows[10:i], changed, *rows[i + 1 :]], tmp_path / "b.xlsx")
    upload(client, first)
    suspects = upload(client, second.read_bytes()).json()["suspected_duplicates"]
    assert suspects == [
        {
            "date": rows[i].date.isoformat(),
            "movement": rows[i].movement.value,
            "product": rows[i].product,
        }
    ]


def test_each_user_imports_on_their_own(
    client: TestClient, owner: AppUser, story: bytes, db_session: Session
) -> None:
    other = AppUser(email="outra@example.com")
    db_session.add(other)
    db_session.flush()
    upload(client, story)
    # O mesmo arquivo, outra pessoa: não é "já importado" para ela.
    response = upload(client, story, email="outra@example.com", sub="g-2").json()
    assert response["already_imported"] is False
    assert len(imports_of(db_session, other)) == 1


def test_needs_login(client: TestClient, story: bytes) -> None:
    response = client.post(URL, files={"file": ("m.xlsx", story, XLSX)})
    assert response.status_code == 401


def test_file_name_is_cleaned(
    client: TestClient, owner: AppUser, story: bytes, db_session: Session
) -> None:
    upload(client, story, name="../../pasta\\movimentacao.xlsx")
    (saved,) = imports_of(db_session, owner)
    assert saved.file_name == "movimentacao.xlsx"


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("mov\x00imen\ttacao.xlsx", "movimentacao.xlsx"),
        ("C:\\Users\\x\\extrato.xlsx", "extrato.xlsx"),
        ("   ", "extrato.xlsx"),
        (None, "extrato.xlsx"),
    ],
)
def test_clean_file_name(raw: str | None, clean: str) -> None:
    assert clean_file_name(raw) == clean


def test_long_file_name_is_cut(
    client: TestClient, owner: AppUser, story: bytes, db_session: Session
) -> None:
    upload(client, story, name="a" * 400 + ".xlsx")
    (saved,) = imports_of(db_session, owner)
    assert len(saved.file_name) == 255
    assert saved.file_name.endswith(".xlsx")


def test_other_extension_is_refused(client: TestClient, owner: AppUser, story: bytes) -> None:
    assert upload(client, story, name="movimentacao.csv").status_code == 422


def test_zip_bomb_is_refused_and_nothing_is_saved(
    client: TestClient, owner: AppUser, story: bytes, db_session: Session
) -> None:
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(story)) as src,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("xl/worksheets/sheet2.xml", b" " * 60_000_000)
    response = upload(client, out.getvalue())
    assert response.status_code == 422
    assert "planilha comum" in response.json()["detail"]
    assert imports_of(db_session, owner) == []


def test_xlsx_that_is_not_a_statement(
    client: TestClient, owner: AppUser, db_session: Session
) -> None:
    wb = Workbook()
    wb.active.append(["Nome", "Telefone"])
    wb.active.append(["DADO PESSOAL", "99999-9999"])
    buffer = io.BytesIO()
    wb.save(buffer)
    response = upload(client, buffer.getvalue())
    assert response.status_code == 422
    # Mensagem fixa: nada da planilha volta na resposta.
    assert "DADO PESSOAL" not in response.text
    assert db_session.scalar(select(func.count()).select_from(RawRow)) == 0


def test_too_big_is_cut_at_the_door(client: TestClient, owner: AppUser) -> None:
    response = upload(client, b"PK\x03\x04" + b"\x00" * (6 * 1024 * 1024))
    assert response.status_code == 413


def test_lying_content_length_is_cut_too(client: TestClient, owner: AppUser) -> None:
    # Quem declara um tamanho e manda outro também é barrado pela contagem dos bytes.
    def chunks():
        for _ in range(7):
            yield b"\x00" * (1024 * 1024)

    response = client.post(
        URL,
        content=chunks(),
        headers=bearer(make_token()) | {"Content-Type": "multipart/form-data; boundary=x"},
    )
    assert response.status_code == 413


def test_missing_file(client: TestClient, owner: AppUser) -> None:
    response = client.post(URL, headers=bearer(make_token()))
    assert response.status_code == 422


def test_upload_is_read_in_quarantine(
    client: TestClient, owner: AppUser, story: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    # O resultado seria o mesmo lendo direto; o que se prova aqui é o caminho.
    calls = []
    real = imports_route.parse_in_quarantine

    def spy(data: bytes):
        calls.append(len(data))
        return real(data)

    monkeypatch.setattr(imports_route, "parse_in_quarantine", spy)
    upload(client, story)
    assert calls == [len(story)]


def test_file_just_over_the_limit(client: TestClient, owner: AppUser) -> None:
    # Passa pela folga do envelope do formulário; o endpoint recusa pelo tamanho do arquivo.
    response = upload(client, b"PK\x03\x04" + b"\x00" * MAX_UPLOAD_BYTES)
    assert response.status_code == 413


def test_declared_size_is_refused_without_reading_the_body() -> None:
    sent: list[dict] = []
    read: list[bool] = []

    async def receive() -> dict:
        read.append(True)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    async def never_called(scope, receive, send) -> None:
        raise AssertionError("a requisição não devia chegar à aplicação")

    scope = {
        "type": "http",
        "method": "POST",
        "path": URL,
        "headers": [(b"content-length", str(10**9).encode())],
    }
    asyncio.run(BodySizeLimit(never_called)(scope, receive, send))
    assert sent[0]["status"] == 413
    assert read == []
