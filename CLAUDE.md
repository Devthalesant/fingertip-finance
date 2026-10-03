# Fingertip Finance

Webapp de finanças. Consolida investimentos de várias fontes (B3, bancos, exterior)
numa visão só, **avisa o que importa** (insights) e controla e categoriza gastos do
cartão. Integra com APIs externas (Banco Central, dados de mercado, Open Finance via
Pluggy). Serve de portfólio (posts no LinkedIn a cada versão) e mira **monetização**:
a parte de investimentos vira produto multiusuário com mensalidade (ADR 0002); gastos
e Pluggy ficam como módulo pessoal do dono por enquanto. O repositório é **público**
hoje e será fechado.

## Visão do produto

Nasceu do descontentamento com o app do Itaú (Ion), ruim para acompanhar investimentos,
e da falta de detalhe em apps como o da Rico. O diferencial não é "ver os números", é o
app **dizer algo útil**:

- **Copiloto da carteira:** feed de insights gerado no backend (destaques do dia,
  maiores perdas, concentração, vencimentos de renda fixa, proventos, divergência com a
  B3, limite de isenção de R$ 20 mil em vendas de ações no mês). Novos insights são
  mapeados ao longo do desenvolvimento.
- **Rentabilidade de verdade:** TWR e TIR, comparadas com CDI, IPCA e IBOV.
- **IR:** apuração mensal (DARF de ações e FIIs; exterior pela Lei 14.754/2023) e
  rascunho de "Bens e Direitos" para a declaração anual.
- **Gastos:** cartão de crédito Itaú (atual) e Rico (histórico, usado antes),
  categorização e KPIs customizáveis.
- **KPI que une as duas metades:** taxa de poupança (aportes ÷ renda) e evolução do
  patrimônio líquido.

**Qualidade visual é requisito**, não enfeite: o app tem que ser bonito e agradável de
usar, mobile-first (o uso principal é no celular), instalável como PWA.

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
- Decisões de arquitetura relevantes viram um ADR curto em `docs/adr/`
  (contexto, decisão, consequências).
- Informações pessoais de contexto ficam em `CLAUDE.local.md` (não versionado).
- Ao explicar código, use linguagem simples e analogias (planilha, ata etc.); sem
  jargão solto. Depois de um bloco de trabalho, explique o que foi feito e por quê
  antes de pedir a próxima decisão.

## Regras de segurança (repo público)

- **Nunca commitar:** `data/`, `.env*` (exceto `.env.example`), CSV, XLSX, PDF, OFX,
  chaves. O `.gitignore` protege e o **gitleaks** (pre-commit) bloqueia segredos no
  conteúdo, mas confira o `git status` antes de todo commit.
- **Nunca imprimir, logar ou repetir** connection strings, senhas ou tokens.
- **Não ler arquivos de `data/`** a menos que o dono peça explicitamente. Eles têm
  dados financeiros reais (os PDFs da Nomad têm nome e endereço).
- Testes, exemplos, docs, prints e mensagens de commit usam **só dados sintéticos**
  (`sample_data/`). Nada de posições, valores ou ativos reais do dono.
- **Segredos só no backend.** O frontend nunca fala direto com o banco nem com APIs
  que exigem credencial (Pluggy, brapi etc.). Toda integração passa pelo backend.
- No Next.js, variáveis `NEXT_PUBLIC_*` vão para o navegador: **nunca** coloque
  segredo nelas. A única prevista é a URL da API.
- Não dar a um agente acesso ao banco (MCP do Neon, `neon init`, `neon deploy`) nem
  adicionar ferramentas do Neon ao projeto sem pedir. O banco é acessado só via
  `DATABASE_URL`, pelo código do backend (API ou jobs).
- **Dois ambientes, dois bancos:** `demo` (dados sintéticos, link público no
  portfólio) e `prod` (dados reais, com login). Nunca misturar.
- **API autenticada desde o início**, mesmo em dev. Multiusuário em beta fechado: login
  (Auth.js com Google/GitHub ou passkey) aceita só e-mails convidados; o FastAPI valida
  o token. Toda consulta a dados do usuário filtra por `user_id` (ADR 0002).
