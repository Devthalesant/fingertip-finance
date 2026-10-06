"""POST /imports/b3-movements: upload do extrato de movimentação da B3 (ADR 0004).

Barreiras, na ordem: tamanho na porta (limits.py) → tamanho e extensão aqui → raio-x do
zip e leitura em quarentena (parsers/quarantine.py) → gravador. O arquivo é lido em
memória e descartado; o log guarda motivo e tamanho, nunca conteúdo.
"""

import logging
import re
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUserDep, SessionDep
from app.api.rate_limit import limited
from app.ledger.importer import import_b3_upload
from app.models import ImportFile, RawRow
from app.parsers.quarantine import QuarantineFailed, parse_in_quarantine
from app.parsers.xlsx_guard import MAX_UPLOAD_BYTES, UnsafeFile

log = logging.getLogger(__name__)

router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[limited("api")])

MAX_FILE_NAME = 255
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class SuspectedDuplicateOut(BaseModel):
    """Linha que voltou diferente num export novo: a pessoa confere qual vale."""

    date: date
    movement: str
    product: str


class ImportOut(BaseModel):
    file_name: str
    already_imported: bool
    new_rows: int
    skipped_rows: int  # já gravadas por outro arquivo (período sobreposto)
    ledger_entries: int
    suspected_duplicates: list[SuspectedDuplicateOut]


class ImportFileOut(BaseModel):
    file_name: str
    period_start: date | None
    period_end: date | None
    imported_at: datetime
    new_rows: int  # linhas que entraram por este arquivo (as repetidas ficam com o anterior)


@router.get("")
def list_imports(session: SessionDep, user: CurrentUserDep) -> list[ImportFileOut]:
    """Histórico de importações da pessoa, a mais recente primeiro."""
    new_rows = (
        select(func.count())
        .where(RawRow.import_file_id == ImportFile.id)
        .correlate(ImportFile)
        .scalar_subquery()
    )
    rows = session.execute(
        select(ImportFile, new_rows)
        .where(ImportFile.user_id == user.id)
        .order_by(ImportFile.imported_at.desc(), ImportFile.id.desc())
    )
    return [
        ImportFileOut(
            file_name=f.file_name,
            period_start=f.period_start,
            period_end=f.period_end,
            imported_at=f.imported_at,
            new_rows=count,
        )
        for f, count in rows
    ]


@router.post("/b3-movements", dependencies=[limited("upload")])
def upload_b3_movements(file: UploadFile, session: SessionDep, user: CurrentUserDep) -> ImportOut:
    name = clean_file_name(file.filename)
    if not name.lower().endswith(".xlsx"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Envie o extrato de movimentação da B3 em xlsx.",
        )
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    try:
        result = import_b3_upload(session, user.id, data, name, parse=parse_in_quarantine)
    except (UnsafeFile, QuarantineFailed) as exc:
        log.warning(
            "upload recusado: user=%s reason=%s detail=%s bytes=%d",
            user.id,
            exc.reason,
            exc.detail,
            len(data),
        )
        code = (
            status.HTTP_413_CONTENT_TOO_LARGE
            if exc.reason == "too_big"
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(code, str(exc)) from None
    return ImportOut(
        file_name=name,
        already_imported=result.already_imported,
        new_rows=result.new_rows,
        skipped_rows=result.skipped_rows,
        ledger_entries=result.ledger_entries,
        suspected_duplicates=[
            SuspectedDuplicateOut(date=s.date, movement=s.movement, product=s.product)
            for s in result.suspected_duplicates
        ],
    )


def clean_file_name(raw: str | None) -> str:
    """Só o nome (sem pastas), sem caracteres de controle, até 255 caracteres."""
    name = re.split(r"[/\\]", raw or "")[-1]
    name = _CONTROL_CHARS.sub("", name).strip()
    if len(name) > MAX_FILE_NAME:
        stem, dot, ext = name.rpartition(".")
        name = stem[: MAX_FILE_NAME - len(ext) - 1] + dot + ext if dot else name[:MAX_FILE_NAME]
    return name or "extrato.xlsx"
