"""Testa a conexão com o Postgres (Neon).

Uso (a partir da pasta backend/, com o venv ativo):
    python check_db.py

Não imprime a connection string nem a senha.
"""
import sys
import time

import psycopg

from app.config import settings

TENTATIVAS = 3


def conectar() -> tuple[str, str, str, bool, float]:
    """Abre a conexão e devolve (versão, banco, usuário, usa_ssl, latência)."""
    inicio = time.perf_counter()
    # Se o Neon estiver "dormindo" (scale-to-zero), a 1ª conexão demora mais.
    with psycopg.connect(settings.database_url, connect_timeout=15) as conn:
        latencia = time.perf_counter() - inicio
        usa_ssl = conn.pgconn.ssl_in_use
        with conn.cursor() as cur:
            cur.execute("select version(), current_database(), current_user")
            versao, banco, usuario = cur.fetchone()
    return versao, banco, usuario, usa_ssl, latencia


def main() -> int:
    ultimo_erro: Exception | None = None

    for tentativa in range(1, TENTATIVAS + 1):
        try:
            versao, banco, usuario, usa_ssl, latencia = conectar()
        except psycopg.OperationalError as exc:
            # Só erros de conexão (rede, servidor dormindo) valem nova tentativa.
            # Qualquer outro erro é bug e deve aparecer na hora.
            ultimo_erro = exc
            print(f"Tentativa {tentativa}/{TENTATIVAS} falhou: {type(exc).__name__}")
            time.sleep(2)
            continue

        print("Conexão OK")
        print(f"  banco:    {banco}")
        print(f"  usuário:  {usuario}")
        print(f"  SSL:      {'sim' if usa_ssl else 'NÃO (verifique sslmode=require)'}")
        print(f"  versão:   {versao.split(',')[0]}")
        print(f"  conexão em {latencia:.2f}s (tentativa {tentativa})")
        return 0

    print("\nNão foi possível conectar.")
    print(f"Último erro: {ultimo_erro}")
    print("Dicas: confira o DATABASE_URL no .env, o sslmode=require e se o projeto existe no Neon.")
    return 1


if __name__ == "__main__":
    sys.exit(main())