- Banco com papéis separados: um com privilégio mínimo para a aplicação, outro para
  as migrations. Backups (`pg_dump`) sempre criptografados.
- A interface tem **modo "ocultar valores"** (privacidade e prints para o LinkedIn).

## Arquitetura

```
 Navegador ──> frontend (Next.js + TypeScript) ──HTTP/JSON──> backend (FastAPI)
                                                                 │
                                          ┌──────────────────────┼─────────────────┐
                                          ▼                      ▼                 ▼
                                   Postgres (Neon)      Dados de mercado       Pluggy
                                          ▲             (BCB, brapi, Tesouro,  (Open Finance)
                                          │              CVM)
                          jobs agendados (GitHub Actions cron)
```

- **Backend (Python)** é a fonte da verdade: parsers, ledger, motor de cálculo,
  insights, integrações e API REST.
- **Frontend (TypeScript)** só apresenta e interage. **Nenhum cálculo financeiro no
  frontend** além de formatação: PM, resultado, rentabilidade e insights vêm prontos
  da API.
- **Jobs agendados** (cotações diárias, sincronização Pluggy) rodam no GitHub Actions
  com cron, executando um comando do backend (`python -m app.jobs.<job>`) que grava
  direto no Neon. Não dependem da API estar acordada (hospedagem gratuita dorme).
  O `DATABASE_URL` fica nos Secrets do GitHub.
- **Dados de mercado atrás de uma interface de provedor**, com implementações
  trocáveis (fontes gratuitas mudam ou caem). Cotações são gravadas no banco, nunca
  buscadas a cada tela aberta. Fontes previstas, todas gratuitas: SGS e PTAX do Banco
  Central, brapi.dev (plano grátis, 1 atualização/dia basta), Tesouro Transparente,
  CVM dados abertos.
- **Contrato tipado:** o FastAPI gera o schema OpenAPI; o frontend gera seus tipos a
  partir dele (`openapi-typescript`). Mudou a API, regenera os tipos.
- **Dinheiro:** `NUMERIC`/`Decimal` no banco e no Python, nunca `float`. A API envia
  valores monetários como **string decimal** (ex.: `"1234.56"`); o frontend só formata
  com `Intl.NumberFormat("pt-BR")`.

## Stack

**Backend** (`backend/`, Python 3.12, gerenciado com **uv**)
- FastAPI + Uvicorn, SQLAlchemy 2.x + Alembic, psycopg 3, pydantic-settings.
- pandas, openpyxl, pdfplumber (parsers); httpx (APIs externas).
- Dev: pytest, ruff, pre-commit (gitleaks, ruff, checagens básicas).
- Dependências em `backend/pyproject.toml`, versões exatas travadas em `backend/uv.lock`
  (versionado). Ambiente em `backend/.venv`.
- Comandos (dentro de `backend/`): `uv sync` (instala), `uv run pytest`,
  `uv run ruff check .`, `uv add <pacote>` (adiciona dependência, pedir antes).
- Hooks: `uv run pre-commit install` (uma vez por clone).

**Frontend** (`frontend/`, a criar na v0.1; Node LTS, npm)
- Next.js (App Router) + TypeScript em modo `strict`. PWA instalável.
- Tailwind CSS + shadcn/ui (componentes). Gráficos com shadcn/ui Charts (Recharts);
  Lightweight Charts para a série de preço do ativo.
- TanStack Query para busca e cache de dados da API (atualização reativa).
- `openapi-typescript` + `openapi-fetch` para o cliente tipado da API.
- ESLint + Prettier; Vitest + Testing Library; Playwright depois.
- Usar as versões estáveis atuais no momento do scaffold (`create-next-app`).

**Design** (definido antes do scaffold do frontend)
- Identidade: paleta com tokens, dark mode desde o início, tipografia com números
  tabulares (Geist ou Inter).
- Wireframes das telas: Visão geral, Carteira, Ativo, Proventos, Renda fixa, Exterior,
  IR, Gastos, Conciliação.
- Padrões financeiros: alta/baixa com cor **e** ícone (acessibilidade), valores
  alinhados à direita, estados de carregamento e vazio pensados.

