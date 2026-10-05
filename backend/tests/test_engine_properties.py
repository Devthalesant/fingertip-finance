"""Regras que valem para QUALQUER histórico (Hypothesis gera milhares de casos).

O gabarito prova exemplos conhecidos; aqui são as leis do domínio:
custo se conserva, PM não muda na venda, aluguel e transferência não mexem no custo,
desdobro e grupamento não mudam o custo total, a ordem do arquivo não importa.
"""

from datetime import date, timedelta
from decimal import Decimal

from hypothesis import example, given, settings
from hypothesis import strategies as st

from app.engine.positions import Entry, compute_portfolio
from app.models.enums import Direction as Dir
from app.models.enums import EntryType as T

CENT = Decimal("0.01")
ASSET = "ABCD3"
ACCOUNTS = ("CORRETORA A", "CORRETORA B")
START = date(2021, 1, 4)

prices = st.decimals(min_value="0.01", max_value="1000", places=2)
settings.register_profile("default", deadline=None)
settings.load_profile("default")


def buy(day: date, qty: int, price: Decimal, account: str = ACCOUNTS[0]) -> Entry:
    q = Decimal(qty)
    return Entry(day, T.COMPRA, Dir.IN, ASSET, account, q, (q * price).quantize(CENT))


def sell(day: date, qty: Decimal, price: Decimal, account: str = ACCOUNTS[0]) -> Entry:
    return Entry(day, T.VENDA, Dir.OUT, ASSET, account, qty, (qty * price).quantize(CENT))


def transfer(day: date, qty: Decimal, source: str, target: str) -> list[Entry]:
    return [
        Entry(day, T.TRANSFERENCIA_CUSTODIA, Dir.OUT, ASSET, source, qty),
        Entry(day, T.TRANSFERENCIA_CUSTODIA, Dir.IN, ASSET, target, qty),
    ]


@st.composite
def buys(draw, min_size: int = 1) -> list[Entry]:
    """Só compras, uma por dia, na corretora A."""
    lots = draw(st.lists(st.tuples(st.integers(1, 10_000), prices), min_size=min_size, max_size=6))
    return [buy(START + timedelta(days=i), q, p) for i, (q, p) in enumerate(lots)]


@st.composite
def histories(draw) -> list[Entry]:
    """Compras, vendas e transferências entre duas corretoras, sempre válidas.

    O gerador acompanha quanto há em cada corretora: nunca vende nem transfere mais
    do que existe ali (a restrição está no gerador, não num filtro depois).
    """
    held = dict.fromkeys(ACCOUNTS, 0)
    entries: list[Entry] = []
    for i in range(draw(st.integers(1, 12))):
        day = START + timedelta(days=i)
        options = ["buy"] + (["sell", "transfer"] if any(held.values()) else [])
        op = draw(st.sampled_from(options))
        if op == "buy":
            account = draw(st.sampled_from(ACCOUNTS))
            qty = draw(st.integers(1, 10_000))
            entries.append(buy(day, qty, draw(prices), account))
            held[account] += qty
        else:
            account = draw(st.sampled_from([a for a in ACCOUNTS if held[a]]))
            qty = draw(st.integers(1, held[account]))
            held[account] -= qty
            if op == "sell":
                entries.append(sell(day, Decimal(qty), draw(prices), account))
            else:
                other = next(a for a in ACCOUNTS if a != account)
                entries += transfer(day, Decimal(qty), account, other)
                held[other] += qty
    return entries


def bought(entries: list[Entry]) -> Decimal:
    return sum((e.amount for e in entries if e.entry_type is T.COMPRA), Decimal(0))


@given(histories())
def test_cost_is_conserved(entries: list[Entry]) -> None:
    # Todo real pago ou saiu como custo de alguma venda ou ainda está na posição.
    state = compute_portfolio(entries)
    left = state.positions[ASSET].total_cost if ASSET in state.positions else Decimal(0)
    assert sum((s.cost for s in state.sales), Decimal(0)) + left == bought(entries)


@given(histories())
def test_custody_adds_up_to_the_position(entries: list[Entry]) -> None:
    # Conta independente do motor: comprado − vendido. Transferência não muda o total.
    state = compute_portfolio(entries)
    signed = {T.COMPRA: 1, T.VENDA: -1}
    want = sum((signed.get(e.entry_type, 0) * e.quantity for e in entries), Decimal(0))
    assert sum(state.custody.get(ASSET, {}).values(), Decimal(0)) == want
    assert not state.flags


