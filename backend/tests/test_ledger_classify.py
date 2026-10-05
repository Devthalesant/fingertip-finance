"""Classificador: linha lida da B3 → lançamento com o nosso tipo (COMPRA, JCP, ALUGUEL...)."""

import itertools
from collections import Counter
from datetime import date
from decimal import Decimal

import pytest

from app.ledger.classify import ClassifiedEntry, classify_movements, split_product
from app.models.enums import Direction as Dir
from app.models.enums import EntryType as T
from app.parsers.b3_movimentacao import MovementRow, parse_movement_statement
from sample_data.b3_format import write_movement_statement
from sample_data.scenario import movement_rows

BROKER = "CORRETORA ALFA S/A"
_hashes = itertools.count()


def mv(
    movement: str,
    direction: Dir = Dir.IN,
    *,
    product: str = "BBAS3 - BANCO DO BRASIL S/A",
    institution: str = BROKER,
    quantity: str = "100",
    price: str | None = None,
    amount: str | None = None,
    day: date = date(2023, 1, 2),
) -> MovementRow:
    """Linha já lida, montada à mão (para rótulos que a história não usa)."""
    n = next(_hashes)
    return MovementRow(
        row_number=n + 2,
        direction=direction,
        date=day,
        movement=movement,
        product=product,
        institution=institution,
        quantity=Decimal(quantity),
        unit_price=None if price is None else Decimal(price),
        amount=None if amount is None else Decimal(amount),
        payload={},
        content_hash=f"c{n}",
        occurrence_index=0,
        row_hash=f"h{n}",
    )


def one(row: MovementRow) -> ClassifiedEntry:
    (entry,) = classify_movements([row])
    return entry


@pytest.fixture(scope="module")
def story(tmp_path_factory: pytest.TempPathFactory) -> list[ClassifiedEntry]:
    path = tmp_path_factory.mktemp("b3") / "movimentacao.xlsx"
    return classify_movements(
        parse_movement_statement(write_movement_statement(movement_rows(), path))
    )


def find(story: list[ClassifiedEntry], code: str, day: date, kind: T | None = None):
    return [
        e
        for e in story
        if e.asset_code == code and e.trade_date == day and (kind is None or e.entry_type is kind)
    ]


# --- Rótulos: um por linha, com o tipo e se mexe na quantidade do ativo -------------


@pytest.mark.parametrize(
    ("label", "direction", "price", "amount", "kind", "moves_quantity"),
    [
        ("Transferência - Liquidação", Dir.IN, "30", "3000", T.COMPRA, True),
        ("Transferência - Liquidação", Dir.OUT, "30", "3000", T.VENDA, True),
        ("Rendimento", Dir.IN, "1", "100", T.RENDIMENTO, False),
        ("Dividendo", Dir.IN, "0.4", "40", T.DIVIDENDO, False),
        ("Reembolso", Dir.IN, None, "15", T.REEMBOLSO_ALUGUEL, False),
        ("Empréstimo", Dir.IN, None, None, T.ALUGUEL_REGISTRO, False),
        ("Empréstimo", Dir.IN, None, "18", T.ALUGUEL_REMUNERACAO, False),
        ("Evento em Dinheiro - Excluído", Dir.OUT, None, None, T.EVENTO_EXCLUIDO, False),
        ("Bonificação em Ativos", Dir.IN, None, None, T.BONIFICACAO, True),
        ("Desdobro", Dir.IN, None, None, T.DESDOBRO, True),
        ("Grupamento", Dir.IN, None, None, T.GRUPAMENTO, True),
        ("Atualização", Dir.IN, None, None, T.ATUALIZACAO, True),
        ("Incorporação", Dir.IN, None, None, T.INCORPORACAO, True),
        ("Fração em Ativos", Dir.OUT, None, None, T.FRACAO_BAIXA, True),
        # A fração já saiu na linha anterior; o leilão só traz o dinheiro.
        ("Leilão de Fração", Dir.IN, "13", "6.5", T.LEILAO_FRACAO, False),
        ("Direito de Subscrição", Dir.IN, None, None, T.DIREITO_RECEBIDO, True),
        ("Solicitação de Subscrição", Dir.OUT, None, None, T.SUBSCRICAO_SOLICITADA, True),
        # O pagamento: os direitos já saíram na solicitação.
        (
            "Direitos de Subscrição - Exercido",
            Dir.OUT,
            "162.74",
            "3743.02",
            T.SUBSCRICAO_EXERCIDA,
            False,
        ),
        ("Direitos de Subscrição - Não Exercido", Dir.OUT, None, None, T.DIREITO_EXPIRADO, True),
        ("Recibo de Subscrição", Dir.IN, None, None, T.SUBSCRICAO_RECIBO, True),
        ("Cessão de Direitos", Dir.OUT, "1", "10", T.DIREITO_CEDIDO, True),
        (
            "Cessão de Direitos - Solicitada",
            Dir.OUT,
            None,
            None,
            T.DIREITO_CESSAO_SOLICITADA,
            False,
        ),
        # Renda fixa e Tesouro: caixa, acento e espaço variam.
        ("Compra", Dir.IN, "13000", "6500", T.COMPRA, True),
        ("Venda", Dir.OUT, "14500", "2900", T.VENDA, True),
        ("COMPRA / VENDA", Dir.IN, "1000", "5000", T.COMPRA, True),
        ("COMPRA/VENDA", Dir.OUT, "1000", "5000", T.VENDA, True),
        ("Resgate", Dir.OUT, "1000", "1000", T.RESGATE, True),
        ("RESGATE ANTECIPADO", Dir.OUT, "1120", "2240", T.RESGATE, True),
        ("Juros", Dir.IN, "100", "100", T.JUROS, False),
        ("PAGAMENTO DE JUROS", Dir.IN, "100", "100", T.JUROS, False),
        ("AMORTIZAÇÃO", Dir.IN, "100", "100", T.AMORTIZACAO, False),
        ("AMORTIZACAO PROGRAMADA", Dir.IN, "100", "100", T.AMORTIZACAO, False),
    ],
)
def test_label_becomes_entry_type(label, direction, price, amount, kind, moves_quantity) -> None:
    entry = one(mv(label, direction, price=price, amount=amount))
    assert entry.entry_type is kind
    assert entry.affects_position is moves_quantity


