"""Classificador do extrato da B3: linha lida → lançamento com o nosso tipo.

Lê cada linha ao pé da letra e decide só o que a linha diz:
- o tipo (COMPRA, JCP, ALUGUEL_SAIDA...), pelo rótulo e, quando preciso, pelo contexto;
- affects_position: se a linha muda a quantidade do PRÓPRIO ativo na corretora.

O que depende de eventos curados (custo da bonificação, recibo que vira cota, troca de
ticker) é do motor de cálculo. Regras e armadilhas: .claude/rules/dados-b3.md.
"""

import unicodedata
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from app.models.enums import Direction, EntryType
from app.parsers.b3_movimentacao import MovementRow

T = EntryType
CENT = Decimal("0.01")

# Rótulo normalizado (sem acento, minúsculo, "a / b" = "a/b") → (tipo, mexe na quantidade).
SIMPLE_LABELS: dict[str, tuple[EntryType, bool]] = {
    "rendimento": (T.RENDIMENTO, False),
    "dividendo": (T.DIVIDENDO, False),
    "juros sobre capital proprio": (T.JCP, False),
    "reembolso": (T.REEMBOLSO_ALUGUEL, False),
    "evento em dinheiro - excluido": (T.EVENTO_EXCLUIDO, False),
    "bonificacao em ativos": (T.BONIFICACAO, True),
    "desdobro": (T.DESDOBRO, True),
    # Grupamento traz a quantidade resultante; o motor converte em variação.
    "grupamento": (T.GRUPAMENTO, True),
    "atualizacao": (T.ATUALIZACAO, True),
    "incorporacao": (T.INCORPORACAO, True),
    "fracao em ativos": (T.FRACAO_BAIXA, True),
    # A fração já saiu em "Fração em Ativos"; o leilão só traz o dinheiro.
    "leilao de fracao": (T.LEILAO_FRACAO, False),
    "direito de subscricao": (T.DIREITO_RECEBIDO, True),
    "solicitacao de subscricao": (T.SUBSCRICAO_SOLICITADA, True),
    # O pagamento da subscrição: os direitos já saíram na solicitação.
    "direitos de subscricao - exercido": (T.SUBSCRICAO_EXERCIDA, False),
    "direitos de subscricao - nao exercido": (T.DIREITO_EXPIRADO, True),
    "recibo de subscricao": (T.SUBSCRICAO_RECIBO, True),
    "cessao de direitos": (T.DIREITO_CEDIDO, True),
    "cessao de direitos - solicitada": (T.DIREITO_CESSAO_SOLICITADA, False),
    # Renda fixa e Tesouro.
    "compra": (T.COMPRA, True),
    "venda": (T.VENDA, True),
    "resgate": (T.RESGATE, True),
    "resgate antecipado": (T.RESGATE, True),
    "juros": (T.JUROS, False),
    "pagamento de juros": (T.JUROS, False),
    "amortizacao": (T.AMORTIZACAO, False),
    "amortizacao programada": (T.AMORTIZACAO, False),
}
# Compra se entra, venda se sai. O aluguel usa o mesmo rótulo (ver _mark_loans).
TRADE_LABEL = "transferencia - liquidacao"
TRADE_LABELS = {TRADE_LABEL, "compra/venda"}
TRANSFER_LABELS = {
    "transferencia",
    "transferencia sem financeiro",
    "saida/entr. cust-transf s/fin",
}
# Empréstimo sem valor = registro do contrato; com valor = remuneração.
LOAN_LABEL = "emprestimo"

FIXED_INCOME_KINDS = {"CDB", "LCA", "LCI", "LC", "LF", "LIG", "CRI", "CRA", "DEB", "DEBENTURE"}


@dataclass(frozen=True)
class ClassifiedEntry:
    row_hash: str
    row_number: int
    trade_date: date
    entry_type: EntryType
    direction: Direction
    asset_code: str
    asset_name: str | None
    institution: str  # grafia original
    quantity: Decimal
    unit_price: Decimal | None
    gross_amount: Decimal | None
    tax_withheld: Decimal | None
    affects_position: bool
    flags: tuple[str, ...] = ()
    # Retorno do aluguel aponta para a saída.
    related_row_hash: str | None = None


def classify_movements(rows: list[MovementRow]) -> list[ClassifiedEntry]:
    """Classifica todas as linhas do extrato, devolvidas na ordem recebida."""
    entries = [_classify(row) for row in rows]
    labels = {row.row_hash: _norm_label(row.movement) for row in rows}
    entries = _mark_internal_transfers(entries)
    return _mark_loans(entries, labels)