**Banco:** Postgres 18 no **Neon** (plano gratuito). É Postgres padrão, então migrar
depois é `pg_dump` + `restore`.
- O Neon "dorme" após 5 min parado: a 1ª conexão demora mais. Use retry.
- Configuração em `backend/app/config.py`, lendo `DATABASE_URL` do `.env` da raiz.
- O Neon entrega `postgresql://...`; o SQLAlchemy com psycopg 3 exige
  `postgresql+psycopg://`. Converta **no código**, não edite o `.env`.
- Teste de conexão: `cd backend && uv run python check_db.py`.
- **Migrations (Alembic)**, dentro de `backend/`: `uv run alembic upgrade head` (aplica),
  `uv run alembic current` (versão do banco), `uv run alembic downgrade -1` (desfaz a
  última), `uv run alembic upgrade head --sql` (só gera o SQL, sem banco). A URL vem do
  `.env` via `app.config`, nunca do `alembic.ini`. Modelos em `app/models/` (ver ADR 0001).
- **Ambientes:**
  - `dev`: Postgres local (Postgres.app, **a instalar** antes dos testes do parser).
  - `demo`: o projeto atual no Neon, branch **`demo`** (renomeada de `production`).
    Só dados sintéticos. É o banco do `.env` hoje, com a migration inicial aplicada.
    Usuário atual é o dono (`*_owner`); serve para o demo.
  - `prod`: **outro projeto** no Neon (credenciais separadas), criado só quando for
    importar dados reais. Antes disso, papéis separados: migrations e app com
    privilégio mínimo.
- Testes nunca usam o banco real: `tests/conftest.py` troca o `DATABASE_URL` por uma
  URL falsa.

**Qualidade e CI:** GitHub Actions rodando lint, testes e build a cada PR. Secret
scanning com push protection e Dependabot ativos no GitHub.

**Hospedagem (v1.0):** frontend na Vercel; backend no Google Cloud Run (cold start
curto e cota gratuita). Custo esperado: zero (domínio próprio opcional).

## Estrutura

```
backend/        app/config.py, app/models/ (15 tabelas), alembic/ (migrations), tests/,
                check_db.py. API, parsers, motor e jobs virão aqui
frontend/       Next.js + TypeScript (a criar)
infra/          configs de deploy (futuro)
data/           LOCAL, ignorado pelo Git: raw/ (originais) e processed/ (CSVs padronizados)
sample_data/    gerador de dados sintéticos (generate.py), versionado (a criar)
docs/           diagramas, ADRs (docs/adr/) e prints com dados falsos, versionados
scratch/        rascunhos locais, ignorado (build_b3.py é o protótipo do parser B3)
```

## Fontes de dados

| Fonte | O que traz | Status |
|---|---|---|
| B3, extrato de movimentação (xlsx) | todos os ativos custodiados na B3, 2020 em diante, todas as corretoras | em `data/raw` |
| B3, relatórios consolidados mensais e anuais (xlsx) | snapshots de posição e proventos | em `data/raw` |
| Itaú, internet banking | CDBs que não aparecem na B3 | manual (print) |
| Nomad, extratos mensais e relatório de IR (PDF) | exterior (USD), dividendos, IR retido | em `data/raw` |
| Rico/XP, notas de corretagem e extratos | custos de transação (corretagem, emolumentos) e histórico anterior | **a obter** |
| Itaú, fatura do cartão (CSV/OFX) | gastos atuais | a obter; depois via Pluggy |
| Rico, faturas do cartão | histórico de gastos (cartão usado antes do Itaú) | a obter |

## Decisões de modelagem

1. **Ledger primeiro, em camadas.** Arquivo importado (com hash do arquivo) → linha
   bruta imutável (com hash) → lançamento normalizado (derivado, reprocessável, com a
   versão do parser). Reimportar períodos sobrepostos não duplica. Posição, PM e
   resultado são **sempre calculados** a partir do ledger, nunca armazenados como
   verdade.