@given(buys(), st.integers(1, 99), prices)
# 3 ações por 3,02: vender 1 custa 1,0066... → 1,01; as 2 que ficam valem 2,01.
@example(
    [buy(START, 1, Decimal("1.00")), buy(START + timedelta(days=1), 2, Decimal("1.01"))],
    33,
    Decimal("2.00"),
)
def test_sale_keeps_the_average_price(lots: list[Entry], pct: int, price: Decimal) -> None:
    before = compute_portfolio(lots).positions[ASSET]
    qty = max(Decimal(1), (before.quantity * pct / 100).to_integral_value())
    if qty >= before.quantity:
        qty = before.quantity - 1
    if qty <= 0:
        return  # posição de 1 ação: não há venda parcial possível
    day = lots[-1].trade_date + timedelta(days=1)
    after = compute_portfolio([*lots, sell(day, qty, price)])
    (sale,) = after.sales
    left = after.positions[ASSET]
    # O custo se divide sem sumir um centavo; o PM só oscila pelo arredondamento.
    assert sale.cost + left.total_cost == before.total_cost
    assert abs(left.average_price - before.average_price) * left.quantity <= CENT


@given(buys(), st.integers(2, 10))
def test_split_multiplies_quantity_and_keeps_cost(lots: list[Entry], factor: int) -> None:
    before = compute_portfolio(lots).positions[ASSET]
    day = lots[-1].trade_date + timedelta(days=1)
    received = before.quantity * (factor - 1)  # a B3 traz só as ações recebidas
    split = Entry(day, T.DESDOBRO, Dir.IN, ASSET, ACCOUNTS[0], received)
    after = compute_portfolio([*lots, split]).positions[ASSET]
    assert after.quantity == before.quantity * factor
    assert after.total_cost == before.total_cost


@given(buys(), st.integers(2, 100))
def test_reverse_split_divides_quantity_and_keeps_cost(lots: list[Entry], factor: int) -> None:
    before = compute_portfolio(lots).positions[ASSET]
    day = lots[-1].trade_date + timedelta(days=1)
    resulting = before.quantity / factor  # a B3 traz a quantidade resultante, com fração
    group = Entry(day, T.GRUPAMENTO, Dir.IN, ASSET, ACCOUNTS[0], resulting)
    after = compute_portfolio([*lots, group]).positions[ASSET]
    assert after.quantity == resulting
    assert after.total_cost == before.total_cost


@given(buys(), st.data())
def test_loan_out_and_back_changes_nothing(lots: list[Entry], data: st.DataObject) -> None:
    held = int(compute_portfolio(lots).positions[ASSET].quantity)
    qty = Decimal(data.draw(st.integers(1, held)))
    out_day = lots[-1].trade_date + timedelta(days=1)
    back_day = out_day + timedelta(days=data.draw(st.integers(1, 365)))
    account = ACCOUNTS[0]
    loan = [
        *[
            Entry(
                e.trade_date,
                e.entry_type,
                e.direction,
                e.asset,
                e.account,
                e.quantity,
                affects_position=False,
            )
            for e in transfer(out_day, qty, account, account)
        ],
        Entry(out_day, T.ALUGUEL_REGISTRO, Dir.IN, ASSET, account, qty, affects_position=False),
        Entry(out_day, T.ALUGUEL_SAIDA, Dir.OUT, ASSET, account, qty, affects_position=False),
        Entry(
            back_day,
            T.ALUGUEL_RETORNO,
            Dir.IN,
            ASSET,
            account,
            qty,
            (qty * Decimal("99.99")).quantize(CENT),
            affects_position=False,
        ),
    ]
    without, with_loan = compute_portfolio(lots), compute_portfolio([*lots, *loan])
    assert with_loan.positions == without.positions
    assert with_loan.custody == without.custody
    assert with_loan.sales == []


@given(buys(), st.data())
def test_transfer_moves_custody_not_cost(lots: list[Entry], data: st.DataObject) -> None:
    before = compute_portfolio(lots)
    held = int(before.positions[ASSET].quantity)
    qty = data.draw(st.integers(1, held))
    day = lots[-1].trade_date + timedelta(days=1)
    after = compute_portfolio([*lots, *transfer(day, Decimal(qty), *ACCOUNTS)])
    assert after.positions == before.positions
    assert after.custody[ASSET] == {
        k: v for k, v in {ACCOUNTS[0]: Decimal(held - qty), ACCOUNTS[1]: Decimal(qty)}.items() if v
    }


@given(histories(), st.randoms())
def test_file_order_does_not_matter(entries: list[Entry], rnd) -> None:
    # Cada dia tem no máximo uma operação (o par da transferência é simétrico): a ordem
    # da lista recebida não pode mudar o resultado.
    shuffled = list(entries)
    rnd.shuffle(shuffled)
    a, b = compute_portfolio(entries), compute_portfolio(shuffled)
    assert (a.positions, a.custody, a.sales) == (b.positions, b.custody, b.sales)
