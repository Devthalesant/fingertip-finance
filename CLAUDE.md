# Fingertip Finance

Webapp de finanças: consolida investimentos de várias fontes (B3, bancos, exterior),
**avisa o que importa** (insights) e controla gastos do cartão. Portfólio (post no
LinkedIn a cada versão) e produto: a parte de investimentos vira multiusuário com
mensalidade (ADR 0002); gastos e Pluggy ficam como módulo pessoal do dono. Repo
público hoje, será fechado.

## Visão do produto
O diferencial não é "ver os números", é o app **dizer algo útil**:
- **Copiloto da carteira:** feed de insights do backend (destaques, perdas,
  concentração, vencimentos, proventos, divergência com a B3, limite de R$ 20 mil).
- **Rentabilidade de verdade:** TWR e TIR contra CDI, IPCA e IBOV.
- **IR:** apuração mensal (DARF de ações e FIIs; exterior pela Lei 14.754/2023) e
  rascunho de "Bens e Direitos".
- **Gastos:** cartão Itaú (atual) e Rico (histórico), categorização, KPIs.
- **Taxa de poupança** (aportes ÷ renda) e evolução do patrimônio.

**Qualidade visual é requisito**: bonito, mobile-first (uso principal no celular), PWA.

## Como trabalhar comigo
- O dono é economista aprendendo engenharia de software. Explique o **porquê**, com
  linguagem simples e analogias (planilha, ata); passos pequenos, um de cada vez.
  Depois de um bloco de trabalho, explique o que foi feito antes da próxima decisão.
- Proponha antes de mudar algo grande (schema, dependências, estrutura de pastas,
  contrato da API). Espere aprovação.
- Commits: pergunte antes e rode `git status`. Conventional Commits com escopo quando
  ajudar (`feat(api): ...`, `feat(web): ...`). **Sem** linha de coautoria do Claude.
- Português na conversa e na documentação; identificadores em inglês, exceto termos de
  domínio sem boa tradução (provento, PM, aluguel).
- Decisões de arquitetura viram ADR curto em `docs/adr/` (contexto, decisão,
  consequências).
- Contexto pessoal e preferências do dono: `CLAUDE.local.md` (não versionado).

## Segurança
- **Nunca commitar** `data/`, `.env*` (exceto `.env.example`), CSV, XLSX, PDF, OFX,
  chaves. `.gitignore` e **gitleaks** (pre-commit) protegem; confira o `git status`.
- **Nunca imprimir, logar ou repetir** connection strings, senhas ou tokens.
- **Não ler `data/`** sem pedido explícito: tem dados financeiros reais (PDFs da Nomad
  têm nome e endereço). Para inspecionar formato, usar máscara (letra → A, dígito → 9).
- Testes, exemplos, docs, prints e commits usam **só dados sintéticos**.
- **Segredos só no backend**: o frontend nunca fala com o banco nem com APIs que exigem
  credencial (Pluggy, brapi etc.).
- Nenhum agente recebe acesso ao banco (MCP do Neon, `neon init`, `neon deploy`) sem
  pedir. Banco só via `DATABASE_URL`, pelo código do backend.
- **Ambientes separados, nunca misturar:** `dev` (local), `demo` (sintético, público),
  `prod` (real, com login).
- **API autenticada desde o início.** Beta fechado: login (Auth.js com Google/GitHub ou
  passkey) só para e-mails convidados; o FastAPI valida o token. Toda consulta a dados
  do usuário filtra por `user_id` (ADR 0002).
- Banco com papéis separados (app com privilégio mínimo; migrations); backups
  criptografados. A interface tem modo **"ocultar valores"**.

## Arquitetura
```
 Navegador ──> frontend (Next.js) ──HTTP/JSON──> backend (FastAPI) ──> Postgres (Neon)
                                                   │                    ▲
                                    dados de mercado, Pluggy     jobs (GitHub Actions cron)
```
- **Backend é a fonte da verdade**: parsers, ledger, motor de cálculo, insights, API.
- **Frontend só apresenta**: nenhum cálculo financeiro além de formatação.
- **Jobs agendados** rodam `python -m app.jobs.<job>` no GitHub Actions e gravam direto
  no banco (não dependem da API acordada). `DATABASE_URL` nos Secrets do GitHub.