2. **Hash de linha inclui índice de ocorrência.** O extrato da B3 tem linhas legítimas
   e idênticas (mesmo dia, ativo, tipo e valor). O hash é do conteúdo normalizado +
   fonte + ordem da ocorrência daquele conteúdo no arquivo, senão lançamentos reais
   seriam descartados.
3. **PM é por investidor e ativo, não por corretora** (critério da Receita). Custódia
   (onde está) e custo (quanto custou) são dimensões separadas; transferência entre
   corretoras mantém o custo.
4. **Custo de aquisição inclui custos de transação** (corretagem, emolumentos), que vêm
   das notas de corretagem, não do extrato da B3.
5. **Snapshots de conciliação.** Os relatórios mensais e anuais da B3 são checkpoints.
   Se a quantidade calculada divergir do snapshot, sinalizar.
6. **Multimoeda.** Cada ativo tem moeda. A consolidação em BRL usa a PTAX do Banco
   Central da data. Exterior é categoria fiscal própria (Lei 14.754/2023: 15% sobre o
   resultado anual líquido).
7. **Uma posição pode aparecer em duas fontes** (ex.: um CDB na B3 e no banco).
   Deduplicar por data + valor + vencimento.
8. **Tabela curada de eventos corporativos** (desdobro, grupamento, troca de ticker,
   cisão, incorporação), alimentada manualmente quando surgir um caso novo.
9. **Aliases e classes de ativo em tabela**, não no código. Inferir classe pelo sufixo
   do ticker falha: "11" pode ser FII, unit (TAEE11), ETF (BOVA11); "34" é BDR.
10. **Direitos de subscrição têm ciclo próprio** (recebido, cedido, exercido,
    expirado) e são frequentes nos dados; modelar explicitamente.
11. **Insights são dados do backend:** cada regra gera itens tipados (tipo, severidade,
    título, ativo, explicação, data). O frontend só renderiza o feed.
12. **Um parser por fonte**, isolado, com testes em fixtures sintéticas.

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
- O extrato não traz corretagem nem emolumentos (ver decisão 4).
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

**Cartão de crédito (a validar quando houver dados)**
- Compra parcelada: cada parcela cai numa fatura. Separar data da compra (competência)
  da fatura em que aparece (caixa).
- Estornos e créditos na fatura não são receita.
- Compras internacionais: IOF e câmbio da data de fechamento.
- Pagamento da fatura na conta corrente não é gasto (evitar contar duas vezes).

## Dados processados (`data/processed/`, locais)

Colunas dos CSVs (valores reais nunca vão para o repo):

- `b3_ledger.csv`: data, tipo, tipo_original, ativo, ticker_original, codigo_titulo,
  classe, instituicao, entrada_saida, quantidade, preco_brl, valor_brl, afeta_posicao,
  qtd_apos, pm_apos, resultado_realizado_brl, obs, fonte.
  Tipos normalizados incluem COMPRA, VENDA, ALUGUEL_SAIDA, ALUGUEL_RETORNO,
  ALUGUEL_REGISTRO, ALUGUEL_REMUNERACAO, REEMBOLSO_ALUGUEL, RENDIMENTO, JCP, DIVIDENDO,
  JUROS, AMORTIZACAO, BONIFICACAO, DESDOBRO, GRUPAMENTO, ATUALIZACAO, INCORPORACAO,
  FRACAO_BAIXA, LEILAO_FRACAO, RESGATE, SUBSCRICAO_*, DIREITO_*,
  TRANSFERENCIA_CUSTODIA, EVENTO_EXCLUIDO.
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

Entregas em **fatias verticais**: cada versão vai do banco até a tela e rende um post.

- [x] Fase 0: repositório, `.gitignore`, dependências
- [x] Fase 1: Postgres no Neon, config por `.env`, `check_db.py`
- [x] Fundação: uv + lockfile, pre-commit com gitleaks, `.gitignore` pronto p/ frontend
- [ ] **v0.1 Carteira B3** ← em andamento
  - [x] Schema aprovado (ADR 0001), modelos SQLAlchemy, migration inicial aplicada no demo
  - [x] Multiusuário (ADR 0002): `app_user`, `user_id` nas tabelas do usuário, ativo
        privado; migration `d29a1ab84532` (aplicar no demo)
  - [ ] **Próximo:** gerador `sample_data/generate.py` (ver seção abaixo)
  - [ ] Postgres local (Postgres.app) para testes que gravam no banco
  - [ ] Parser B3 (a partir de `scratch/build_b3.py`) e motor de PM
  - [ ] Primeiros endpoints, design (identidade + wireframes), scaffold do frontend,
        tela "Carteira" (dados sintéticos), CI
