"""Investidor fictício muito ativo, para medir tempo (ADR 0004: medir antes de otimizar).

Não tem gabarito: serve só para volume. Dez anos, 20 ativos inventados, compras quase
todo dia útil, vendas e dividendos. Determinístico (mesma semente → mesmo arquivo).
Os códigos começam com VLM para não lembrar nenhum ticker real.
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from sample_data.b3_format import Movement, StatementRow
from sample_data.scenario import BROKER_A, Asset, buy, income, sell

ASSETS = [Asset(f"VLM{chr(65 + i)}3", f"EMPRESA FICTICIA {chr(65 + i)} S/A") for i in range(20)]


def volume_rows(years: int = 10, buys_per_month: int = 200, seed: int = 42) -> list[StatementRow]:
    rng = random.Random(seed)
    broker = BROKER_A.spellings[0]
    holdings = dict.fromkeys(ASSETS, 0)
    rows: list[StatementRow] = []
    start = date(2016, 1, 1)
    for month in range(years * 12):
        first = date(start.year + (start.month - 1 + month) // 12, (month % 12) + 1, 1)
        for _ in range(buys_per_month):
            day = first + timedelta(days=rng.randrange(28))
            asset = rng.choice(ASSETS)
            quantity = rng.randrange(1, 50)
            rows.append(buy(day, asset, quantity, _price(rng), broker))
            holdings[asset] += quantity
        for asset in ASSETS:
            if holdings[asset] > 100 and rng.random() < 0.5:
                quantity = rng.randrange(1, holdings[asset] // 2)
                rows.append(sell(first + timedelta(days=28), asset, quantity, _price(rng), broker))
                holdings[asset] -= quantity
            if month % 3 == 2 and holdings[asset]:
                rows.append(
                    income(
                        first + timedelta(days=27),
                        Movement.DIVIDENDO,
                        asset,
                        holdings[asset],
                        "0.25",
                        broker,
                    )
                )
    return rows


def _price(rng: random.Random) -> str:
    return str(Decimal(rng.randrange(1000, 9000)) / 100)
