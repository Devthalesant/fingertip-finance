"""Catálogo e eventos curados da história sintética: o que o admin cadastraria.

É entrada da prova, não gabarito: diz ao app quem é quem (classe de cada ativo,
corretoras) e o que a B3 não explica (troca de ticker, custo da bonificação, oferta de
subscrição). Fontes dos eventos: comentários de scenario.py.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Asset, CorporateEvent, Institution, SubscriptionOffer
from app.models.enums import AssetClass, CorporateEventType, InstitutionKind
from sample_data import scenario as s

C = AssetClass

BANK = "BANCO EXEMPLO S/A"

# (código, nome, classe, código do ativo de origem para direito/recibo)
ASSETS = [
    (s.WEGE3.ticker, s.WEGE3.b3_name, C.ACAO, None),
    (s.CVCB3.ticker, s.CVCB3.b3_name, C.ACAO, None),
    (s.CVCB1.ticker, s.CVCB1.b3_name, C.DIREITO_SUBSCRICAO, s.CVCB3.ticker),
    (s.BBAS3.ticker, s.BBAS3.b3_name, C.ACAO, None),
    (s.MGLU3.ticker, s.MGLU3.b3_name, C.ACAO, None),
    (s.ITSA4.ticker, s.ITSA4.b3_name, C.ACAO, None),
    (s.VIIA3.ticker, s.VIIA3.b3_name, C.ACAO, None),
    (s.BHIA3.ticker, s.BHIA3.b3_name, C.ACAO, None),
    (s.PETR4.ticker, s.PETR4.b3_name, C.ACAO, None),
    (s.KNRI11.ticker, s.KNRI11.b3_name, C.FII, None),
    (s.KNRI12.ticker, s.KNRI12.b3_name, C.DIREITO_SUBSCRICAO, s.KNRI11.ticker),
    (s.KNRI13.ticker, s.KNRI13.b3_name, C.RECIBO_SUBSCRICAO, s.KNRI11.ticker),
    ("23C01234567", f"CDB - {BANK}", C.RENDA_FIXA, None),
    ("23F00765432", f"LCA - {BANK}", C.RENDA_FIXA, None),
    (s.TESOURO_SELIC.ticker, None, C.TESOURO, None),
    (s.TESOURO_IPCA_JUROS.ticker, None, C.TESOURO, None),
]


def seed_story_catalog(session: Session) -> None:
    """Grava instituições, ativos e eventos da história. Para banco vazio (testes)."""
    session.add_all(
        [
            Institution(name=s.BROKER_A.name, kind=InstitutionKind.BROKER),
            Institution(name=s.BROKER_B.name, kind=InstitutionKind.BROKER),
            Institution(name=BANK, kind=InstitutionKind.BANK),
        ]
    )
    assets: dict[str, Asset] = {}
    for code, name, asset_class, underlying in ASSETS:
        asset = Asset(canonical_code=code, name=name, asset_class=asset_class)
        if underlying is not None:
            asset.underlying_asset_id = assets[underlying].id
        session.add(asset)
        session.flush()
        assets[code] = asset

    def event(kind, day, source, ratio_from, ratio_to, target=None, cost=None, notes=None):
        return CorporateEvent(
            event_type=kind,
            ex_date=day,
            source_asset_id=assets[source].id,
            target_asset_id=assets[target].id if target else None,
            ratio_from=Decimal(ratio_from),
            ratio_to=Decimal(ratio_to),
            cost_per_unit=None if cost is None else Decimal(cost),
            notes=notes,
        )

    E = CorporateEventType
    session.add_all(
        [
            event(
                E.TROCA_TICKER,
                date(2023, 9, 20),
                "VIIA3",
                1,
                1,
                target="BHIA3",
                notes="Via → Grupo Casas Bahia",
            ),
            event(E.DESDOBRO, date(2024, 4, 15), "BBAS3", 1, 2, notes="data-base 15/04/2024"),
            event(E.GRUPAMENTO, date(2024, 5, 27), "MGLU3", 10, 1),
            event(
                E.BONIFICACAO,
                date(2024, 12, 2),
                "ITSA4",
                100,
                105,
                cost="13.55518731",
                notes="5 por 100; custo atribuído do aviso aos acionistas",
            ),
            SubscriptionOffer(
                right_asset_id=assets["KNRI12"].id,
                underlying_asset_id=assets["KNRI11"].id,
                price_per_unit=Decimal("162.74"),  # 159,55 + 3,19 de taxa de distribuição
                ratio=Decimal("0.2373977429"),
                record_date=date(2024, 3, 26),
                deadline=date(2024, 4, 10),
                notes="8ª emissão",
            ),
            SubscriptionOffer(
                right_asset_id=assets["CVCB1"].id,
                underlying_asset_id=assets["CVCB3"].id,
                price_per_unit=Decimal("19.12"),
                ratio=Decimal("0.1247884739"),
                record_date=date(2021, 6, 24),
                deadline=date(2021, 7, 26),
                notes="aumento de capital de 2021",
            ),
        ]
    )
    session.flush()
