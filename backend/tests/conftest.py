import os

# Os testes nunca usam o banco real: uma URL falsa tem prioridade sobre o .env.
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"