- [ ] v0.2 Mercado: cotações diárias (job agendado), benchmarks BCB, Visão geral
      (patrimônio, alocação, comparação com CDI/IPCA/IBOV), TWR e TIR
- [ ] v0.3 Renda fixa e exterior: CDBs (marcação na curva), Nomad (PTAX), notas de
      corretagem Rico/XP, tela de Conciliação
  - CDBs fora da B3, para qualquer banco: o usuário informa só 5 campos (valor, data,
    vencimento, indexador, taxa) e o backend calcula o saldo pela série do CDI. Entrada
    por formulário curto (com "duplicar" para aportes recorrentes), planilha modelo para
    lote e conferência periódica do saldo informado pelo banco (diverge → sinaliza)
  - Logo depois, como diferencial: print do app do banco → IA extrai os campos → usuário
    confirma (opcional; constar na política de privacidade). Open Finance só com receita
- [ ] v0.4 Insights e proventos: feed de insights, calendário e histórico de proventos
- [ ] v0.5 Gastos: importação das faturas Itaú (atual) e Rico (histórico), categorização
      por regras, KPIs customizáveis, taxa de poupança
- [ ] v0.6 Pluggy: cartão e conta Itaú via Open Finance, sincronização agendada
- [ ] v0.7 IR: apuração mensal, DARF, rascunho de Bens e Direitos
- [ ] v1.0 Deploy: autenticação, ambientes demo e prod, backups, README de portfólio
      com demo pública e dataset sintético

Depois: categorização com ML, alertas por push (PWA), novos insights.

## v0.1: decisões já tomadas (não rediscutir)

- **Schema:** 14 tabelas em 4 grupos (cadastro, importação/ledger, eventos,
  conciliação/mercado) mais `app_user`. Detalhes e motivos nos ADRs 0001 e 0002. A tabela
  `dividend_announcement` (proventos anunciados) fica para a v0.4.
- **Ativo novo vindo de importação** entra como `A_CLASSIFICAR`; o admin classifica uma
  vez e vale para todos (catálogo pré-carregado com a lista pública da B3/CVM).
- **Lançamento manual + importação, modelo híbrido:** compra lançada à mão na hora
  (`origin = MANUAL`, com quantidade e valor total da nota, que já inclui os custos);
  o extrato da B3 importado depois traz proventos e eventos e casa com o manual via
  `duplicate_of_id`. Importação não precisa ser mensal; períodos sobrepostos são
  deduplicados pelo hash.
- **Proventos:** recebido e anunciado são exatos (valor por cota × quantidade na data
  com); não anunciado é projeção pelo histórico. A tela mostra confirmado e estimado
  separados.

## v0.1: próximo passo, o gerador de `sample_data/`

Aprovado pelo dono. `sample_data/generate.py`, determinístico, gera xlsx sintéticos no
**formato exato do extrato de movimentação da B3**; os testes e o seed do demo chamam o
gerador (o xlsx gerado não precisa ser versionado). Investidor fictício desde 2021,
duas corretoras fictícias (com grafias variadas), 12 a 15 ativos com **tickers reais e
públicos** e quantidades e preços inventados. Carteira **diferente da do dono**.
Cenários obrigatórios: compras e vendas com lucro e prejuízo; linhas idênticas no
mesmo dia; aluguel (saída, remuneração, retorno, reembolso de provento); desdobro,
grupamento, bonificação; troca de ticker; direito exercido e direito expirado;
transferência entre corretoras; rendimentos de FII, dividendos, JCP; mês com vendas
acima de R$ 20 mil; consolidado mensal com uma divergência proposital; CDB, LCA,
Tesouro. Nomad fica para a v0.3.

Commits feitos por você não devem carregar a mensagem de coautoria do Claude.
