"""Teste de volume (ADR 0004): 10 anos de um investidor muito ativo, medidos de ponta a
ponta pela API. Fora da bateria normal (lento); rodar com `uv run pytest -m slow -s`.

Os tetos são folgados: o objetivo é perceber quando um "limite conhecido" do ADR 0004
começar a pesar, não cronometrar ao milissegundo.
"""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import rate_limit
from app.models import AppUser
from sample_data.b3_format import write_movement_statement
from sample_data.volume import volume_rows
from tests.api import bearer, make_token

pytestmark = pytest.mark.slow

URL = "/imports/b3-movements"


def timed(call):
    started = time.monotonic()
    response = call()
    return response, time.monotonic() - started


def test_ten_years_of_an_active_investor(
    client: TestClient, db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(rate_limit.LIMITS, "api", (1000, 60))
    db_session.add(AppUser(email="demo@example.com"))
    db_session.flush()
    rows = volume_rows()
    # Dois exports que se sobrepõem: o 2º traz o último ano de novo e um mês a mais.
    cut = len(rows) - len(rows) // 10
    first = write_movement_statement(rows[:cut], tmp_path / "a.xlsx").read_bytes()
    second = write_movement_statement(rows[cut - 2000 :], tmp_path / "b.xlsx").read_bytes()
    headers = bearer(make_token())

    def send(data: bytes):
        files = {"file": ("m.xlsx", data, "application/octet-stream")}
        # O crachá vence em 5 min; um novo a cada chamada, como faria o frontend.
        return client.post(URL, files=files, headers=bearer(make_token()))

    first_upload, t_first = timed(lambda: send(first))
    second_upload, t_second = timed(lambda: send(second))
    portfolio, t_portfolio = timed(lambda: client.get("/portfolio", headers=headers))

    print(
        f"\n{len(rows)} linhas, {len(first) // 1024} KB: 1º upload {t_first:.1f}s, "
        f"2º (sobreposto) {t_second:.1f}s, carteira {t_portfolio:.2f}s"
    )
    assert first_upload.status_code == second_upload.status_code == portfolio.status_code == 200
    assert second_upload.json()["skipped_rows"] == 2000
    assert first_upload.json()["ledger_entries"] + len(rows) - cut == len(rows)
    assert len(portfolio.json()["positions"]) == 20
    assert t_first < 60
    assert t_second < 60
    assert t_portfolio < 5
