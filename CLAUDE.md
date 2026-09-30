# Fingertip Finance

Webapp pessoal de finanças, para uso de uma única pessoa. Consolida investimentos de
várias fontes (B3, bancos, exterior) numa visão só, com dashboards reativos, e depois
controla e categoriza gastos. Integra com APIs externas (Banco Central, Open Finance
via Pluggy). O repositório é **público** e também serve de portfólio.

## Como trabalhar comigo

- O dono é economista e está aprendendo engenharia de software com este projeto.
  Explique o **porquê** das decisões. Passos pequenos, um de cada vez.
- Proponha antes de mudar algo grande (schema, dependências, estrutura de pastas,
  contrato da API). Espere aprovação.
- Quem faz os commits é o dono. Se for commitar, pergunte antes e rode `git status`
  primeiro. Mensagens em Conventional Commits (`feat`, `fix`, `chore`, `docs`, `test`),
  com escopo quando ajudar: `feat(api): ...`, `feat(web): ...`.
- Conversa e documentação em português. Identificadores de código em inglês, exceto
  termos de domínio sem boa tradução (provento, PM, aluguel).
- Informações pessoais de contexto ficam em `CLAUDE.local.md` (não versionado).

## Regras de segurança (repo público)

- **Nunca commitar:** `data/`, `.env*` (exceto `.env.example`), CSV, XLSX, PDF, OFX,
  chaves. O `.gitignore` protege, mas confira o `git status` antes de todo commit.
- **Nunca imprimir, logar ou repetir** connection strings, senhas ou tokens.
- **Não ler arquivos de `data/`** a menos que o dono peça explicitamente. Eles têm
  dados financeiros reais.
- Testes, exemplos, docs, prints e mensagens de commit usam **só dados sintéticos**
  (`sample_data/`). Nada de posições, valores ou ativos reais do dono.
- **Segredos só no backend.** O frontend nunca fala direto com o banco nem com APIs
  que exigem credencial (Pluggy etc.). Toda integração passa pelo FastAPI.
- No Next.js, variáveis `NEXT_PUBLIC_*` vão para o navegador: **nunca** coloque
  segredo nelas. A única prevista é a URL da API.
- Não dar a um agente acesso ao banco (MCP do Neon, `neon init`, `neon deploy`) nem
  adicionar ferramentas do Neon ao projeto sem pedir. O banco é acessado só via
  `DATABASE_URL`, pelo backend.

## Arquitetura

```
 Navegador ──> frontend (Next.js + TypeScript) ──HTTP/JSON──> backend (FastAPI)
                                                                 │
                                          ┌──────────────────────┼─────────────────┐
                                          ▼                      ▼                 ▼
                                   Postgres (Neon)      APIs do Banco Central   Pluggy
                                                        (CDI, IPCA, PTAX)       (Open Finance)
```

- **Backend (Python)** é a fonte da verdade: parsers, ledger, motor de cálculo,
  integrações e API REST.
- **Frontend (TypeScript)** só apresenta e interage. **Nenhum cálculo financeiro no
  frontend** além de formatação: PM, resultado, rentabilidade vêm prontos da API.
- **Contrato tipado:** o FastAPI gera o schema OpenAPI; o frontend gera seus tipos a
  partir dele (`openapi-typescript`). Mudou a API, regenera os tipos.
- **Dinheiro:** `NUMERIC`/`Decimal` no banco e no Python, nunca `float`. A API envia
  valores monetários como **string decimal** (ex.: `"1234.56"`); o frontend só formata
  com `Intl.NumberFormat("pt-BR")`.

## Stack

**Backend** (`backend/`, Python 3.12, venv na raiz: `source venv/bin/activate`)
- FastAPI + Uvicorn, SQLAlchemy 2.x + Alembic, psycopg 3, pydantic-settings.
- pandas, openpyxl, pdfplumber (parsers); httpx (APIs externas).
- Dev: pytest, ruff, pre-commit (gitleaks planejado).
- Dependências fixadas em `backend/requirements.txt` e `requirements-dev.txt`.

**Frontend** (`frontend/`, a criar na Fase 6; Node LTS, npm)
- Next.js (App Router) + TypeScript em modo `strict`.
- Tailwind CSS + shadcn/ui (componentes).
- TanStack Query para busca e cache de dados da API (atualização reativa).
- Recharts para gráficos (reavaliar ECharts ou Lightweight Charts se precisar de
  séries financeiras pesadas).
