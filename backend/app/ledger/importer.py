"""Gravador do extrato da B3 no banco, nas três camadas do ADR 0001.

1. import_file: o arquivo, pelo SHA-256. O mesmo arquivo não entra duas vezes.
2. raw_row: cada linha, imutável. Linha já gravada por outro arquivo (período
   sobreposto) é reconhecida pelo row_hash e não duplica.
3. ledger_entry: derivado. A cada importação, os lançamentos importados da pessoa são
   refeitos a partir de TODAS as linhas brutas dela: o aluguel que sai num arquivo e
   volta no outro é reconhecido, e corrigir o classificador é só reprocessar.

Não faz commit: quem chama decide (a API faz commit; os testes desfazem).
"""

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.ledger.classify import ClassifiedEntry, classify_movements, institution_key
from app.models import (
    Account,
    Asset,
    AssetAlias,
    ImportFile,
    Institution,
    InstitutionAlias,
    LedgerEntry,
    RawRow,
)
from app.models.enums import AccountKind, AssetClass, EntryOrigin, InstitutionKind
from app.parsers.b3_movimentacao import SOURCE, movement_from_raw, parse_movement_statement

# Muda quando o leitor ou o classificador mudam o resultado: dá para saber de qual
# versão veio cada lançamento e reprocessar.
PARSER_VERSION = "b3-mov-1"
# Conta de custódia na B3, uma por corretora.
CUSTODY_LABEL = "B3"


@dataclass(frozen=True)
class ImportResult:
    import_file_id: int
    already_imported: bool
    new_rows: int
    skipped_rows: int  # já gravadas por outro arquivo
    ledger_entries: int  # lançamentos importados da pessoa, depois de refeitos


def import_b3_movements(session: Session, user_id: int, path: Path) -> ImportResult:
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    existing = session.scalar(
        select(ImportFile).where(ImportFile.user_id == user_id, ImportFile.file_sha256 == sha256)
    )
    if existing is not None:
        return ImportResult(existing.id, True, 0, 0, _count_entries(session, user_id))

    rows = parse_movement_statement(path)
    file = ImportFile(
        user_id=user_id,
        source=SOURCE,
        file_name=path.name,
        file_sha256=sha256,
        period_start=min((r.date for r in rows), default=None),
        period_end=max((r.date for r in rows), default=None),
    )
    session.add(file)
    session.flush()

    known = set(
        session.scalars(
            select(RawRow.row_hash).where(
                RawRow.user_id == user_id,
                RawRow.source == SOURCE,
                RawRow.row_hash.in_([r.row_hash for r in rows]),
            )
        )
    )
    new = [r for r in rows if r.row_hash not in known]
    session.add_all(
        RawRow(
            user_id=user_id,
            import_file_id=file.id,
            source=SOURCE,
            row_number=r.row_number,
            payload=r.payload,
            content_hash=r.content_hash,
            occurrence_index=r.occurrence_index,
            row_hash=r.row_hash,
        )
        for r in new
    )
    session.flush()
    total = rebuild_ledger(session, user_id)
    return ImportResult(file.id, False, len(new), len(rows) - len(new), total)


def rebuild_ledger(session: Session, user_id: int) -> int:
    """Apaga e refaz os lançamentos importados da B3 a partir das linhas brutas."""
    raw_ids = select(RawRow.id).where(RawRow.user_id == user_id, RawRow.source == SOURCE)
    session.execute(
        delete(LedgerEntry).where(
            LedgerEntry.user_id == user_id,
            LedgerEntry.origin == EntryOrigin.IMPORT,
            LedgerEntry.raw_row_id.in_(raw_ids),
        )
    )
    raws = session.scalars(
        select(RawRow)
        .where(RawRow.user_id == user_id, RawRow.source == SOURCE)
        .order_by(RawRow.import_file_id, RawRow.row_number)
    ).all()
    raw_by_hash = {r.row_hash: r for r in raws}
    classified = classify_movements(
        [
            movement_from_raw(
                r.row_number, r.payload, r.content_hash, r.occurrence_index, r.row_hash
            )
            for r in raws
        ]
    )

    resolver = _Resolver(session, user_id)
    saved: dict[str, LedgerEntry] = {}
    for c in classified:
        saved[c.row_hash] = _entry(c, user_id, raw_by_hash[c.row_hash].id, resolver)
    session.add_all(saved.values())
    session.flush()
    # O retorno do aluguel aponta para a saída: só dá para ligar depois de ter os ids.
    for c in classified:
        if c.related_row_hash is not None:
            saved[c.row_hash].related_entry_id = saved[c.related_row_hash].id
    session.flush()
    return len(saved)


