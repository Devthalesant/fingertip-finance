# Backend (carregado quando se trabalha em `backend/`)

## Stack e comandos
Python 3.12 com **uv**. FastAPI + Uvicorn, SQLAlchemy 2.x + Alembic, psycopg 3,
pydantic-settings; pandas, openpyxl, pdfplumber (parsers); httpx (APIs externas).
Dev: pytest, ruff, pre-commit (gitleaks, ruff). `pyproject.toml` + `uv.lock`
(versionado); ambiente em `.venv`.

| Comando (em `backend/`) | Para quê |
|---|---|
| `uv sync` | instala |
| `uv run pytest` | testes |
| `uv run ruff check .` / `uv run ruff format .` | lint / formatação |
| `uv add <pacote>` | nova dependência (pedir antes) |
| `uv run pre-commit install` | hooks (uma vez por clone) |
| `uv run python check_db.py` | testa a conexão do ambiente (não imprime segredo) |
| `uv run python -m sample_data.generate` | gera os xlsx sintéticos em `sample_data/out/` |

## Banco e ambientes
- Config em `app/config.py`: `APP_ENV` escolhe o arquivo da raiz (`dev` padrão → `.env`,
  banco local `fingertip_dev`; `demo` → `.env.demo`, Neon; `prod` → `.env.prod`). Ex.:
  `APP_ENV=demo uv run alembic current`. O Neon entrega
  `postgresql://`; o código converte para `postgresql+psycopg://` (não editar o `.env`).
- O Neon dorme após 5 min: a 1ª conexão demora. Usar retry.
- `dev`: Postgres 18 local (Homebrew, `postgresql@18`). `demo`: Neon, branch `demo`,
  só dados sintéticos, migrations até `d29a1ab84532` aplicadas. `prod`: outro projeto
  no Neon, criado só ao importar dados reais, com papéis separados (app com privilégio
  mínimo, outro para migrations). Backups (`pg_dump`) criptografados.
- Testes nunca usam o banco do `.env`: `tests/conftest.py` troca o `DATABASE_URL` por
  URL falsa. Quem precisa de banco pede a fixture `db_session`: Postgres local
  `fingertip_test` (ou `TEST_DATABASE_URL`), recriado pelas migrations a cada rodada,
  tudo desfeito ao fim de cada teste (até commits). `tests/db.py` **recusa** host fora
  de `localhost` ou banco sem sufixo `_test`; com o Postgres desligado, os testes pulam.

## Migrations (Alembic)
- `uv run alembic upgrade head` (aplica), `current` (versão), `downgrade -1` (desfaz),
  `upgrade A:B --sql` (só gera SQL, p/ rodar no SQL Editor do Neon).
- URL vem do `.env` via `app.config`, nunca do `alembic.ini`. Modelos em `app/models/`.
- Nunca editar migration aplicada: criar nova. Constraints com nomes da
  `naming_convention`. Enums como texto + CHECK.
- Tabelas de dados do usuário usam `UserOwnedMixin` (`user_id`); o resto é catálogo
  compartilhado (ADR 0002). Teste em `tests/test_models.py` garante a lista.

## Skills do projeto (`.claude/skills/`, origem e versões no README de lá)
- `fastapi`: seguir, **exceto** SQLModel (usamos SQLAlchemy, ADR 0001) e `float` nos
  exemplos (dinheiro é `Decimal`).
- `test-driven-development`: vale para parser, motor e IR; exploração combinada com o
  dono fica fora da regra "apague o código".
- `gabarito`: método dos dados sintéticos e do gabarito à mão.

## Linha de montagem do extrato (v0.1)
`parsers/b3_movimentacao.py` lê (tipos e hash por linha) → `ledger/classify.py` dá o tipo
(aluguel, transferências, JCP bruto) → `engine/positions.py` calcula (sem banco; eventos
curados entram como `CuratedEvents`). `ledger/importer.py` grava as 3 camadas e refaz os
lançamentos importados a cada importação. Mudou o resultado do leitor ou do
classificador? Subir `PARSER_VERSION`. Rótulo novo da B3 = caso novo testado.

## Dinheiro
`Decimal` no Python, `NUMERIC` no banco (`MONEY` 18,2; quantidade e preço 28,10),
string decimal na API. Nunca `float`.

## Gerador sintético (`sample_data/`)
- `scenario.py`: a história do investidor fictício, um grupo de cenários por função.
- `expected.py`: **gabarito calculado à mão** e validado pelo dono. Nunca gerá-lo com
  código do app (um erro de PM apareceria nos dois lados).
- `b3_format.py`, `b3_consolidated.py`: o formato da B3, com as esquisitices. Saída
  determinística (mesmos bytes → mesmo SHA-256 no `import_file`).
- Tickers e eventos reais (fonte no comentário); quantidades, preços e proventos
  inventados. Ao incluir ativo, conferir eventos reais no período em que é mantido.