def test_unknown_label_is_refused_by_name() -> None:
    # Melhor parar do que chutar: rótulo novo vira caso novo na tabela.
    with pytest.raises(ValueError, match="Rótulo desconhecido.*Bonus Misterioso"):
        one(mv("Bonus Misterioso"))


# --- Produto → código do ativo -----------------------------------------------------


@pytest.mark.parametrize(
    ("product", "code", "name"),
    [
        ("WEGE3 - WEG S/A", "WEGE3", "WEG S/A"),
        # O nome do FII também tem " - ": o ticker continua sendo a primeira parte.
        (
            "KNRI11 - KINEA RENDA IMOBILIÁRIA FDO INV IMOB - FII",
            "KNRI11",
            "KINEA RENDA IMOBILIÁRIA FDO INV IMOB - FII",
        ),
        # Renda fixa: TIPO - CÓDIGO - EMISSOR; o código da B3 identifica o título.
        ("CDB - 23C01234567 - BANCO EXEMPLO S/A", "23C01234567", "CDB - BANCO EXEMPLO S/A"),
        ("LCA - 23F00765432 - BANCO EXEMPLO S/A", "23F00765432", "LCA - BANCO EXEMPLO S/A"),
        # Tesouro: o nome por extenso é o próprio código.
        ("Tesouro Selic 2029", "Tesouro Selic 2029", None),
    ],
)
def test_product_splits_into_code_and_name(product: str, code: str, name: str | None) -> None:
    assert split_product(product) == (code, name)


# --- Proventos ---------------------------------------------------------------------


def test_jcp_line_is_net_so_gross_and_tax_are_rebuilt() -> None:
    # 200 ações × R$ 0,50 = 100,00 bruto; a B3 mostra 85,00 (já sem 15% de IR).
    entry = one(mv("Juros Sobre Capital Próprio", quantity="200", price="0.50", amount="85.00"))
    assert entry.entry_type is T.JCP
    assert (entry.gross_amount, entry.tax_withheld) == (Decimal("100.00"), Decimal("15.00"))


def test_dividend_is_already_gross() -> None:
    entry = one(mv("Dividendo", quantity="200", price="0.40", amount="80.00"))
    assert (entry.gross_amount, entry.tax_withheld) == (Decimal("80.00"), None)


# --- Aluguel e transferências (precisam olhar várias linhas juntas) ----------------


