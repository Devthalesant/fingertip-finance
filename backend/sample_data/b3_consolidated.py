"""Formato do relatório consolidado mensal da B3 (xlsx), com as esquisitices do original.

Uma aba por tipo de posição. O que o original tem e o sintético imita:
- nome do produto com espaços sobrando no fim;
- cada aba termina com uma linha em branco, a palavra "Total" e o valor total;
- na aba de proventos, a quantidade vem como texto;
- na renda fixa, alguns títulos trazem o valor em duas colunas sem nome no fim
  (fora de "CURVA"), e o Total da aba ignora esses títulos. Não confiar no Total.

Abas sem linhas não são gravadas. O original mistura célula vazia e texto vazio ("");
o openpyxl grava "" como vazia, então o parser deve tratar os dois como iguais.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from sample_data.b3_format import DATE_FORMAT, EMPTY, _number, save_deterministic

STOCKS_HEADER = (
    "Produto",
    "Instituição",
    "Conta",
    "Código de Negociação",
    "CNPJ da Empresa",
    "Código ISIN / Distribuição",
    "Tipo",
    "Escriturador",
    "Quantidade",
    "Quantidade Disponível",
    "Quantidade Indisponível",
    "Motivo",
    "Preço de Fechamento",
    "Valor Atualizado",
)
FUNDS_HEADER = tuple(
    {"CNPJ da Empresa": "CNPJ do Fundo", "Escriturador": "Administrador"}.get(h, h)
    for h in STOCKS_HEADER
)
FIXED_INCOME_HEADER = (
    "Produto",
    "Instituição",
    "Emissor",
    "Código",
    "Indexador",
    "Tipo de regime",
    "Data de Emissão",
    "Vencimento",
    "Quantidade",
    "Quantidade Disponível",
    "Quantidade Indisponível",
    "Motivo",
    "Contraparte",
    "Preço Atualizado MTM",
    "Valor Atualizado MTM",
    "Preço Atualizado CURVA",
    "Valor Atualizado CURVA",
    None,
    None,
)
INCOME_HEADER = (
    "Produto",
    "Pagamento",
    "Tipo de Evento",
    "Instituição",
    "Quantidade",
    "Preço unitário",
    "Valor líquido",
)
TRADES_HEADER = (
    "Código de Negociação",
    "Período (Inicial)",
    "Período (Final)",
    "Instituição",
    "Quantidade (Compra)",
    "Quantidade (Venda)",
    "Quantidade (Líquida)",
    "Preço Médio (Compra)",
    "Preço Médio (Venda)",
)
PRODUCT_WIDTH = 60
# Placeholders: o parser não usa estes campos, mas o formato precisa deles.
FAKE_ACCOUNT = "0000000"
FAKE_CNPJ = "00000000000000"


@dataclass(frozen=True)
class EquityPosition:
    """Linha das abas de ações e de fundos."""

    product: str
    institution: str
    ticker: str
    kind: str  # ON, PN, UNIT; "Cotas" para fundo
    custodian: str  # escriturador (ação) ou administrador (fundo)
    quantity: Decimal
    close_price: Decimal

    def cells(self) -> tuple:
        qty = _number(self.quantity)
        return (
            self.product.ljust(PRODUCT_WIDTH),
            self.institution,
            FAKE_ACCOUNT,
            self.ticker,
            FAKE_CNPJ,
            f"BR{self.ticker[:4]}XXXXX0 - 100",
            self.kind,
            self.custodian,
            qty,
            qty,
            EMPTY,
            EMPTY,
            _number(self.close_price),
            _number(self.value),
        )

    @property
    def value(self) -> Decimal:
        return (self.quantity * self.close_price).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class FixedIncomePosition:
    product: str
    institution: str
    issuer: str
    code: str
    indexer: str
    issue_date: date
    maturity: date
    quantity: Decimal
    curve_price: Decimal
    # A armadilha: valor fora da coluna CURVA, nas duas colunas sem nome.
    shifted: bool = False

    @property
    def value(self) -> Decimal:
        return (self.quantity * self.curve_price).quantize(Decimal("0.01"))

    def cells(self) -> tuple:
        qty = _number(self.quantity)
        price_value = (_number(self.curve_price), _number(self.value))
        dashes = (EMPTY, EMPTY)
        return (
            self.product,
            self.institution,
            self.issuer,
            self.code,
            self.indexer,
            "DEPOSITADO",
            self.issue_date.strftime(DATE_FORMAT),
            self.maturity.strftime(DATE_FORMAT),
            qty,
            qty,
            EMPTY,
            EMPTY,
            EMPTY,
            EMPTY,
            EMPTY,
            *(dashes + price_value if self.shifted else price_value + dashes),
        )


@dataclass(frozen=True)
class IncomeReceived:
    product: str
    payment_date: date
    event: str  # "Rendimento", "Dividendo", "Juros Sobre Capital Próprio"
    institution: str
    quantity: int
    unit_price: Decimal
    net_value: Decimal

    def cells(self) -> tuple:
        return (
            self.product,
            self.payment_date.strftime(DATE_FORMAT),
            self.event,
            self.institution,
            str(self.quantity),  # a B3 grava como texto
            _number(self.unit_price),
            _number(self.net_value),
        )


@dataclass(frozen=True)
class MonthTrades:
    ticker: str
    start: date
    institution: str
    bought: Decimal
    sold: Decimal
    avg_buy: Decimal
    avg_sell: Decimal

    def cells(self) -> tuple:
        return (
            self.ticker,
            self.start.strftime(DATE_FORMAT),
            EMPTY,
            self.institution,
            _number(self.bought),
            _number(self.sold),
            _number(self.bought - self.sold),
            _number(self.avg_buy),
            _number(self.avg_sell),
        )


@dataclass(frozen=True)
class ConsolidatedReport:
    stocks: tuple[EquityPosition, ...] = ()
    funds: tuple[EquityPosition, ...] = ()
    fixed_income: tuple[FixedIncomePosition, ...] = ()
    income: tuple[IncomeReceived, ...] = ()
    trades: tuple[MonthTrades, ...] = ()


def _total_rows(width: int, total: Decimal) -> list[tuple]:
    # Linha em branco, "Total" na última coluna e o valor embaixo.
    blank = ("",) + (None,) * (width - 1)
    pad = ("",) * (width - 1)
    return [blank, pad + ("Total",), pad + (_number(total),)]


def _fixed_income_total_rows(rows: tuple[FixedIncomePosition, ...]) -> list[tuple]:
    # Total só da coluna CURVA: os títulos com valor deslocado ficam de fora.
    curve_total = sum((r.value for r in rows if not r.shifted), Decimal("0"))
    blank = ("",) + (None,) * 18
    head = ("",) * 14
    return [
        blank,
        head + ("Total", "", "Total", None, None),
        head + (EMPTY, "", _number(curve_total), None, None),
    ]


def write_consolidated(report: ConsolidatedReport, path: Path) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    sheets = [
        ("Posição - Ações", STOCKS_HEADER, report.stocks),
        ("Posição - Fundos", FUNDS_HEADER, report.funds),
        ("Posição - Renda Fixa", FIXED_INCOME_HEADER, report.fixed_income),
        ("Proventos Recebidos", INCOME_HEADER, report.income),
        ("Negociações", TRADES_HEADER, report.trades),
    ]
    for title, header, rows in sheets:
        if not rows:
            continue
        ws = wb.create_sheet(title)
        ws.append(header)
        for row in rows:
            ws.append(row.cells())
        if rows is report.fixed_income:
            tail = _fixed_income_total_rows(rows)
        elif rows is report.income:
            tail = _total_rows(len(header), sum((r.net_value for r in rows), Decimal("0")))
            tail[0] = ("",) * len(header)  # nesta aba a linha em branco é toda ""
        elif rows is report.trades:
            tail = []  # a aba de negociações não tem Total
        else:
            tail = _total_rows(len(header), sum((r.value for r in rows), Decimal("0")))
        for row in tail:
            ws.append(row)
    save_deterministic(wb, path)
    return path
