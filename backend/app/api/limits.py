"""Corte de tamanho na porta (ADR 0004): a requisição grande é barrada enquanto chega.

Sem isso, o FastAPI receberia o corpo inteiro (gravando em arquivo temporário) antes de
o endpoint poder recusar. Confere o Content-Length declarado e, como ele pode mentir ou
faltar, conta os bytes que de fato chegam.
"""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.parsers.xlsx_guard import MAX_UPLOAD_BYTES

# O arquivo mais o envelope do formulário (multipart).
MAX_BODY_BYTES = MAX_UPLOAD_BYTES + 64 * 1024
TOO_LARGE = "Arquivo grande demais (máximo de 5 MB)."


class BodySizeLimit:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            response = JSONResponse({"detail": TOO_LARGE}, status_code=413)
            await response(scope, receive, send)
            return

        received = 0

        async def counted() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # HTTPException atravessa a leitura do corpo no FastAPI e vira 413.
                    raise HTTPException(status_code=413, detail=TOO_LARGE)
            return message

        await self.app(scope, counted, send)