def test_loan_is_not_a_sale(story: list[ClassifiedEntry]) -> None:
    # WEGE3: 100 emprestadas em 01/09/2022, devolvidas em 01/12/2022.
    start = Counter(e.entry_type for e in find(story, "WEGE3", date(2022, 9, 1)))
    assert start == {T.TRANSFERENCIA_CUSTODIA: 2, T.ALUGUEL_REGISTRO: 1, T.ALUGUEL_SAIDA: 1}
    assert all(not e.affects_position for e in find(story, "WEGE3", date(2022, 9, 1)))

    (back,) = find(story, "WEGE3", date(2022, 12, 1))
    (out,) = find(story, "WEGE3", date(2022, 9, 1), T.ALUGUEL_SAIDA)
    assert back.entry_type is T.ALUGUEL_RETORNO
    assert not back.affects_position
    assert back.related_row_hash == out.row_hash


def test_loan_internal_transfer_pair_is_flagged(story: list[ClassifiedEntry]) -> None:
    pair = find(story, "WEGE3", date(2022, 9, 1), T.TRANSFERENCIA_CUSTODIA)
    assert {e.direction for e in pair} == {Dir.IN, Dir.OUT}
    assert all("TRANSFERENCIA_INTERNA" in e.flags for e in pair)


def test_loan_income_is_typed(story: list[ClassifiedEntry]) -> None:
    (fee,) = find(story, "WEGE3", date(2022, 12, 5))
    (refund,) = find(story, "WEGE3", date(2022, 11, 10), T.REEMBOLSO_ALUGUEL)
    assert (fee.entry_type, fee.gross_amount) == (T.ALUGUEL_REMUNERACAO, Decimal("18.00"))
    assert refund.gross_amount == Decimal("15.00")


def test_transfer_between_brokers_moves_custody(story: list[ClassifiedEntry]) -> None:
    legs = find(story, "WEGE3", date(2024, 8, 5))
    assert {(e.entry_type, e.direction, e.institution) for e in legs} == {
        (T.TRANSFERENCIA_CUSTODIA, Dir.OUT, "FICTICIA CORRETORA DE VALORES S/A"),
        (T.TRANSFERENCIA_CUSTODIA, Dir.IN, "EXEMPLAR INVESTIMENTOS  CTVM S.A."),
    }
    assert all(e.affects_position and not e.flags for e in legs)


def test_story_sales_are_exactly_the_real_ones(story: list[ClassifiedEntry]) -> None:
    # As vendas da história; a saída do aluguel não pode aparecer aqui.
    sales = {(e.asset_code, e.trade_date) for e in story if e.entry_type is T.VENDA}
    assert sales == {
        ("WEGE3", date(2023, 8, 10)),
        ("CVCB3", date(2022, 3, 14)),
        ("MGLU3", date(2025, 2, 17)),
        ("ITSA4", date(2025, 6, 16)),
        ("BHIA3", date(2023, 11, 20)),
        ("PETR4", date(2023, 5, 15)),
        ("Tesouro Selic 2029", date(2024, 4, 4)),
    }


def test_every_story_row_becomes_one_entry(story: list[ClassifiedEntry]) -> None:
    # Quebra se o classificador engolir ou duplicar linhas.
    assert len(story) == len(movement_rows())
    assert len({e.row_hash for e in story}) == len(story)


def test_classifier_does_not_depend_on_file_order() -> None:
    # O extrato vem da mais nova para a mais antiga; o retorno ainda acha a saída.
    out = mv("Transferência - Liquidação", Dir.OUT, day=date(2022, 9, 1))
    back = mv(
        "Transferência - Liquidação", Dir.IN, price="29", amount="2900", day=date(2022, 12, 1)
    )
    entries = {e.row_hash: e for e in classify_movements([back, out])}
    assert entries[back.row_hash].entry_type is T.ALUGUEL_RETORNO
    assert entries[back.row_hash].related_row_hash == out.row_hash


def test_buy_before_any_loan_is_a_buy() -> None:
    # Mesma quantidade e corretora, mas sem saída de aluguel antes: é compra mesmo.
    buy = mv("Transferência - Liquidação", Dir.IN, price="30", amount="3000", day=date(2022, 1, 3))
    out = mv("Transferência - Liquidação", Dir.OUT, day=date(2022, 9, 1))
    entries = {e.row_hash: e for e in classify_movements([out, buy])}
    assert entries[buy.row_hash].entry_type is T.COMPRA