def split_product(product: str) -> tuple[str, str | None]:
    """'WEGE3 - WEG S/A' → ('WEGE3', 'WEG S/A'); renda fixa usa o código da B3."""
    if product.startswith("Tesouro "):
        return product, None
    parts = product.split(" - ")
    if len(parts) >= 3 and parts[0] in FIXED_INCOME_KINDS:
        return parts[1], " - ".join([parts[0], *parts[2:]])
    return parts[0], " - ".join(parts[1:]) or None


def _classify(row: MovementRow) -> ClassifiedEntry:
    label = _norm_label(row.movement)
    if label in SIMPLE_LABELS:
        kind, moves = SIMPLE_LABELS[label]
    elif label in TRADE_LABELS:
        kind, moves = (T.COMPRA if row.direction is Direction.IN else T.VENDA), True
    elif label in TRANSFER_LABELS:
        kind, moves = T.TRANSFERENCIA_CUSTODIA, True
    elif label == LOAN_LABEL:
        kind = T.ALUGUEL_REGISTRO if row.amount is None else T.ALUGUEL_REMUNERACAO
        moves = False
    else:
        raise ValueError(f"Rótulo desconhecido na linha {row.row_number}: {row.movement!r}")

    gross, tax = row.amount, None
    if kind is T.JCP and row.unit_price is not None and row.amount is not None:
        # A linha traz o líquido; o preço é o bruto por ação.
        gross = (row.quantity * row.unit_price).quantize(CENT)
        tax = gross - row.amount

    code, name = split_product(row.product)
    return ClassifiedEntry(
        row_hash=row.row_hash,
        row_number=row.row_number,
        trade_date=row.date,
        entry_type=kind,
        direction=row.direction,
        asset_code=code,
        asset_name=name,
        institution=row.institution,
        quantity=row.quantity,
        unit_price=row.unit_price,
        gross_amount=gross,
        tax_withheld=tax,
        affects_position=moves,
    )


def _mark_internal_transfers(entries: list[ClassifiedEntry]) -> list[ClassifiedEntry]:
    """Saída e entrada no mesmo dia, ativo, quantidade e corretora: par interno.

    Acontece no aluguel (as ações vão da carteira livre para a de empréstimo). Não muda
    a custódia, então não mexe na quantidade. Com corretoras diferentes, é
    transferência de custódia de verdade e fica como está.
    """
    groups: dict[tuple, dict[Direction, list[int]]] = defaultdict(lambda: defaultdict(list))
    for i, e in enumerate(entries):
        if e.entry_type is T.TRANSFERENCIA_CUSTODIA:
            key = (e.trade_date, e.asset_code, e.quantity, institution_key(e.institution))
            groups[key][e.direction].append(i)

    result = list(entries)
    for legs in groups.values():
        for out_i, in_i in zip(legs[Direction.OUT], legs[Direction.IN], strict=False):
            for i in (out_i, in_i):
                result[i] = replace(
                    result[i], affects_position=False, flags=("TRANSFERENCIA_INTERNA",)
                )
    return result


def _mark_loans(entries: list[ClassifiedEntry], labels: dict[str, str]) -> list[ClassifiedEntry]:
    """Aluguel disfarçado de compra e venda.

    Saída sem preço com o rótulo da venda = ações emprestadas. A próxima entrada, em
    data posterior, da mesma quantidade, ativo e corretora = devolução (o preço é só
    referência). Nenhuma das duas mexe na posição nem no PM.
    """
    result = list(entries)
    open_loans: dict[tuple, list[int]] = defaultdict(list)
    # Em ordem de data, qualquer que seja a ordem do arquivo (sorted é estável).
    for i in sorted(range(len(result)), key=lambda i: result[i].trade_date):
        e = result[i]
        if labels[e.row_hash] != TRADE_LABEL:
            continue
        key = (e.asset_code, e.quantity, institution_key(e.institution))
        if e.direction is Direction.OUT and e.unit_price is None:
            result[i] = replace(e, entry_type=T.ALUGUEL_SAIDA, affects_position=False)
            open_loans[key].append(i)
        elif e.direction is Direction.IN and open_loans[key]:
            out = result[open_loans[key][0]]
            if e.trade_date > out.trade_date:
                open_loans[key].pop(0)
                result[i] = replace(
                    e,
                    entry_type=T.ALUGUEL_RETORNO,
                    affects_position=False,
                    related_row_hash=out.row_hash,
                )
    return result


def _norm_label(label: str) -> str:
    text = unicodedata.normalize("NFKD", label)
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return " ".join(text.replace(" / ", "/").split())


def institution_key(name: str) -> str:
    # Mesma corretora com ponto final ou espaço duplo (a tabela de aliases é a palavra
    # final; aqui só importa saber se é a mesma).
    return " ".join(name.split()).rstrip(".")
