"""Formato do extrato de movimentação da B3 (xlsx), com as esquisitices do original.

Este módulo é só o "formulário": recebe linhas prontas e grava o arquivo como a B3
exporta. Quais linhas existem (a história do investidor) fica em scenario.py.

O que o original tem e o sintético imita:
- data como texto dd/mm/aaaa, não como data do Excel;
- linhas da mais nova para a mais antiga;
- preço e valor ausentes como o texto "-", não célula vazia;
- número inteiro gravado como inteiro (10, não 10.0).
"""

import io
import re
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from openpyxl import Workbook

HEADER = (
    "Entrada/Saída",
    "Data",
    "Movimentação",
    "Produto",
    "Instituição",
    "Quantidade",
    "Preço unitário",
    "Valor da Operação",
)
# Conferido no arquivo real. Mesmo assim, o parser lê a primeira aba, qualquer que seja
# o nome.
SHEET_TITLE = "Movimentação"
EMPTY = "-"
DATE_FORMAT = "%d/%m/%Y"


class Direction(StrEnum):
    CREDIT = "Credito"
    DEBIT = "Debito"


class Movement(StrEnum):
    """Rótulos da coluna Movimentação, escritos exatamente como a B3 escreve."""

    # Compra e venda de renda variável. O aluguel usa o mesmo rótulo.
    LIQUIDACAO = "Transferência - Liquidação"
    TRANSFERENCIA = "Transferência"
    TRANSFERENCIA_SEM_FINANCEIRO = "TRANSFERÊNCIA SEM FINANCEIRO"
    TRANSFERENCIA_CUSTODIA = "SAIDA/ENTR. CUST-TRANSF S/FIN"
    # Aluguel: registro do contrato (sem valor) e remuneração (com valor), ambos crédito.
    EMPRESTIMO = "Empréstimo"
    REEMBOLSO = "Reembolso"
    RENDIMENTO = "Rendimento"
    DIVIDENDO = "Dividendo"
    JCP = "Juros Sobre Capital Próprio"
    JCP_TRANSFERIDO = "Juros Sobre Capital Próprio - Transferido"
    EVENTO_EXCLUIDO = "Evento em Dinheiro - Excluído"
    BONIFICACAO = "Bonificação em Ativos"
    DESDOBRO = "Desdobro"
    GRUPAMENTO = "Grupamento"
    ATUALIZACAO = "Atualização"
    INCORPORACAO = "Incorporação"
    FRACAO = "Fração em Ativos"
    LEILAO_FRACAO = "Leilão de Fração"
    DIREITO = "Direito de Subscrição"
    SUBSCRICAO_SOLICITADA = "Solicitação de Subscrição"
    SUBSCRICAO_EXERCIDA = "Direitos de Subscrição - Exercido"
    SUBSCRICAO_NAO_EXERCIDA = "Direitos de Subscrição - Não Exercido"
    RECIBO_SUBSCRICAO = "Recibo de Subscrição"
    CESSAO = "Cessão de Direitos"
    CESSAO_SOLICITADA = "Cessão de Direitos - Solicitada"
    # Renda fixa e Tesouro: a B3 mistura caixa alta e baixa.
    COMPRA = "Compra"
    VENDA = "Venda"
    COMPRA_VENDA = "COMPRA / VENDA"
    JUROS = "Juros"
    PAGAMENTO_JUROS = "PAGAMENTO DE JUROS"
    AMORTIZACAO = "AMORTIZAÇÃO"
    RESGATE = "Resgate"
    RESGATE_ANTECIPADO = "RESGATE ANTECIPADO"


@dataclass(frozen=True)
class StatementRow:
    """Uma linha do extrato. Valores em Decimal; viram número do Excel só na gravação."""

    direction: Direction
    date: date
    movement: Movement
    product: str
    institution: str
    quantity: Decimal
    unit_price: Decimal | None = None
    amount: Decimal | None = None

    def cells(self) -> tuple:
        return (
            self.direction.value,
            self.date.strftime(DATE_FORMAT),
            self.movement.value,
            self.product,
            self.institution,
            _number(self.quantity),
            EMPTY if self.unit_price is None else _number(self.unit_price),
            EMPTY if self.amount is None else _number(self.amount),
        )


def _number(value: Decimal) -> int | float:
    # O xlsx guarda número como ponto flutuante; a B3 grava inteiros sem casas.
    return int(value) if value == value.to_integral_value() else float(value)


def write_movement_statement(rows: Iterable[StatementRow], path: Path) -> Path:
    """Grava o extrato. Mais nova primeiro; no mesmo dia, mantém a ordem recebida."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_TITLE
    ws.append(HEADER)
    # sorted é estável: linhas do mesmo dia não trocam de lugar entre si.
    for row in sorted(rows, key=lambda r: r.date, reverse=True):
        ws.append(row.cells())
    save_deterministic(wb, path)
    return path


# Data fixa nos metadados e no zip: o mesmo conteúdo gera os mesmos bytes (e o mesmo
# SHA-256, que é como o import_file reconhece um arquivo já importado).
_FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def save_deterministic(wb: Workbook, path: Path) -> None:
    wb.properties.creator = "fingertip-finance sample_data"
    buffer = io.BytesIO()
    wb.save(buffer)
    path.parent.mkdir(parents=True, exist_ok=True)
    with (
        zipfile.ZipFile(buffer) as source,
        zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "docProps/core.xml":
                data = _fix_core_dates(data)
            info = zipfile.ZipInfo(item.filename, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, data)


def _fix_core_dates(xml: bytes) -> bytes:
    return re.sub(
        rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:)",
        rb"\g<1>2020-01-01T00:00:00Z\g<2>",
        xml,
    )
