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

from sample_data.b3_consolidated import (
    ConsolidatedReport,
    EquityPosition,
    FixedIncomePosition,
    IncomeReceived,
    MonthTrades,
)
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
        # Tesouro não tem "TICKER - NOME": o produto é o próprio nome do título.
        return f"{self.ticker} - {self.b3_name}" if self.b3_name else self.ticker


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
PETR4 = Asset("PETR4", "PETROLEO BRASILEIRO S/A PETROBRAS")
KNRI11 = Asset("KNRI11", "KINEA RENDA IMOBILIÁRIA FDO INV IMOB - FII")
KNRI12 = Asset("KNRI12", "KINEA RENDA IMOBILIÁRIA FDO INV IMOB - FII")  # direito
KNRI13 = Asset("KNRI13", "KINEA RENDA IMOBILIÁRIA FDO INV IMOB - FII")  # recibo

# Renda fixa: o "Produto" segue outro padrão. Título privado: "TIPO - CÓDIGO - EMISSOR";
# Tesouro: nome por extenso com o ano. O emissor é fictício; o código segue o formato
# dos códigos da B3 (inventado).
CDB_EXEMPLO = Asset("CDB", "23C01234567 - BANCO EXEMPLO S/A")
LCA_EXEMPLO = Asset("LCA", "23F00765432 - BANCO EXEMPLO S/A")
TESOURO_SELIC = Asset("Tesouro Selic 2029", "")
TESOURO_IPCA_JUROS = Asset("Tesouro IPCA+ com Juros Semestrais 2035", "")

# JCP tem 15% de IR retido na fonte. Na linha da B3, o preço é o valor bruto por ação
# e o "Valor da Operação" já vem líquido. Dividendo e rendimento de FII vêm brutos.
JCP_NET_FACTOR = Decimal("0.85")