- **Dados de mercado atrás de interface de provedor** (trocável). Cotações gravadas no
  banco, nunca buscadas por tela. Fontes gratuitas: SGS e PTAX (BCB), brapi.dev,
  Tesouro Transparente, CVM.
- **Contrato tipado**: OpenAPI do FastAPI → tipos do frontend (`openapi-typescript`).
- **Dinheiro**: `NUMERIC`/`Decimal`, nunca `float`; na API, string decimal (`"1234.56"`).
  Multimoeda: cada ativo tem moeda; consolidação em BRL pela PTAX da data.
- **Insights são dados**: cada regra gera itens tipados (tipo, severidade, título,
  ativo, explicação, data); o frontend só renderiza o feed.

## Stack (detalhes nos arquivos indicados abaixo)
- Backend: Python 3.12 + uv, FastAPI, SQLAlchemy 2 + Alembic, psycopg 3, pytest, ruff.
- Frontend (a criar): Next.js + TypeScript strict, Tailwind + shadcn/ui, TanStack Query.
- Banco: Postgres 18 (local via Homebrew; Neon na nuvem). CI: GitHub Actions; secret
  scanning e Dependabot ativos. Hospedagem v1.0: Vercel + Google Cloud Run (custo zero).

## Onde está cada coisa
```
backend/        app/ (config, models: 15 tabelas), alembic/, tests/, sample_data/
frontend/       Next.js (a criar)
docs/           adr/ (decisões), roadmap.md (detalhe das versões)
data/           LOCAL, ignorado: raw/ (originais reais) e processed/ (CSVs)
scratch/        LOCAL, ignorado: build_b3.py (protótipo com dados reais)
estudo/         LOCAL, ignorado: material de estudo do dono (ver CLAUDE.local.md)
```
Referência carregada sob demanda (ler antes de mexer no assunto):
- `backend/CLAUDE.md`: comandos, banco, ambientes, migrations, gerador sintético.
- `.claude/rules/dados-b3.md`: modelagem do ledger e armadilhas do formato da B3.
- `.claude/rules/outras-fontes.md`: renda fixa bancária, Nomad, cartão.
- `.claude/rules/ir.md`: regras de IR (compensação de prejuízo, isenção).
- `.claude/rules/frontend.md`: stack do frontend e design.
- `.claude/skills/`: skills auditadas (fastapi, frontend-design, property-based-testing,
  test-driven-development, verification-before-completion) e a nossa `gabarito`.

## Roadmap (detalhes em `docs/roadmap.md`)
- [x] Fundação: repo, Neon, uv + lockfile, pre-commit com gitleaks
- [ ] **v0.1 Carteira B3** ← em andamento
  - [x] Schema (ADR 0001), multiusuário (ADR 0002), gerador sintético com gabarito
  - [x] Postgres 18 local instalado; contexto do Claude reorganizado; skills auditadas
  - [ ] **Próximo (ver "Próximos passos" em `docs/roadmap.md`):** 1) aprovar e montar
        os bancos locais + `.env` por ambiente; 2) parser B3 e motor de PM com TDD,
        gabarito e testes de propriedade
  - [ ] Endpoints, design, scaffold do frontend, tela Carteira, CI
- [ ] v0.2 Mercado · v0.3 Renda fixa e exterior · v0.4 Insights e proventos ·
      v0.5 Gastos · v0.6 Pluggy · v0.7 IR · v1.0 Deploy

## Decisões já tomadas (não rediscutir)
- Schema: 14 tabelas em 4 grupos + `app_user` (ADRs 0001 e 0002).
- Ativo novo de importação entra como `A_CLASSIFICAR`; o admin classifica uma vez, vale
  para todos (catálogo pré-carregado com a lista pública da B3/CVM).
- Lançamento manual + importação (híbrido): compra à mão (`origin = MANUAL`, valor da
  nota com custos); o extrato importado depois casa via `duplicate_of_id`. Períodos
  sobrepostos são deduplicados pelo hash.
- Proventos: recebido e anunciado são exatos; não anunciado é projeção. A tela separa
  confirmado de estimado.