def _entry(c: ClassifiedEntry, user_id: int, raw_row_id: int, resolver: "_Resolver") -> LedgerEntry:
    return LedgerEntry(
        user_id=user_id,
        raw_row_id=raw_row_id,
        origin=EntryOrigin.IMPORT,
        parser_version=PARSER_VERSION,
        account_id=resolver.account(c.institution),
        asset_id=resolver.asset(c.asset_code, c.asset_name, c.trade_date),
        trade_date=c.trade_date,
        entry_type=c.entry_type,
        direction=c.direction,
        quantity=c.quantity,
        unit_price=c.unit_price,
        gross_amount=c.gross_amount,
        tax_withheld=c.tax_withheld,
        currency="BRL",
        affects_position=c.affects_position,
        flags=list(c.flags),
    )


def _count_entries(session: Session, user_id: int) -> int:
    return session.scalar(
        select(func.count())
        .select_from(LedgerEntry)
        .where(LedgerEntry.user_id == user_id, LedgerEntry.origin == EntryOrigin.IMPORT)
    )


class _Resolver:
    """Acha (ou cria) instituição, conta e ativo, com cache para não repetir consultas."""

    def __init__(self, session: Session, user_id: int) -> None:
        self.session = session
        self.user_id = user_id
        self.accounts: dict[str, int] = {}
        self.assets: dict[tuple[str, date], int] = {}

    def account(self, raw_name: str) -> int:
        if raw_name not in self.accounts:
            institution = self._institution(raw_name)
            account = self.session.scalar(
                select(Account).where(
                    Account.user_id == self.user_id,
                    Account.institution_id == institution.id,
                    Account.kind == AccountKind.CUSTODY,
                    Account.label == CUSTODY_LABEL,
                )
            )
            if account is None:
                account = Account(
                    user_id=self.user_id,
                    institution_id=institution.id,
                    kind=AccountKind.CUSTODY,
                    label=CUSTODY_LABEL,
                )
                self.session.add(account)
                self.session.flush()
            self.accounts[raw_name] = account.id
        return self.accounts[raw_name]

    def _institution(self, raw_name: str) -> Institution:
        """Pela grafia exata (alias) ou, se for nova, por uma instituição de mesmo nome
        a menos de espaços e ponto final. A grafia nova vira alias."""
        institution = self.session.scalar(
            select(Institution)
            .join(InstitutionAlias, InstitutionAlias.institution_id == Institution.id)
            .where(InstitutionAlias.raw_name == raw_name)
        )
        if institution is not None:
            return institution
        key = institution_key(raw_name)
        institution = next(
            (
                i
                for i in self.session.scalars(select(Institution))
                if institution_key(i.name) == key
            ),
            None,
        )
        if institution is None:
            institution = Institution(name=" ".join(raw_name.split()), kind=InstitutionKind.BROKER)
            self.session.add(institution)
            self.session.flush()
        self.session.add(InstitutionAlias(institution_id=institution.id, raw_name=raw_name))
        self.session.flush()
        return institution

    def asset(self, code: str, name: str | None, day: date) -> int:
        """Pelo alias vigente na data, pelo código, ou cria no catálogo a classificar."""
        key = (code, day)
        if key not in self.assets:
            asset_id = self.session.scalar(
                select(AssetAlias.asset_id).where(
                    AssetAlias.alias == code,
                    or_(AssetAlias.valid_from.is_(None), AssetAlias.valid_from <= day),
                    or_(AssetAlias.valid_to.is_(None), AssetAlias.valid_to >= day),
                )
            ) or self.session.scalar(
                # Ativo privado da pessoa primeiro, depois o catálogo compartilhado.
                select(Asset.id)
                .where(
                    Asset.canonical_code == code,
                    or_(Asset.owner_user_id == self.user_id, Asset.owner_user_id.is_(None)),
                )
                .order_by(Asset.owner_user_id.is_(None))
            )
            if asset_id is None:
                asset = Asset(canonical_code=code, name=name, asset_class=AssetClass.A_CLASSIFICAR)
                self.session.add(asset)
                self.session.flush()
                asset_id = asset.id
            self.assets[key] = asset_id
        return self.assets[key]