def _trade(
    direction: Direction,
    day: date,
    asset: Asset,
    quantity: int | str,
    price: str,
    institution: str,
    movement: Movement = Movement.LIQUIDACAO,
) -> StatementRow:
    unit_price = Decimal(price)
    qty = Decimal(quantity)
    return StatementRow(
        direction=direction,
        date=day,
        movement=movement,
        product=asset.product,
        institution=institution,
        quantity=qty,
        unit_price=unit_price,
        amount=(unit_price * qty).quantize(Decimal("0.01")),
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


def income(
    day: date, movement: Movement, asset: Asset, quantity: int, per_share: str, institution: str
) -> StatementRow:
    """Provento em dinheiro: quantidade na data com × valor por ação."""
    price = Decimal(per_share)
    gross = price * quantity
    net = gross * JCP_NET_FACTOR if movement is Movement.JCP else gross
    return StatementRow(
        Direction.CREDIT,
        day,
        movement,
        asset.product,
        institution,
        Decimal(quantity),
        unit_price=price,
        amount=net.quantize(Decimal("0.01")),
    )


def transfer(
    day: date, asset: Asset, quantity: int, source: str, target: str
) -> list[StatementRow]:
    """Transferência de custódia entre corretoras: sai de uma, entra na outra, sem valor.

    Mesmo rótulo do par interno do aluguel; a diferença é que aqui as corretoras são
    diferentes. Não é compra nem venda: o PM não muda.
    """
    qty = Decimal(quantity)
    return [
        StatementRow(Direction.DEBIT, day, Movement.TRANSFERENCIA, asset.product, source, qty),
        StatementRow(Direction.CREDIT, day, Movement.TRANSFERENCIA, asset.product, target, qty),
    ]


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


def transfers() -> list[StatementRow]:
    """WEGE3 muda de corretora (A → B) com a posição inteira."""
    return transfer(date(2024, 8, 5), WEGE3, 150, BROKER_A.name, BROKER_B.spellings[1])


def dividends() -> list[StatementRow]:
    """Proventos: JCP (líquido na linha), dividendo e rendimento mensal de FII.

    Valores por ação inventados (redondos); datas plausíveis para cada empresa.
    """
    a, b = BROKER_A.name, BROKER_B.name
    return [
        # BBAS3: JCP e dividendo antes do desdobro (200 ações) e JCP depois (400).
        income(date(2022, 3, 10), Movement.JCP, BBAS3, 200, "0.50", a),
        income(date(2023, 3, 10), Movement.DIVIDENDO, BBAS3, 200, "0.40", a),
        income(date(2024, 6, 10), Movement.JCP, BBAS3, 400, "0.25", a),
        # WEGE3: JCP com 200 ações; e o de nov/2022, durante o aluguel, só sobre as 100
        # que ficaram (as outras 100 rendem o reembolso pago pelo tomador).
        income(date(2022, 8, 10), Movement.JCP, WEGE3, 200, "0.10", a),
        income(date(2022, 11, 10), Movement.JCP, WEGE3, 100, "0.15", a),
        # KNRI11: comprado em jan/2022, três rendimentos mensais (isentos para PF).
        buy(date(2022, 1, 10), KNRI11, 100, "150.00", b),
        income(date(2022, 2, 15), Movement.RENDIMENTO, KNRI11, 100, "1.00", b),
        income(date(2022, 3, 15), Movement.RENDIMENTO, KNRI11, 100, "1.00", b),
        income(date(2022, 4, 14), Movement.RENDIMENTO, KNRI11, 100, "1.00", b),
        # Aparece também no consolidado de março/2024.
        income(date(2024, 3, 15), Movement.RENDIMENTO, KNRI11, 100, "1.10", b),
    ]


def fixed_income() -> list[StatementRow]:
    """CDB, LCA e Tesouro, com os rótulos próprios da renda fixa.

    Tesouro tem quantidade fracionada (frações de título). O resgate e a venda trazem o
    valor recebido; o rendimento é a diferença para o custo daquela parte.
    """
    b = BROKER_B.name
    credit, debit = Direction.CREDIT, Direction.DEBIT
    return [
        # CDB de liquidez diária: aplicação de 5 títulos e resgate antecipado de 2.
        _trade(credit, date(2023, 3, 1), CDB_EXEMPLO, 5, "1000.00", b, Movement.COMPRA_VENDA),
        _trade(debit, date(2024, 3, 1), CDB_EXEMPLO, 2, "1120.00", b, Movement.RESGATE_ANTECIPADO),
        # LCA: aplicação mantida (isenta de IR para PF).
        _trade(credit, date(2023, 6, 1), LCA_EXEMPLO, 3, "1000.00", b, Movement.COMPRA_VENDA),
        # Tesouro Selic: compra de meio título e venda de 0,2.
        _trade(credit, date(2022, 4, 4), TESOURO_SELIC, "0.5", "13000.00", b, Movement.COMPRA),
        _trade(debit, date(2024, 4, 4), TESOURO_SELIC, "0.2", "14500.00", b, Movement.VENDA),
        # Tesouro IPCA+ com juros semestrais: compra de 1 título e um cupom.
        _trade(credit, date(2023, 1, 10), TESOURO_IPCA_JUROS, "1", "4000.00", b, Movement.COMPRA),
        _trade(credit, date(2023, 5, 15), TESOURO_IPCA_JUROS, "1", "100.00", b, Movement.JUROS),
    ]


def big_sales_month() -> list[StatementRow]:
    """Mês com vendas de ações acima de R$ 20 mil: o lucro deixa de ser isento."""
    a = BROKER_A.name
    return [
        buy(date(2023, 2, 6), PETR4, 1000, "25.00", a),
        sell(date(2023, 5, 15), PETR4, 1000, "28.00", a),
    ]


def movement_rows() -> list[StatementRow]:
    """Todas as linhas do extrato de movimentação, de todos os grupos."""
    groups = (
        trades,
        loans,
        corporate_events,
        transfers,
        dividends,
        big_sales_month,
        fixed_income,
        subscriptions,
    )
    return [row for group in groups for row in group()]


def subscriptions() -> list[StatementRow]:
    """Direito exercido: 8ª emissão do KNRI11 (fonte: comunicado da oferta).

    Data de corte 26/03/2024, fator 0,237397742885, exercício de 28/03 a 10/04/2024,
    R$ 159,55 + R$ 3,19 de taxa de distribuição = R$ 162,74 por cota. Com 100 cotas:
    100 × 0,2374 = 23,74 → 23 direitos, todos exercidos.

    Caminho no extrato: direito recebido → solicitação (o direito sai) → exercido (o
    pagamento) → recibo (KNRI13) → atualização (o recibo vira cota). A cota nova entra
    uma vez só: contar o recibo E a atualização dobraria a quantidade.
    """
    b = BROKER_B.name
    price = Decimal("162.74")
    return [
        event(date(2024, 3, 28), Movement.DIREITO, KNRI12, "23", b),
        event(date(2024, 3, 28), Movement.SUBSCRICAO_SOLICITADA, KNRI12, "23", b, Direction.DEBIT),
        StatementRow(
            Direction.DEBIT,
            date(2024, 4, 11),
            Movement.SUBSCRICAO_EXERCIDA,
            KNRI12.product,
            b,
            Decimal("23"),
            unit_price=price,
            amount=price * 23,
        ),
        event(date(2024, 4, 15), Movement.RECIBO_SUBSCRICAO, KNRI13, "23", b),
        event(date(2024, 5, 20), Movement.ATUALIZACAO, KNRI11, "23", b),
    ]


def consolidated_march_2024() -> ConsolidatedReport:
    """Consolidado mensal de 31/03/2024: o gabarito da conciliação.

    Divergência proposital: a B3 informa 1.000 MGLU3, mas o extrato soma 1.005. O app
    precisa sinalizar. Preços de fechamento inventados.
    """
    a, b = BROKER_A.name, BROKER_B.name
    escriturador = "BANCO ESCRITURADOR FICTICIO S/A"

    def stock(asset: Asset, broker: str, kind: str, quantity: str, close: str):
        return EquityPosition(
            asset.product,
            broker,
            asset.ticker,
            kind,
            escriturador,
            Decimal(quantity),
            Decimal(close),
        )

    return ConsolidatedReport(
        stocks=(
            stock(BBAS3, a, "ON", "200", "56.37"),
            stock(WEGE3, a, "ON", "150", "38.12"),
            stock(MGLU3, a, "ON", "1000", "2.13"),  # divergência: o extrato soma 1.005
            stock(ITSA4, b, "PN", "200", "10.41"),
        ),
        funds=(
            EquityPosition(
                KNRI11.product,
                b,
                KNRI11.ticker,
                "Cotas",
                "ADMINISTRADOR FICTICIO DTVM S/A",
                Decimal("100"),
                Decimal("158.40"),
            ),
        ),
        fixed_income=(
            FixedIncomePosition(
                "CDB - BANCO EXEMPLO S/A",
                b,
                "BANCO EXEMPLO S/A",
                "23C01234567",
                "DI",
                date(2023, 3, 1),
                date(2026, 3, 2),
                Decimal("3"),
                Decimal("1105.37"),
            ),
            # Valor nas colunas sem nome: o Total da aba não inclui esta LCA.
            FixedIncomePosition(
                "LCA - BANCO EXEMPLO S/A",
                b,
                "BANCO EXEMPLO S/A",
                "23F00765432",
                "DI",
                date(2023, 6, 1),
                date(2025, 6, 2),
                Decimal("3"),
                Decimal("1045.12"),
                shifted=True,
            ),
        ),
        income=(
            IncomeReceived(
                KNRI11.product,
                date(2024, 3, 15),
                "Rendimento",
                b,
                100,
                Decimal("1.10"),
                Decimal("110.00"),
            ),
        ),
        trades=(
            MonthTrades(
                ITSA4.ticker,
                date(2024, 3, 11),
                b,
                Decimal("200"),
                Decimal("0"),
                Decimal("10.00"),
                Decimal("0"),
            ),
        ),
    )
