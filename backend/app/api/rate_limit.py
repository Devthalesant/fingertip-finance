"""Limite de requisições por usuário (ADR 0004).

Janela deslizante: guarda o horário das últimas requisições aceitas de cada pessoa, por
"balde" (api, upload). Passou do limite dentro da janela → 429 com Retry-After. Fica em
memória: vale com uma instância só (beta). Com várias, mover para o banco.
"""

import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.api.deps import CurrentUserDep

# balde → (requisições, janela em segundos)
LIMITS: dict[str, tuple[int, int]] = {
    "api": (120, 60),
    # Cada upload abre um processo de quarentena: bem mais apertado.
    "upload": (10, 3600),
}


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[tuple[str, int], deque[float]] = defaultdict(deque)
        # Endpoints síncronos rodam em várias threads ao mesmo tempo.
        self._lock = threading.Lock()

    def hit(self, bucket: str, user_id: int, limit: int, window: float) -> float | None:
        """Registra a requisição; devolve None se passou ou quantos segundos esperar."""
        now = self._clock()
        with self._lock:
            hits = self._hits[(bucket, user_id)]
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= limit:
                # Recusada não conta: insistir não empurra a liberação para frente.
                return hits[0] + window - now
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def limited(bucket: str):
    """Dependência que conta a requisição no balde da pessoa logada."""

    def dependency(user: CurrentUserDep) -> None:
        max_requests, window = LIMITS[bucket]
        wait = limiter.hit(bucket, user.id, max_requests, window)
        if wait is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Muitas requisições. Tente de novo em instantes.",
                headers={"Retry-After": str(max(1, math.ceil(wait)))},
            )

    return Depends(dependency)