- `openapi-typescript` + `openapi-fetch` para o cliente tipado da API.
- ESLint + Prettier; Vitest + Testing Library; Playwright depois.
- Usar as versões estáveis atuais no momento do scaffold (`create-next-app`).

**Banco:** Postgres 18 no **Neon** (plano gratuito). É Postgres padrão, então migrar
depois é `pg_dump` + `restore`.
- O Neon "dorme" após 5 min parado: a 1ª conexão demora mais. Use retry.
- Configuração em `backend/app/config.py`, lendo `DATABASE_URL` do `.env` da raiz.
- O Neon entrega `postgresql://...`; o SQLAlchemy com psycopg 3 exige
  `postgresql+psycopg://`. Converta **no código**, não edite o `.env`.
- Teste de conexão: `cd backend && python check_db.py`.

**Hospedagem (Fase 9, a decidir):** frontend em plano gratuito com suporte a Next.js
(ex.: Vercel); backend em serviço gratuito compatível com FastAPI.

## Estrutura

```
backend/        FastAPI: app/config.py, check_db.py (API, parsers e motor virão aqui)
frontend/       Next.js + TypeScript (a criar)
infra/          configs de deploy (futuro)
data/           LOCAL, ignorado pelo Git: raw/ (originais) e processed/ (CSVs padronizados)
sample_data/    dados sintéticos, versionados (a criar)
docs/           diagramas e prints com dados falsos, versionados
scratch/        rascunhos locais, ignorado
```

## Decisões de modelagem

1. **Ledger primeiro.** Cada linha bruta importada é gravada de forma imutável, com
   hash para idempotência: reimportar períodos sobrepostos não duplica. Posição, PM e
   resultado são **sempre calculados** a partir do ledger, nunca armazenados como
   verdade.
2. **Snapshots de conciliação.** Os relatórios mensais e anuais da B3 são checkpoints.
   Se a quantidade calculada divergir do snapshot, sinalizar.
3. **Multimoeda.** Cada ativo tem moeda. A consolidação em BRL usa a PTAX do Banco
   Central da data. Exterior é categoria fiscal própria (Lei 14.754/2023: 15% sobre o
   resultado anual líquido).
4. **Uma posição pode aparecer em duas fontes** (ex.: um CDB na B3 e no banco).
   Deduplicar por data + valor + vencimento.
5. **Tabela curada de eventos corporativos** (desdobro, grupamento, troca de ticker,
   cisão, incorporação), alimentada manualmente quando surgir um caso novo.
6. **Um parser por fonte**, isolado, com testes em fixtures sintéticas.

## Armadilhas nos dados (não redescobrir)

