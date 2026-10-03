"""Gabarito: as respostas certas para a história de scenario.py, calculadas À MÃO.

Não use código do app para gerar estes números. Se o mesmo código montasse a prova e o
gabarito, um erro de PM apareceria nos dois e o teste passaria assim mesmo.

Regras (Receita Federal): PM é o custo total ÷ quantidade, por investidor e ativo
(não por corretora). Compra soma ao custo; venda não muda o PM, só tira quantidade e
o custo proporcional. Resultado da venda = valor da venda − PM × quantidade vendida.
O extrato da B3 não traz corretagem, então aqui o custo é só o valor da operação.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal as D


@dataclass(frozen=True)
class Position:
    """Custo da posição: quanto foi pago pelo que sobrou, não quanto vale hoje.

    O valor atual (cotação, preço do Tesouro, marcação na curva) e o rendimento
    acumulado (valor atual − custo) entram no gabarito na v0.2/v0.3.
    """

    quantity: D
    total_cost: D
    average_price: D


@dataclass(frozen=True)
class Sale:
    date: date
    ticker: str
    quantity: D
    proceeds: D  # valor da venda
    cost: D  # PM × quantidade vendida
    result: D  # proceeds − cost (negativo = prejuízo)


# Custo da posição depois de todas as operações.
#   WEGE3: 100 × 35 = 3.500 + 100 × 27 = 2.700 → 200 por 6.200, PM 31,00.
#          Aluguel de 100 (set a dez/2022): sai e volta, NÃO mexe na posição nem no
#          PM. O preço do retorno (R$ 29) é só referência, não é compra.
#          Venda de 50: custo 50 × 31 = 1.550; sobram 150 por 4.650, PM 31,00.
#   CVCB3: zerada.
#   BBAS3: 2 × (100 × 30) = 6.000 → 200 por 6.000, PM 30,00.
#          Desdobro 1:2: +200 → 400 pelo mesmo custo de 6.000, PM 15,00.
#   CVCB1: 24 direitos recebidos de graça e expirados: sem custo, sem resultado.
#   MGLU3: 1.005 × 2 = 2.010. Grupamento 10:1 → 100,5 pelo mesmo custo, PM 20,00.
#          Fração de 0,5 sai com custo 0,5 × 20 = 10,00; sobram 100 por 2.000.
#          Vendida (ver SALES).
#   ITSA4: 200 × 10 = 2.000. Bonificação de 10 × 13,55518731 = 135,55 (ao centavo)
#          → 210 por 2.135,55, PM ≈ 10,17. Vendida (ver SALES).
#   BHIA3: 1.000 VIIA3 × 2 = 2.000; a troca de ticker não mexe em nada (mesmo ativo,
#          mesmo PM). Vendida (ver SALES).
POSITIONS = {
    "WEGE3": Position(D("150"), D("4650.00"), D("31.00")),
    "BBAS3": Position(D("400"), D("6000.00"), D("15.00")),
    # 100 × 150 = 15.000. Rendimentos não mexem no PM. Subscrição da 8ª emissão: 23 ×
    # 162,74 = 3.743,02 (a taxa de distribuição é custo). 123 por 18.743,02, PM
    # 152,38 (18.743,02 ÷ 123 = 152,3823). Recibo e atualização são a mesma cota.
    "KNRI11": Position(D("123"), D("18743.02"), D("152.38")),
}

# Custódia (onde está) é outra dimensão do custo (quanto custou). A transferência de
# 05/08/2024 leva as 150 WEGE3 para a corretora B; o PM continua 31,00.
CUSTODY = {
    "WEGE3": {"EXEMPLAR INVESTIMENTOS CTVM S.A.": D("150")},
    "BBAS3": {"FICTICIA CORRETORA DE VALORES S/A": D("400")},
    "KNRI11": {"EXEMPLAR INVESTIMENTOS CTVM S.A.": D("123")},
}

SALES = [
    # 50 × 39 = 1.950 − 1.550 = lucro de 400.
    Sale(date(2023, 8, 10), "WEGE3", D("50"), D("1950.00"), D("1550.00"), D("400.00")),
    # 200 × 12,50 = 2.500 − 200 × 20 = 4.000 → prejuízo de 1.500.
    Sale(date(2022, 3, 14), "CVCB3", D("200"), D("2500.00"), D("4000.00"), D("-1500.00")),
    # Leilão da fração: 6,50 − 10,00 = prejuízo de 3,50. Para o IR, é uma venda.
    Sale(date(2024, 7, 8), "MGLU3", D("0.5"), D("6.50"), D("10.00"), D("-3.50")),
    # 100 × 9 = 900 − 2.000 = prejuízo de 1.100.
    Sale(date(2025, 2, 17), "MGLU3", D("100"), D("900.00"), D("2000.00"), D("-1100.00")),
    # 210 × 11 = 2.310 − 2.135,55 = lucro de 174,45. Com custo zero na bonificação
    # (erro comum), o lucro sairia 310,00 e o IR seria maior.
    Sale(date(2025, 6, 16), "ITSA4", D("210"), D("2310.00"), D("2135.55"), D("174.45")),
    # 1.000 × 0,70 = 700 − 2.000 = prejuízo de 1.300, já com o ticker novo.
    Sale(date(2023, 11, 20), "BHIA3", D("1000"), D("700.00"), D("2000.00"), D("-1300.00")),
    # 1.000 × 28 = 28.000 − 1.000 × 25 = lucro de 3.000.
    Sale(date(2023, 5, 15), "PETR4", D("1000"), D("28000.00"), D("25000.00"), D("3000.00")),
]


@dataclass(frozen=True)
class MonthSales:
    """Vendas de ações no mês. Até R$ 20 mil, o lucro é isento (Lei 9.250/95)."""

    month: str  # "AAAA-MM"
    total_sales: D
    exempt: bool


# Só ações (FII não tem isenção). Leilão de fração entra no total do mês.
STOCK_SALES_BY_MONTH = [
    MonthSales("2022-03", D("2500.00"), True),  # CVCB3
    MonthSales("2023-05", D("28000.00"), False),  # PETR4: acima de 20 mil, lucro tributável
    MonthSales("2023-08", D("1950.00"), True),  # WEGE3
    MonthSales("2023-11", D("700.00"), True),  # BHIA3
    MonthSales("2024-07", D("6.50"), True),  # leilão da fração de MGLU3
    MonthSales("2025-02", D("900.00"), True),  # MGLU3
    MonthSales("2025-06", D("2310.00"), True),  # ITSA4
]


@dataclass(frozen=True)
class Income:
    date: date
    ticker: str
    kind: str  # JCP, DIVIDENDO, RENDIMENTO
    gross: D
    tax_withheld: D
    net: D


# JCP: bruto = quantidade × valor por ação; IR de 15% retido; o extrato mostra o líquido.
INCOME = [
    Income(date(2022, 3, 10), "BBAS3", "JCP", D("100.00"), D("15.00"), D("85.00")),
    Income(date(2023, 3, 10), "BBAS3", "DIVIDENDO", D("80.00"), D("0.00"), D("80.00")),
    Income(date(2024, 6, 10), "BBAS3", "JCP", D("100.00"), D("15.00"), D("85.00")),
    Income(date(2022, 8, 10), "WEGE3", "JCP", D("20.00"), D("3.00"), D("17.00")),
    Income(date(2022, 11, 10), "WEGE3", "JCP", D("15.00"), D("2.25"), D("12.75")),
    Income(date(2022, 2, 15), "KNRI11", "RENDIMENTO", D("100.00"), D("0.00"), D("100.00")),
    Income(date(2022, 3, 15), "KNRI11", "RENDIMENTO", D("100.00"), D("0.00"), D("100.00")),
    Income(date(2022, 4, 14), "KNRI11", "RENDIMENTO", D("100.00"), D("0.00"), D("100.00")),
    Income(date(2024, 3, 15), "KNRI11", "RENDIMENTO", D("110.00"), D("0.00"), D("110.00")),
]


@dataclass(frozen=True)
class LoanIncome:
    date: date
    ticker: str
    kind: str  # "REMUNERACAO" (aluguel) ou "REEMBOLSO" (provento pago pelo tomador)
    amount: D


# O aluguel não gera venda: a lista SALES continua só com as vendas de verdade.
LOAN_INCOME = [
    LoanIncome(date(2022, 11, 10), "WEGE3", "REEMBOLSO", D("15.00")),
    LoanIncome(date(2022, 12, 5), "WEGE3", "REMUNERACAO", D("18.00")),
]


# Renda fixa: custo da posição e resultado bruto (antes do IR). Marcação na curva e
# IR regressivo ficam para a v0.3. Cada título é um ativo próprio.
#   CDB: 5 × 1.000 = 5.000. Resgate de 2 a 1.120 = 2.240 − 2 × 1.000 = 240 de
#        rendimento bruto; sobram 3 por 3.000.
#   LCA: 3 × 1.000 = 3.000, mantida.
#   Tesouro Selic: 0,5 × 13.000 = 6.500. Venda de 0,2 a 14.500 = 2.900 − 0,2 × 13.000
#        = 2.600 → 300 de rendimento; sobram 0,3 por 3.900.
#   Tesouro IPCA+ juros semestrais: 1 × 4.000 = 4.000; cupom de 100 é rendimento e
#        não mexe no custo.
FIXED_INCOME_POSITIONS = {
    "CDB - 23C01234567 - BANCO EXEMPLO S/A": Position(D("3"), D("3000.00"), D("1000.00")),
    "LCA - 23F00765432 - BANCO EXEMPLO S/A": Position(D("3"), D("3000.00"), D("1000.00")),
    "Tesouro Selic 2029": Position(D("0.3"), D("3900.00"), D("13000.00")),
    "Tesouro IPCA+ com Juros Semestrais 2035": Position(D("1"), D("4000.00"), D("4000.00")),
}


@dataclass(frozen=True)
class Redemption:
    date: date
    product: str
    received: D
    cost: D  # custo da parte resgatada ou vendida
    gain: D  # rendimento bruto


FIXED_INCOME_REDEMPTIONS = [
    Redemption(
        date(2024, 3, 1),
        "CDB - 23C01234567 - BANCO EXEMPLO S/A",
        D("2240.00"),
        D("2000.00"),
        D("240.00"),
    ),
    Redemption(date(2024, 4, 4), "Tesouro Selic 2029", D("2900.00"), D("2600.00"), D("300.00")),
]

# Cupom do Tesouro IPCA+ com juros: rendimento, não mexe no custo.
FIXED_INCOME_COUPONS = [
    (date(2023, 5, 15), "Tesouro IPCA+ com Juros Semestrais 2035", D("100.00")),
]


# Conciliação com o consolidado de 31/03/2024. Quantidade calculada pelo extrato até
# essa data × quantidade informada pela B3:
#   BBAS3 200 (desdobro só em abril) | WEGE3 150 (ainda na corretora A) | MGLU3 1.005
#   (grupamento só em maio) | ITSA4 200 | KNRI11 100 | CDB 3 (2 resgatados em 01/03)
#   | LCA 3.
# Só MGLU3 diverge: calculado 1.005, informado 1.000.
RECONCILIATION_DATE = date(2024, 3, 31)
RECONCILIATION_DIVERGENCES = {"MGLU3": (D("1005"), D("1000"))}  # (calculado, informado)

# Armadilha do Total da renda fixa: a aba soma só a coluna CURVA. O CDB (3 × 1.105,37
# = 3.316,11) entra; a LCA (3 × 1.045,12 = 3.135,36), com valor deslocado, fica fora.
# O Total informado é 3.316,11, quando o certo seria 6.451,47.
FIXED_INCOME_SHEET_TOTAL = D("3316.11")
FIXED_INCOME_TRUE_TOTAL = D("6451.47")
