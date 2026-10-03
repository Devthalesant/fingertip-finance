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


# Posição depois de todas as operações.
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