**B3, extrato de movimentação**
- Aluguel de ações vem com o mesmo rótulo de compra e venda ("Transferência -
  Liquidação"). Detectar: saída com transferência interna na mesma corretora, e um
  retorno posterior com a mesma quantidade. **Não é venda e não mexe no PM.**
- "Atualização" pode ser troca de ticker, ajuste de quantidade ou conversão de recibo.
  Tratar caso a caso pela tabela de eventos.
- Grupamento altera a quantidade (logo, o PM unitário), não o custo total.
- Bonificação: a B3 não informa o custo atribuído (assumido 0, sinalizar). Cisão: a B3
  não informa a divisão de custo (premissa: migra integralmente, sinalizar).
- Nomes de instituição variam entre arquivos e tickers mudam ao longo do tempo:
  normalizar e manter alias para um ticker canônico.
- Nos relatórios consolidados, o "Total" de renda fixa pode omitir títulos (o CRI vem
  numa coluna diferente, a mercado). Não confiar cegamente.
- Resultado realizado é **bruto** (antes de IR). Categorias fiscais distintas: ações,
  FIIs, exterior, renda fixa (LCA isenta; CDB na tabela regressiva).

**Renda fixa bancária**
- CDBs de aportes pequenos podem não aparecer na B3. A fonte é o extrato do banco e,
  depois, o Open Finance via Pluggy (plano pessoal "Meu Pluggy").
- A taxa contratada (% do CDI) não vem nos relatórios da B3. É dado manual por título.

**Exterior (Nomad)**
- O layout do extrato mensal mudou durante o ano: o template antigo mostra o dividendo
  **líquido** da retenção de 30%; o novo mostra o **bruto**. Normalizar para bruto + IR
  retido. Conferir contra o resumo do mês.
- Restituição de IR retido ("refund NRA W/H") é evento próprio, não dividendo.
- Custo de aquisição em USD e dólar médio vêm do relatório anual de IR, que serve de
  saldo inicial.
- Transferência de custódia entre corretoras não é compra nem venda.

## Dados processados (`data/processed/`, locais)

Colunas dos CSVs (valores reais nunca vão para o repo):

- `b3_ledger.csv`: data, tipo, tipo_original, ativo, ticker_original, codigo_titulo,
  classe, instituicao, entrada_saida, quantidade, preco_brl, valor_brl, afeta_posicao,
  qtd_apos, pm_apos, resultado_realizado_brl, obs, fonte.
  Tipos normalizados incluem COMPRA, VENDA, ALUGUEL_SAIDA, ALUGUEL_RETORNO,
  ALUGUEL_REMUNERACAO, RENDIMENTO, JCP, DIVIDENDO, JUROS, AMORTIZACAO, BONIFICACAO,
  DESDOBRO, GRUPAMENTO, ATUALIZACAO, INCORPORACAO, FRACAO_BAIXA, LEILAO_FRACAO,
  RESGATE, SUBSCRICAO_*, DIREITO_*, TRANSFERENCIA_CUSTODIA.
- `b3_posicao_<data>.csv`: data_ref, ativo, classe, instituicao, quantidade, pm_brl,
  custo_total_brl, preco_brl, valor_mercado_brl, resultado_nao_realizado_brl,
  resultado_pct, proventos_acumulados_brl, indexador, pct_indexador, vencimento, obs,
  fonte.
- `cdbs_itau_<data>.csv`: instituicao, produto, data_aplicacao, vencimento,
  valor_aplicado, indexador, pct_indexador, liquidez_diaria_desde, saldo_bruto,
  saldo_liquido, aparece_na_b3, fonte.
- `nomad_ledger_<ano>.csv`: data, data_liquidacao, tipo, ativo, quantidade, preco_usd,
  valor_bruto_usd, ir_retido_usd, valor_liquido_usd, custo_brl, dolar_medio, fonte.

## Roadmap

- [x] Fase 0: repositório, `.gitignore`, dependências, venv
- [x] Fase 1: Postgres no Neon, config por `.env`, `check_db.py`
- [ ] **Fase 2: modelagem de dados (SQLAlchemy + Alembic)** ← próxima
- [ ] Fase 3: ingestão (parsers B3, Itaú, Nomad) e conciliação com os snapshots
- [ ] Fase 4: motor de cálculo (PM, realizado e não realizado, proventos, benchmarks
      CDI/IPCA/IBOV via Banco Central, marcação na curva da renda fixa)
- [ ] Fase 5: API (FastAPI) com schema OpenAPI estável
- [ ] Fase 6: frontend (Next.js + TypeScript): scaffold, cliente tipado, dashboard de
      carteira (evolução patrimonial, alocação, comparação com benchmarks)
- [ ] Fase 7: gastos e categorização (regras primeiro, depois ML)
- [ ] Fase 8: Open Finance via Pluggy (sincronização agendada no backend)
- [ ] Fase 9: deploy, autenticação de usuário único, backups (`pg_dump`), README de
      portfólio com dataset sintético

As Fases 5 e 6 podem andar em paralelo: assim que existir um endpoint, o frontend
pode consumi-lo.

## Fase 2: por onde começar

Antes de escrever código, propor e discutir com o dono um schema com, no mínimo:
instituições/contas, ativos (classe, moeda, ticker canônico, aliases), lançamentos
brutos (ledger imutável com hash único), eventos corporativos, snapshots de posição,
cotações, taxas de câmbio (PTAX) e títulos de renda fixa (indexador, %, vencimento,
identificador externo).

Depois de aprovado: modelos SQLAlchemy, `alembic init`, primeira migration e testes
com `sample_data/`.

Commits feitos por você não devem carregar a mensagem de coautoria do CLaude.
