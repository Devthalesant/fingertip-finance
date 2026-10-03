"""A história do investidor fictício, contada em operações.

Quantidades, preços e datas das operações são inventados e não têm relação com
nenhuma carteira real. Tickers, nomes de empresa e eventos corporativos são reais e
públicos (proporção, custo atribuído e preço de subscrição conferidos em fonte
oficial); a data em que o evento aparece no extrato é aproximada. Os números são redondos de
propósito: o gabarito (expected.py) é conferido à mão.

Cada grupo de cenários é uma função que devolve as linhas do extrato. A história
completa é a soma dos grupos.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sample_data.b3_format import Direction, Movement, StatementRow


@dataclass(frozen=True)
class Investor:
    email: str
    display_name: str


@dataclass(frozen=True)
class Broker:
    """Corretora fictícia. A primeira grafia é a canônica; as outras são variações que
    a B3 usa no mesmo extrato (ponto final, espaço duplo)."""

    spellings: tuple[str, ...]

    @property
    def name(self) -> str:
        return self.spellings[0]


@dataclass(frozen=True)
class Asset:
    ticker: str
    b3_name: str

    @property
    def product(self) -> str:
        return f"{self.ticker} - {self.b3_name}"


# example.com é um domínio reservado para exemplos: nunca pertence a ninguém.
INVESTOR = Investor(email="demo@example.com", display_name="Investidor Demo")

BROKER_A = Broker(("FICTICIA CORRETORA DE VALORES S/A", "FICTICIA CORRETORA DE VALORES S/A."))
BROKER_B = Broker(("EXEMPLAR INVESTIMENTOS CTVM S.A.", "EXEMPLAR INVESTIMENTOS  CTVM S.A."))

WEGE3 = Asset("WEGE3", "WEG S/A")
CVCB3 = Asset("CVCB3", "CVC BRASIL OPERADORA E AGÊNCIA DE VIAGENS S/A")
BBAS3 = Asset("BBAS3", "BANCO DO BRASIL S/A")
CVCB1 = Asset("CVCB1", "CVC BRASIL OPERADORA E AGÊNCIA DE VIAGENS S/A")
MGLU3 = Asset("MGLU3", "MAGAZINE LUIZA S/A")
ITSA4 = Asset("ITSA4", "ITAUSA S/A")
VIIA3 = Asset("VIIA3", "VIA S/A")
BHIA3 = Asset("BHIA3", "GRUPO CASAS BAHIA S/A")


def _trade(
    direction: Direction, day: date, asset: Asset, quantity: int, price: str, institution: str
) -> StatementRow:
    unit_price = Decimal(price)
    return StatementRow(
        direction=direction,
        date=day,
        movement=Movement.LIQUIDACAO,
        product=asset.product,
        institution=institution,
        quantity=Decimal(quantity),
        unit_price=unit_price,
        amount=(unit_price * quantity).quantize(Decimal("0.01")),
    )


def buy(day: date, asset: Asset, quantity: int, price: str, institution: str) -> StatementRow:
    return _trade(Direction.CREDIT, day, asset, quantity, price, institution)


def sell(day: date, asset: Asset, quantity: int, price: str, institution: str) -> StatementRow:
    return _trade(Direction.DEBIT, day, asset, quantity, price, institution)


def event(
    day: date,
    movement: Movement,
    asset: Asset,
    quantity: str,
    institution: str,
    direction: Direction = Direction.CREDIT,
) -> StatementRow:
    """Evento sem dinheiro (desdobro, bonificação, direito...): sem preço nem valor."""
    return StatementRow(direction, day, movement, asset.product, institution, Decimal(quantity))


def lend(
    asset: Asset,
    quantity: int,
    institution: str,
    start: date,
    end: date,
    return_price: str,
    fee: tuple[date, str],
    reimbursements: tuple[tuple[date, str], ...] = (),
) -> list[StatementRow]:
    """Aluguel (doador): uma operação da história vira várias linhas do extrato.

    Na B3, a saída e o retorno usam o mesmo rótulo da compra e venda. O que denuncia o
    aluguel: o par de "Transferência" interna no mesmo dia e corretora, a saída sem
    preço, e o retorno da mesma quantidade depois. Nada disso mexe no PM.
    """
    qty = Decimal(quantity)
    common = {"product": asset.product, "institution": institution, "quantity": qty}
    price = Decimal(return_price)
    rows = [
        # Ações saem da carteira livre para a de aluguel (par interno, sem valor).
        StatementRow(Direction.DEBIT, start, Movement.TRANSFERENCIA, **common),
        StatementRow(Direction.CREDIT, start, Movement.TRANSFERENCIA, **common),
        # Registro do contrato: crédito, sem preço nem valor.
        StatementRow(Direction.CREDIT, start, Movement.EMPRESTIMO, **common),
        # Saída das ações para o tomador: mesmo rótulo da venda, mas sem preço.
        StatementRow(Direction.DEBIT, start, Movement.LIQUIDACAO, **common),
        # Retorno: mesmo rótulo da compra; o preço é só referência, não é custo.
        StatementRow(
            Direction.CREDIT,
            end,
            Movement.LIQUIDACAO,
            unit_price=price,
            amount=(price * qty).quantize(Decimal("0.01")),
            **common,
        ),
        # Remuneração do aluguel, paga pelo tomador.
        StatementRow(
            Direction.CREDIT, fee[0], Movement.EMPRESTIMO, amount=Decimal(fee[1]), **common
        ),
    ]
    # Provento pago durante o aluguel: quem recebe da empresa é o tomador, que
    # reembolsa o doador. Não é dividendo comum.
    rows += [
        StatementRow(Direction.CREDIT, day, Movement.REEMBOLSO, amount=Decimal(value), **common)
        for day, value in reimbursements
    ]
    return rows


def trades() -> list[StatementRow]:
    """Compras e vendas: lucro, prejuízo e linhas idênticas no mesmo dia."""
    a, a_dot = BROKER_A.spellings
    return [
        # WEGE3: duas compras a preços diferentes, depois venda parcial com lucro. A
        # primeira compra é posterior ao desdobro real de 27/04/2021, de propósito.
        buy(date(2021, 5, 17), WEGE3, 100, "35.00", a),
        buy(date(2022, 6, 20), WEGE3, 100, "27.00", a_dot),
        sell(date(2023, 8, 10), WEGE3, 50, "39.00", a),
        # CVCB3: compra e venda total com prejuízo.
        buy(date(2021, 5, 10), CVCB3, 200, "20.00", a),
        sell(date(2022, 3, 14), CVCB3, 200, "12.50", a),
        # BBAS3: a ordem foi executada em duas partes iguais, no mesmo dia e preço. São
        # duas linhas idênticas e legítimas; nenhuma pode ser descartada como duplicata.
        buy(date(2021, 8, 2), BBAS3, 100, "30.00", a),
        buy(date(2021, 8, 2), BBAS3, 100, "30.00", a),
    ]


def loans() -> list[StatementRow]:
    """Aluguel de WEGE3 (doador), com remuneração e reembolso de provento."""
    return lend(
        WEGE3,
        100,
        BROKER_A.name,
        start=date(2022, 9, 1),
        end=date(2022, 12, 1),
        return_price="29.00",
        fee=(date(2022, 12, 5), "18.00"),
        reimbursements=((date(2022, 11, 10), "15.00"),),
    )


def corporate_events() -> list[StatementRow]:
    """Desdobro, grupamento com fração, bonificação, troca de ticker e direito expirado.

    Todos reais. Fontes: avisos aos acionistas e fatos relevantes de cada empresa.
    """
    a = BROKER_A.name
    b, b_double_space = BROKER_B.spellings
    return [
        # CVC, aumento de capital de 2021: 0,1247884739 direito por ação, data com
        # 24/06/2021, exercício até 26/07/2021 a R$ 19,12. 200 × 0,1248 = 24,96 → 24
        # direitos (fração de direito não é creditada). O investidor não exerce.
        event(date(2021, 6, 29), Movement.DIREITO, CVCB1, "24", a),
        event(
            date(2021, 7, 27),
            Movement.SUBSCRICAO_NAO_EXERCIDA,
            CVCB1,
            "24",
            a,
            Direction.DEBIT,
        ),
        # Banco do Brasil, desdobro 1:2 (data-base 15/04/2024). A linha traz só as
        # ações recebidas: 200 → +200.
        event(date(2024, 4, 16), Movement.DESDOBRO, BBAS3, "200", a),
        # Magazine Luiza, grupamento 10:1 (agrupada a partir de 27/05/2024). A linha traz
        # a quantidade resultante, com a fração; a fração sai e vai a leilão.
        buy(date(2023, 10, 16), MGLU3, 1005, "2.00", a),
        event(date(2024, 5, 27), Movement.GRUPAMENTO, MGLU3, "100.5", a),
        event(date(2024, 5, 27), Movement.FRACAO, MGLU3, "0.5", a, Direction.DEBIT),
        StatementRow(
            Direction.CREDIT,
            date(2024, 7, 8),
            Movement.LEILAO_FRACAO,
            MGLU3.product,
            a,
            Decimal("0.5"),
            unit_price=Decimal("13.00"),
            amount=Decimal("6.50"),
        ),
        sell(date(2025, 2, 17), MGLU3, 100, "9.00", a),
        # Itaúsa, bonificação de 5 por 100 (data com 02/12/2024, crédito 04/12/2024),
        # custo atribuído R$ 13,55518731 por ação. Vendida antes da bonificação de 2025.
        buy(date(2024, 3, 11), ITSA4, 200, "10.00", b_double_space),
        event(date(2024, 12, 4), Movement.BONIFICACAO, ITSA4, "10", b),
        sell(date(2025, 6, 16), ITSA4, 210, "11.00", b),
        # Via → Grupo Casas Bahia, troca de ticker em 20/09/2023: só um crédito de
        # "Atualização" no ticker novo. Vendida antes do grupamento 25:1 de dez/2023.
        buy(date(2023, 6, 1), VIIA3, 1000, "2.00", b),
        event(date(2023, 9, 20), Movement.ATUALIZACAO, BHIA3, "1000", b),
        sell(date(2023, 11, 20), BHIA3, 1000, "0.70", b),
    ]


def movement_rows() -> list[StatementRow]:
    """Todas as linhas do extrato de movimentação, de todos os grupos."""
    return trades() + loans() + corporate_events()
