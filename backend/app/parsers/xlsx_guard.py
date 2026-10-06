"""Raio-x do xlsx antes de abrir (ADR 0004, camada 1).

Um xlsx é um zip de XMLs. O índice do zip diz o nome, o tamanho comprimido e o tamanho
descompactado de cada peça, sem descompactar nada: dá para recusar bomba de zip, macro,
link externo e caminho estranho antes de o leitor tocar no arquivo. O zipfile do Python
não descompacta além do tamanho declarado (e confere o CRC), então o índice não mente
de um jeito que escape dos tetos daqui.
"""

import io
import zipfile
from collections import Counter

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_PARTS = 100
# Planilha comum comprime ~10:1. Taxa muito maior só em arquivo fabricado.
MAX_RATIO = 100
# Peças pequenas podem ter taxa alta sem perigo (o teto total já as cobre).
RATIO_MIN_BYTES = 64 * 1024
# Só XML e relações: macro (.bin), objeto embutido, imagem, zip dentro do zip ficam fora.
ALLOWED_SUFFIXES = (".xml", ".rels")
# Pastas de peças que buscam dados fora da planilha ou executam algo, mesmo em XML.
FORBIDDEN_PARTS = ("xl/externalLinks/", "xl/activeX/", "xl/embeddings/", "xl/ctrlProps/")
REQUIRED_PARTS = ("[Content_Types].xml", "xl/workbook.xml")
ZIP_SIGNATURE = b"PK\x03\x04"
ENCRYPTED_FLAG = 0x1

MESSAGES = {
    "too_big": "Arquivo grande demais (máximo de 5 MB).",
    "not_xlsx": "O arquivo não é um xlsx válido.",
    "zip_bomb": "O arquivo não parece uma planilha comum e foi recusado.",
    "too_many_parts": "O arquivo não parece uma planilha comum e foi recusado.",
    "unexpected_part": "O arquivo tem conteúdo que uma planilha de extrato não tem (macro, "
    "link externo ou objeto embutido) e foi recusado.",
}


class UnsafeFile(ValueError):
    """Arquivo recusado antes de abrir. `reason` vai para o log; a mensagem, para a tela."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(MESSAGES[reason])
        self.reason = reason
        self.detail = detail  # só para o log (nome da peça, tamanhos); nunca conteúdo


def inspect_xlsx(data: bytes) -> None:
    """Recusa (UnsafeFile) o que não for um xlsx comum; não devolve nada se passar."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise UnsafeFile("too_big", f"{len(data)} bytes")
    if not data.startswith(ZIP_SIGNATURE):
        raise UnsafeFile("not_xlsx", "sem assinatura de zip")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            parts = archive.infolist()
    except (zipfile.BadZipFile, EOFError, ValueError) as exc:
        raise UnsafeFile("not_xlsx", type(exc).__name__) from None

    if len(parts) > MAX_PARTS:
        raise UnsafeFile("too_many_parts", f"{len(parts)} peças")
    names = Counter(p.filename for p in parts)
    if missing := [n for n in REQUIRED_PARTS if n not in names]:
        raise UnsafeFile("not_xlsx", f"faltam {missing}")
    if repeated := [n for n, count in names.items() if count > 1]:
        raise UnsafeFile("unexpected_part", f"repetidas {repeated}")

    total = 0
    for part in parts:
        _check_part(part)
        total += part.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            raise UnsafeFile("zip_bomb", f"mais de {MAX_UNCOMPRESSED_BYTES} bytes ao abrir")


def _check_part(part: zipfile.ZipInfo) -> None:
    name = part.filename
    if (
        name.startswith("/")
        or "\\" in name
        or ":" in name
        or ".." in name.split("/")
        or not name.endswith(ALLOWED_SUFFIXES)
        or name.startswith(FORBIDDEN_PARTS)
    ):
        raise UnsafeFile("unexpected_part", name)
    if part.flag_bits & ENCRYPTED_FLAG:
        raise UnsafeFile("unexpected_part", f"{name} criptografada")
    if part.file_size > RATIO_MIN_BYTES and part.file_size > MAX_RATIO * max(part.compress_size, 1):
        raise UnsafeFile("zip_bomb", f"{name}: {part.file_size}/{part.compress_size}")
