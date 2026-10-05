"""A prova: o motor de PM faz a história do investidor fictício e confere com o gabarito.

O gabarito (sample_data/expected.py) foi calculado à mão. Aqui nada é recalculado:
só se compara o que o motor devolve com os números literais de lá.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.engine.positions import (
    Bonus,
    CuratedEvents,
    Entry,
    PortfolioState,
    Subscription,
    TickerChange,
    compute_portfolio,
)
from app.ledger.classify import classify_movements
from app.models.enums import EntryType as T
from app.parsers.b3_movimentacao import parse_movement_statement
from sample_data import expected
from sample_data.b3_format import write_movement_statement
from sample_data.scenario import BROKER_A, BROKER_B, movement_rows

CENT = Decimal("0.01")

# A tabela de aliases de instituição, como estará no banco: cada grafia → nome canônico.
ACCOUNTS = {
    spelling: broker.name for broker in (BROKER_A, BROKER_B) for spelling in broker.spellings
}

# Eventos curados (fontes citadas em scenario.py).
STORY_EVENTS = CuratedEvents(
    ticker_changes=(TickerChange(old="VIIA3", new="BHIA3", date=date(2023, 9, 20)),),
    bonuses=(Bonus(asset="ITSA4", date=date(2024, 12, 2), cost_per_unit=Decimal("13.55518731")),),
    subscriptions=(Subscription(right="KNRI12", receipt="KNRI13", underlying="KNRI11"),),
)

# Renda fixa: o gabarito usa o produto; o motor, o código do título.
FIXED_INCOME_CODES = {
    "CDB - 23C01234567 - BANCO EXEMPLO S/A": "23C01234567",
    "LCA - 23F00765432 - BANCO EXEMPLO S/A": "23F00765432",
    "Tesouro Selic 2029": "Tesouro Selic 2029",
    "Tesouro IPCA+ com Juros Semestrais 2035": "Tesouro IPCA+ com Juros Semestrais 2035",
}


@pytest.fixture(scope="module")
def story_entries(tmp_path_factory: pytest.TempPathFactory) -> list[Entry]:
    path = tmp_path_factory.mktemp("b3") / "movimentacao.xlsx"
    rows = parse_movement_statement(write_movement_statement(movement_rows(), path))
    return [
        Entry(
            trade_date=e.trade_date,
            entry_type=e.entry_type,
            direction=e.direction,
            asset=e.asset_code,
            account=ACCOUNTS[e.institution],
            quantity=e.quantity,
            amount=e.gross_amount,
            tax_withheld=e.tax_withheld,
            affects_position=e.affects_position,
        )
        for e in classify_movements(rows)
    ]


@pytest.fixture(scope="module")
def story(story_entries: list[Entry]) -> PortfolioState:
    return compute_portfolio(story_entries, STORY_EVENTS)


def summary(state: PortfolioState) -> dict:
    return {
        asset: (p.quantity, p.total_cost, p.average_price.quantize(CENT))
        for asset, p in state.positions.items()
    }


def test_positions_match_the_gabarito(story: PortfolioState) -> None:
    want = {t: (p.quantity, p.total_cost, p.average_price) for t, p in expected.POSITIONS.items()}
    want |= {
        FIXED_INCOME_CODES[product]: (p.quantity, p.total_cost, p.average_price)
        for product, p in expected.FIXED_INCOME_POSITIONS.items()
    }
    # Nada além disso: ativos zerados, direitos e recibos não aparecem.
    assert summary(story) == want


def test_custody_is_per_broker_and_cost_is_not(story: PortfolioState) -> None:
    assert {a: story.custody[a] for a in expected.CUSTODY} == expected.CUSTODY


def test_sales_match_the_gabarito(story: PortfolioState) -> None:
    fixed_income = set(FIXED_INCOME_CODES.values())
    sales = {
        (s.date, s.asset, s.quantity, s.proceeds, s.cost, s.result)
        for s in story.sales
        if s.asset not in fixed_income
    }
    assert sales == {
        (s.date, s.ticker, s.quantity, s.proceeds, s.cost, s.result) for s in expected.SALES
    }


def test_fixed_income_redemptions_match_the_gabarito(story: PortfolioState) -> None:
    fixed_income = set(FIXED_INCOME_CODES.values())
    redemptions = {
        (s.date, s.asset, s.proceeds, s.cost, s.result)
        for s in story.sales
        if s.asset in fixed_income
    }
    assert redemptions == {
        (r.date, FIXED_INCOME_CODES[r.product], r.received, r.cost, r.gain)
        for r in expected.FIXED_INCOME_REDEMPTIONS
    }


def test_dividends_match_the_gabarito(story: PortfolioState) -> None:
    kinds = {T.JCP, T.DIVIDENDO, T.RENDIMENTO}
    got = {
        (i.date, i.asset, i.kind.value, i.gross, i.tax_withheld, i.net)
        for i in story.income
        if i.kind in kinds
    }
    assert got == {
        (i.date, i.ticker, i.kind, i.gross, i.tax_withheld, i.net) for i in expected.INCOME
    }


def test_loan_income_and_coupons_match_the_gabarito(story: PortfolioState) -> None:
    loan_kinds = {T.REEMBOLSO_ALUGUEL: "REEMBOLSO", T.ALUGUEL_REMUNERACAO: "REMUNERACAO"}
    loans = {
        (i.date, i.asset, loan_kinds[i.kind], i.net) for i in story.income if i.kind in loan_kinds
    }
    assert loans == {(i.date, i.ticker, i.kind, i.amount) for i in expected.LOAN_INCOME}

    coupons = {(i.date, i.asset, i.net) for i in story.income if i.kind is T.JUROS}
    assert coupons == {
        (day, FIXED_INCOME_CODES[product], value)
        for day, product, value in expected.FIXED_INCOME_COUPONS
    }


def test_story_with_curated_events_raises_no_flags(story: PortfolioState) -> None:
    assert story.flags == []


def test_quantities_on_the_consolidated_date(story_entries: list[Entry]) -> None:
    # Checkpoint de 31/03/2024 (conta no comentário de expected.py).
    state = compute_portfolio(story_entries, STORY_EVENTS, until=expected.RECONCILIATION_DATE)
    quantities = {a: p.quantity for a, p in state.positions.items()}
    assert {
        a: quantities[a]
        for a in ("BBAS3", "WEGE3", "MGLU3", "ITSA4", "KNRI11", "23C01234567", "23F00765432")
    } == {
        "BBAS3": Decimal("200"),
        "WEGE3": Decimal("150"),
        "MGLU3": expected.RECONCILIATION_DIVERGENCES["MGLU3"][0],
        "ITSA4": Decimal("200"),
        "KNRI11": Decimal("100"),
        "23C01234567": Decimal("3"),
        "23F00765432": Decimal("3"),
    }


def test_bonus_without_curated_cost_is_zero_and_flagged(story_entries: list[Entry]) -> None:
    # O erro comum que o gabarito cita: custo zero na bonificação → lucro de 310,00.
    events = CuratedEvents(
        ticker_changes=STORY_EVENTS.ticker_changes, subscriptions=STORY_EVENTS.subscriptions
    )
    state = compute_portfolio(story_entries, events)
    (itsa,) = [s for s in state.sales if s.asset == "ITSA4"]
    assert itsa.result == Decimal("310.00")
    assert [(f.asset, f.code) for f in state.flags] == [("ITSA4", "COST_ASSUMED_ZERO")]
