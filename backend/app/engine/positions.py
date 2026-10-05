"""Motor de PM: dos lançamentos à posição, ao custo, às vendas e aos proventos.

Regras (Receita Federal): o PM é por investidor e ativo, não por corretora. Compra soma
ao custo; venda não muda o PM, só tira a quantidade e o custo proporcional. Resultado
da venda = valor recebido − custo da parte vendida (bruto, antes do IR).

Custódia (em que corretora está) é outra dimensão: transferência entre corretoras muda a
custódia e não mexe no custo. O que a B3 não explica (custo da bonificação, troca de
ticker, recibo que vira cota) vem dos eventos curados (CuratedEvents).

Nada aqui fala com o banco: entra uma lista de lançamentos, sai o retrato da carteira.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.models.enums import Direction, EntryType

T = EntryType
CENT = Decimal("0.01")
ZERO = Decimal("0")
# Prazo entre a data com da bonificação e o crédito das ações na B3.
BONUS_WINDOW_DAYS = 30

# No mesmo dia, eventos que mudam a quantidade vêm antes do resto: o grupamento antes
# da baixa da fração, o direito recebido antes da solicitação de subscrição.
FIRST_IN_THE_DAY = {
    T.DESDOBRO,
    T.GRUPAMENTO,
    T.BONIFICACAO,
    T.ATUALIZACAO,
    T.INCORPORACAO,
    T.DIREITO_RECEBIDO,
}
INCOME_TYPES = {
    T.JCP,
    T.DIVIDENDO,
    T.RENDIMENTO,
    T.JUROS,
    # Amortização devolve parte do principal; o abatimento do custo fica para a v0.3.
    T.AMORTIZACAO,
    T.REEMBOLSO_ALUGUEL,
    T.ALUGUEL_REMUNERACAO,
}
SALE_TYPES = {T.VENDA, T.RESGATE, T.DIREITO_CEDIDO}


@dataclass(frozen=True)
class Entry:
    """Um lançamento, do jeito que o motor precisa (vem do ledger, importado ou manual)."""

    trade_date: date
    entry_type: EntryType
    direction: Direction
    asset: str
    account: str
    quantity: Decimal
    amount: Decimal | None = None  # valor bruto da operação ou do provento
    tax_withheld: Decimal | None = None
    affects_position: bool = True


@dataclass(frozen=True)
class TickerChange:
    old: str
    new: str
    date: date


@dataclass(frozen=True)
class Bonus:
    asset: str
    date: date  # data com
    cost_per_unit: Decimal  # custo atribuído, do aviso aos acionistas


@dataclass(frozen=True)
class Subscription:
    right: str  # direito (ex.: KNRI12)
    receipt: str  # recibo (ex.: KNRI13), que depois vira o ativo
    underlying: str  # o ativo (ex.: KNRI11)


@dataclass(frozen=True)
class CuratedEvents:
    ticker_changes: tuple[TickerChange, ...] = ()
    bonuses: tuple[Bonus, ...] = ()
    subscriptions: tuple[Subscription, ...] = ()


NO_EVENTS = CuratedEvents()


@dataclass(frozen=True)
class Position:
    quantity: Decimal
    total_cost: Decimal

    @property
    def average_price(self) -> Decimal:
        return self.total_cost / self.quantity


@dataclass(frozen=True)
class Sale:
    date: date
    asset: str
    quantity: Decimal
    proceeds: Decimal
    cost: Decimal
    result: Decimal  # proceeds − cost; negativo = prejuízo


@dataclass(frozen=True)
class Income:
    date: date
    asset: str
    kind: EntryType
    gross: Decimal
    tax_withheld: Decimal
    net: Decimal


@dataclass(frozen=True)
class Flag:
    """Premissa ou inconsistência que o app mostra ao usuário."""

    date: date
    asset: str
    code: str


@dataclass
class PortfolioState:
    positions: dict[str, Position]
    custody: dict[str, dict[str, Decimal]]
    sales: list[Sale] = field(default_factory=list)
    income: list[Income] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)


def compute_portfolio(
    entries: Iterable[Entry], events: CuratedEvents = NO_EVENTS, until: date | None = None
) -> PortfolioState:
    """Processa os lançamentos em ordem de data (até `until`, se informado)."""
    entries = list(entries)
    order = sorted(
        range(len(entries)),
        key=lambda i: (entries[i].trade_date, entries[i].entry_type not in FIRST_IN_THE_DAY, i),
    )
    book = _Book(events)
    for i in order:
        if until is not None and entries[i].trade_date > until:
            break
        book.apply(entries[i])
    return book.state()


class _Book:
    """O livro-razão em memória: quantidade por corretora e custo por ativo."""

    def __init__(self, events: CuratedEvents) -> None:
        self.events = events
        self.custody: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        self.cost: dict[str, Decimal] = defaultdict(Decimal)
        # Fração baixada no grupamento, esperando o leilão: (quantidade, custo).
        self.fractions: dict[str, tuple[Decimal, Decimal]] = {}
        # Custo da subscrição em andamento (direitos + pagamento), por direito.
        self.subscribing: dict[str, Decimal] = defaultdict(Decimal)
        self.sales: list[Sale] = []
        self.income: list[Income] = []
        self.flags: list[Flag] = []

    # --- leitura ---------------------------------------------------------------

    def quantity(self, asset: str) -> Decimal:
        return sum(self.custody[asset].values(), ZERO)

    def state(self) -> PortfolioState:
        positions, custody = {}, {}
        for asset in sorted(self.custody):
            accounts = {a: q for a, q in self.custody[asset].items() if q != 0}
            if accounts:
                positions[asset] = Position(self.quantity(asset), self.cost[asset])
                custody[asset] = accounts
        return PortfolioState(positions, custody, self.sales, self.income, self.flags)

    # --- operações básicas -----------------------------------------------------

    def add(self, asset: str, account: str, quantity: Decimal, cost: Decimal = ZERO) -> None:
        self.custody[asset][account] += quantity
        self.cost[asset] += cost

    def remove(self, asset: str, account: str, quantity: Decimal) -> Decimal:
        """Tira a quantidade e devolve o custo proporcional (o PM não muda)."""
        total = self.quantity(asset)
        if quantity >= total:
            cost = self.cost[asset]
        else:
            cost = (self.cost[asset] * quantity / total).quantize(CENT)
        self.custody[asset][account] -= quantity
        self.cost[asset] -= cost
        return cost

    def move(self, source: str, target: str) -> None:
        """Toda a posição de um ativo passa para outro (troca de ticker, recibo → cota)."""
        for account, quantity in self.custody.pop(source, {}).items():
            self.custody[target][account] += quantity
        self.cost[target] += self.cost.pop(source, ZERO)

    def flag(self, entry: Entry, code: str) -> None:
        self.flags.append(Flag(entry.trade_date, entry.asset, code))

    # --- um lançamento ---------------------------------------------------------

    def apply(self, e: Entry) -> None:  # noqa: C901 - um ramo por tipo é o mais legível
        kind, asset, account, qty = e.entry_type, e.asset, e.account, e.quantity
        if kind in INCOME_TYPES:
            gross = e.amount or ZERO
            tax = e.tax_withheld or ZERO
            self.income.append(Income(e.trade_date, asset, kind, gross, tax, gross - tax))
        elif kind is T.COMPRA or kind is T.DIREITO_RECEBIDO:
            self.add(asset, account, qty, e.amount or ZERO)
        elif kind in SALE_TYPES:
            self.sell(e)
        elif kind is T.DESDOBRO:
            # A linha traz as ações recebidas; o custo total não muda.
            self.add(asset, account, qty)
        elif kind is T.GRUPAMENTO:
            # A linha traz a quantidade resultante (com fração); o custo não muda.
            self.custody[asset][account] = qty
        elif kind is T.BONIFICACAO:
            self.bonus(e)
        elif kind is T.ATUALIZACAO:
            self.update(e)
        elif kind is T.FRACAO_BAIXA:
            cost = self.remove(asset, account, qty)
            held_qty, held_cost = self.fractions.get(asset, (ZERO, ZERO))
            self.fractions[asset] = (held_qty + qty, held_cost + cost)
        elif kind is T.LEILAO_FRACAO:
            self.fraction_auction(e)
        elif kind is T.SUBSCRICAO_SOLICITADA:
            # O direito sai e o custo dele (zero, se veio de graça) vai para a cota nova.
            if not self._subscription(right=asset):
                self.flag(e, "SUBSCRICAO_SEM_OFERTA")
            self.subscribing[asset] += self.remove(asset, account, qty)
        elif kind is T.SUBSCRICAO_EXERCIDA:
            self.subscribing[asset] += e.amount or ZERO
        elif kind is T.SUBSCRICAO_RECIBO:
            offer = self._subscription(receipt=asset)
            cost = self.subscribing.pop(offer.right, ZERO) if offer else ZERO
            self.add(asset, account, qty, cost)
        elif kind is T.DIREITO_EXPIRADO:
            if self.remove(asset, account, qty) > 0:
                self.flag(e, "DIREITO_EXPIRADO_COM_CUSTO")
        elif kind is T.TRANSFERENCIA_CUSTODIA and e.affects_position:
            sign = 1 if e.direction is Direction.IN else -1
            self.custody[asset][account] += sign * qty
        # Demais (aluguel, registro, par interno, evento excluído): não mexem em nada.

    def sell(self, e: Entry) -> None:
        if e.quantity > self.quantity(e.asset):
            self.flag(e, "VENDA_ACIMA_DA_POSICAO")
        cost = self.remove(e.asset, e.account, e.quantity)
        proceeds = e.amount or ZERO
        self.sales.append(Sale(e.trade_date, e.asset, e.quantity, proceeds, cost, proceeds - cost))

    def bonus(self, e: Entry) -> None:
        bonus = next(
            (
                b
                for b in self.events.bonuses
                if b.asset == e.asset and 0 <= (e.trade_date - b.date).days <= BONUS_WINDOW_DAYS
            ),
            None,
        )
        if bonus is None:
            # A B3 não informa o custo atribuído: zero é a premissa, e o app avisa.
            self.flag(e, "COST_ASSUMED_ZERO")
            self.add(e.asset, e.account, e.quantity)
        else:
            self.add(
                e.asset, e.account, e.quantity, (e.quantity * bonus.cost_per_unit).quantize(CENT)
            )

    def update(self, e: Entry) -> None:
        """'Atualização': troca de ticker ou recibo virando cota, conforme os eventos."""
        change = next(
            (
                c
                for c in self.events.ticker_changes
                if c.new == e.asset and c.date <= e.trade_date and self.quantity(c.old) > 0
            ),
            None,
        )
        offer = self._subscription(underlying=e.asset)
        if change:
            self.move(change.old, change.new)
        elif offer and self.quantity(offer.receipt) > 0:
            # A cota nova já entrou como recibo: contar de novo dobraria a quantidade.
            self.move(offer.receipt, offer.underlying)
        else:
            self.flag(e, "ATUALIZACAO_SEM_EVENTO")
            self.add(e.asset, e.account, e.quantity)

    def fraction_auction(self, e: Entry) -> None:
        held_qty, held_cost = self.fractions.pop(e.asset, (ZERO, ZERO))
        if e.quantity >= held_qty:
            cost = held_cost
        else:
            cost = (held_cost * e.quantity / held_qty).quantize(CENT)
            self.fractions[e.asset] = (held_qty - e.quantity, held_cost - cost)
        proceeds = e.amount or ZERO
        # Para o IR, o leilão da fração é uma venda.
        self.sales.append(Sale(e.trade_date, e.asset, e.quantity, proceeds, cost, proceeds - cost))

    def _subscription(self, **match: str) -> Subscription | None:
        ((attr, value),) = match.items()
        return next((s for s in self.events.subscriptions if getattr(s, attr) == value), None)
