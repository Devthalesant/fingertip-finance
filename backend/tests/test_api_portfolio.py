"""GET /portfolio: a carteira da pessoa, conferida com o gabarito feito à mão."""

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.ledger.importer import import_b3_movements
from app.models import AppUser, Asset, CorporateEvent
from app.models.enums import AssetClass, CorporateEventType
from sample_data import expected
from sample_data.b3_format import write_movement_statement
from sample_data.catalog import seed_story_catalog
from sample_data.scenario import movement_rows
from tests.api import bearer, make_token

# Renda fixa: o gabarito usa o produto; a carteira, o código do título.
FIXED_INCOME_CODES = {
    "CDB - 23C01234567 - BANCO EXEMPLO S/A": "23C01234567",
    "LCA - 23F00765432 - BANCO EXEMPLO S/A": "23F00765432",
    "Tesouro Selic 2029": "Tesouro Selic 2029",
    "Tesouro IPCA+ com Juros Semestrais 2035": "Tesouro IPCA+ com Juros Semestrais 2035",
}


def make_user(session: Session, email: str) -> AppUser:
    user = AppUser(email=email)
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def owner(db_session: Session, tmp_path: Path) -> AppUser:
    """O investidor fictício, com a história inteira importada."""
    seed_story_catalog(db_session)
    user = make_user(db_session, "demo@example.com")
    path = write_movement_statement(movement_rows(), tmp_path / "movimentacao.xlsx")
    import_b3_movements(db_session, user.id, path)
    return user


def get_portfolio(client: TestClient, email: str = "demo@example.com", sub: str = "g-1") -> dict:
    response = client.get("/portfolio", headers=bearer(make_token(email, sub=sub)))
    assert response.status_code == 200
    return response.json()


def text(value: Decimal) -> str:
    """Como a API escreve um número: string decimal, sem zeros sobrando."""
    return format(value.normalize(), "f") if value != value.to_integral() else str(int(value))


def test_positions_match_the_gabarito(client: TestClient, owner: AppUser) -> None:
    got = {
        p["asset"]["code"]: (p["quantity"], p["total_cost"], p["average_price"])
        for p in get_portfolio(client)["positions"]
    }
    want = {
        code: (text(p.quantity), f"{p.total_cost:.2f}", f"{p.average_price:.2f}")
        for code, p in expected.POSITIONS.items()
    } | {
        FIXED_INCOME_CODES[product]: (
            text(p.quantity),
            f"{p.total_cost:.2f}",
            f"{p.average_price:.2f}",
        )
        for product, p in expected.FIXED_INCOME_POSITIONS.items()
    }
    assert got == want


def test_custody_by_broker(client: TestClient, owner: AppUser) -> None:
    positions = {p["asset"]["code"]: p for p in get_portfolio(client)["positions"]}
    for code, brokers in expected.CUSTODY.items():
        got = {c["institution"]: c["quantity"] for c in positions[code]["custody"]}
        assert got == {name: text(q) for name, q in brokers.items()}


def test_numbers_are_decimal_strings(client: TestClient, owner: AppUser) -> None:
    # Dinheiro nunca como número do JSON (vira float no navegador).
    (wege,) = [p for p in get_portfolio(client)["positions"] if p["asset"]["code"] == "WEGE3"]
    assert (wege["quantity"], wege["total_cost"], wege["average_price"]) == (
        "150",
        "4650.00",
        "31.00",
    )


def test_assets_come_with_catalog_name_and_class(client: TestClient, owner: AppUser) -> None:
    positions = {p["asset"]["code"]: p["asset"] for p in get_portfolio(client)["positions"]}
    assert positions["KNRI11"]["asset_class"] == AssetClass.FII.value
    assert positions["WEGE3"]["name"]


def test_story_has_no_flags(client: TestClient, owner: AppUser) -> None:
    assert get_portfolio(client)["flags"] == []


def test_bonus_without_curated_cost_shows_a_flag(
    client: TestClient, owner: AppUser, db_session: Session
) -> None:
    # Sem o custo curado da bonificação, o motor assume zero e avisa. A data do aviso é
    # a do crédito no extrato (04/12), não a do evento (02/12).
    db_session.execute(
        update(CorporateEvent)
        .where(CorporateEvent.event_type == CorporateEventType.BONIFICACAO)
        .values(cost_per_unit=None)
    )
    assert get_portfolio(client)["flags"] == [
        {"date": "2024-12-04", "asset": "ITSA4", "code": "COST_ASSUMED_ZERO"}
    ]


def test_other_user_sees_an_empty_portfolio(
    client: TestClient, owner: AppUser, db_session: Session
) -> None:
    make_user(db_session, "outra@example.com")
    assert get_portfolio(client, "outra@example.com", sub="g-2") == {"positions": [], "flags": []}


def test_another_users_private_asset_does_not_leak(
    client: TestClient, owner: AppUser, db_session: Session
) -> None:
    # Outra pessoa cadastrou um ativo privado com o mesmo código de um ativo da carteira.
    other = make_user(db_session, "outra@example.com")
    db_session.add(
        Asset(
            canonical_code="WEGE3",
            name="NOME PRIVADO DA OUTRA PESSOA",
            asset_class=AssetClass.ACAO,
            owner_user_id=other.id,
        )
    )
    db_session.flush()
    names = {p["asset"]["code"]: p["asset"]["name"] for p in get_portfolio(client)["positions"]}
    assert names["WEGE3"] != "NOME PRIVADO DA OUTRA PESSOA"


def test_needs_login(client: TestClient) -> None:
    assert client.get("/portfolio").status_code == 401


def test_own_private_asset_wins_over_the_catalog(
    client: TestClient, owner: AppUser, db_session: Session
) -> None:
    db_session.add(
        Asset(
            canonical_code="WEGE3",
            name="MEU NOME PARA A WEG",
            asset_class=AssetClass.ACAO,
            owner_user_id=owner.id,
        )
    )
    db_session.flush()
    names = {p["asset"]["code"]: p["asset"]["name"] for p in get_portfolio(client)["positions"]}
    assert names["WEGE3"] == "MEU NOME PARA A WEG"
