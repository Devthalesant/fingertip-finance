"""Leitor do extrato de movimentação da B3: xlsx → linhas tipadas, com hash por linha."""

from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.models.enums import Direction as Dir
from app.parsers.b3_movimentacao import movement_from_raw, parse_movement_statement
from sample_data.b3_format import Direction, Movement, StatementRow, write_movement_statement
from sample_data.scenario import movement_rows

BROKER = "CORRETORA ALFA S/A"


def row(day: date = date(2021, 8, 2), **kwargs) -> StatementRow:
    defaults = {
        "direction": Direction.CREDIT,
        "date": day,
        "movement": Movement.LIQUIDACAO,
        "product": "BBAS3 - BANCO DO BRASIL S/A",
        "institution": BROKER,
        "quantity": Decimal("100"),
        "unit_price": Decimal("30.00"),
        "amount": Decimal("3000.00"),
    }
    return StatementRow(**(defaults | kwargs))


def parse(rows: list[StatementRow], tmp_path: Path, name: str = "x.xlsx"):
    return parse_movement_statement(write_movement_statement(rows, tmp_path / name))


def test_reads_every_row_of_the_story(tmp_path: Path) -> None:
    # Quebra se o leitor pular, duplicar ou deformar alguma linha (data, número, "-").
    def key(direction, day, movement, product, institution, quantity, price, amount):
        return (direction, day, movement, product, institution, quantity, price, amount)

    expected = Counter(
        key(
            Dir.IN if r.direction is Direction.CREDIT else Dir.OUT,
            r.date,
            r.movement.value,
            r.product,
            r.institution,
            r.quantity,
            r.unit_price,
            r.amount,
        )
        for r in movement_rows()
    )
    parsed = parse(movement_rows(), tmp_path)
    got = Counter(
        key(
            p.direction,
            p.date,
            p.movement,
            p.product,
            p.institution,
            p.quantity,
            p.unit_price,
            p.amount,
        )
        for p in parsed
    )
    assert got == expected


def test_dash_becomes_none_and_text_date_becomes_date(tmp_path: Path) -> None:
    expired = row(
        date(2021, 7, 27),
        direction=Direction.DEBIT,
        movement=Movement.SUBSCRICAO_NAO_EXERCIDA,
        quantity=Decimal("24"),
        unit_price=None,
        amount=None,
    )
    (parsed,) = parse([expired], tmp_path)
    assert parsed.date == date(2021, 7, 27)
    assert parsed.direction is Dir.OUT
    assert parsed.quantity == Decimal("24")
    assert parsed.unit_price is None and parsed.amount is None


def test_fractions_and_cents_are_exact_decimals(tmp_path: Path) -> None:
    # Quebra se algum número passar por float sem voltar exato (ex.: 6.4999999).
    auction = row(quantity=Decimal("0.5"), unit_price=Decimal("13.00"), amount=Decimal("6.50"))
    (parsed,) = parse([auction], tmp_path)
    assert parsed.quantity == Decimal("0.5")
    # Dinheiro sempre com centavos, como a coluna MONEY do banco.
    assert str(parsed.amount) == "6.50"
    assert parsed.unit_price == Decimal("13")


def test_amount_with_fraction_of_cent_is_refused(tmp_path: Path) -> None:
    # Quebra se o leitor arredondar dinheiro em silêncio.
    odd = row(amount=Decimal("10.005"))
    with pytest.raises(ValueError, match="centavos"):
        parse([odd], tmp_path)


def test_row_number_is_the_spreadsheet_line(tmp_path: Path) -> None:
    # Linha 1 é o cabeçalho; a mais nova vem primeiro.
    parsed = parse([row(date(2021, 1, 4)), row(date(2022, 1, 3))], tmp_path)
    assert [(p.row_number, p.date) for p in parsed] == [
        (2, date(2022, 1, 3)),
        (3, date(2021, 1, 4)),
    ]


def test_identical_rows_are_both_kept_with_different_hashes(tmp_path: Path) -> None:
    # A ordem executada em duas partes: duas linhas idênticas e legítimas.
    first, second = parse([row(), row()], tmp_path)
    assert first.content_hash == second.content_hash
    assert (first.occurrence_index, second.occurrence_index) == (0, 1)
    assert first.row_hash != second.row_hash


def test_overlapping_exports_give_the_same_row_hash(tmp_path: Path) -> None:
    # Reimportar um período sobreposto não pode duplicar: a mesma linha, mesmo hash,
    # ainda que o outro arquivo tenha linhas a mais.
    shared = [row(), row(), row(date(2021, 9, 1), movement=Movement.DIVIDENDO)]
    extra = row(date(2023, 1, 2), product="WEGE3 - WEG S/A")
    short = parse(shared, tmp_path, "a.xlsx")
    long = parse([extra, *shared], tmp_path, "b.xlsx")
    assert {p.row_hash for p in short} < {p.row_hash for p in long}


def test_spacing_variants_of_the_same_row_have_the_same_hash(tmp_path: Path) -> None:
    # A B3 grava a mesma corretora com espaço duplo em alguns exports.
    (single,) = parse([row(institution="EXEMPLAR INVESTIMENTOS CTVM S.A.")], tmp_path, "a.xlsx")
    (double,) = parse([row(institution="EXEMPLAR INVESTIMENTOS  CTVM S.A.")], tmp_path, "b.xlsx")
    assert single.row_hash == double.row_hash
    # A grafia original continua guardada (a tabela de aliases resolve depois).
    assert double.institution == "EXEMPLAR INVESTIMENTOS  CTVM S.A."


def test_payload_keeps_the_original_cells(tmp_path: Path) -> None:
    (parsed,) = parse([row(unit_price=None, amount=None)], tmp_path)
    assert parsed.payload == {
        "Entrada/Saída": "Credito",
        "Data": "02/08/2021",
        "Movimentação": "Transferência - Liquidação",
        "Produto": "BBAS3 - BANCO DO BRASIL S/A",
        "Instituição": BROKER,
        "Quantidade": "100",
        "Preço unitário": "-",
        "Valor da Operação": "-",
    }


def test_rejects_a_file_that_is_not_a_movement_statement(tmp_path: Path) -> None:
    wb = Workbook()
    wb.active.append(("Produto", "Instituição", "Quantidade"))
    wb.save(tmp_path / "posicao.xlsx")
    with pytest.raises(ValueError, match="extrato de movimentação"):
        parse_movement_statement(tmp_path / "posicao.xlsx")


def test_saved_payload_reads_back_to_the_same_row(tmp_path: Path) -> None:
    # O ledger é refeito a partir das linhas brutas do banco: reler o payload salvo
    # precisa dar exatamente a mesma linha, inclusive frações e "-".
    for parsed in parse(movement_rows(), tmp_path):
        again = movement_from_raw(
            parsed.row_number,
            parsed.payload,
            parsed.content_hash,
            parsed.occurrence_index,
            parsed.row_hash,
        )
        assert again == parsed
