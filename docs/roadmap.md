# Roadmap

Entregas em **fatias verticais**: cada versão vai do banco até a tela e rende um post.
O resumo com o status atual fica no `CLAUDE.md`; aqui ficam os detalhes.

## Próximos passos (atualizado em 03/10/2026)

1. **Bancos locais** (proposta feita, aguardando o ok do dono):
   - o dono roda `createdb fingertip_dev` e `createdb fingertip_test`;
   - `.env` passa a apontar para o local; a URL do Neon vai para `.env.demo` (o dono
     move a linha; nunca imprimir). `app/config.py` escolhe o arquivo por `APP_ENV`
     (`dev` padrão, `demo`, depois `prod`);
   - fixture de testes com banco real: schema via `alembic upgrade head`, transação
     desfeita ao fim de cada teste, **recusa** URL fora de `localhost` ou banco sem
     sufixo `_test`, pula com aviso se o Postgres estiver desligado.
2. **Parser B3 + motor de PM** (v0.1), seguindo as skills `gabarito`,
   `test-driven-development` e `verification-before-completion`:
   - parser grava as 3 camadas (arquivo → linha bruta → lançamento), regras em
     `.claude/rules/dados-b3.md`; portar só regras de `scratch/build_b3.py`;
   - o motor faz a "prova" contra `sample_data/expected.py`;
   - testes de propriedade (skill `property-based-testing`): pedir ok para adicionar
     `hypothesis` como dependência de desenvolvimento.
3. Depois: endpoints, design, scaffold do frontend, tela Carteira, CI.

## Pendências e lembretes
- **Avaliar as skills na prática** ao escrever o parser (especialmente a `gabarito`: foi
  acionada? orientou certo?). Testes formais com o skill-creator ficaram para depois.
- **Outras skills do obra/superpowers** a consultar conforme a necessidade (copiar e
  auditar, como as atuais): `systematic-debugging` (bugs e testes falhando),
  `writing-plans` e `executing-plans` (tarefas grandes), `requesting-code-review` e
  `receiving-code-review`, `brainstorming` (antes de features novas),
  `finishing-a-development-branch`. Evitar `using-superpowers` (exige skill antes de
  qualquer resposta) e o pacote inteiro (hook em toda sessão).
- Conferir se o KNRI11 fez emissões depois da 8ª (2024): o investidor fictício o mantém
  até 2026.
- Formato da aba de Tesouro Direto no consolidado ainda desconhecido (fora do sintético).
- IR (v0.7): validar com contador que lucro de mês isento não consome prejuízo.

## Versões

 schema (ADR 0001), multiusuário (ADR 0002), gerador sintético,
  Postgres local, parser B3 (a partir de `scratch/build_b3.py`), motor de PM, primeiros
  endpoints, design (identidade + wireframes), scaffold do frontend, tela "Carteira"
  com dados sintéticos, CI.
- **v0.2 Mercado**: cotações diárias (job agendado), benchmarks BCB, Visão geral
  (patrimônio, alocação, comparação com CDI/IPCA/IBOV), TWR e TIR.
- **v0.3 Renda fixa e exterior**: CDBs (marcação na curva), Nomad (PTAX), notas de
  corretagem Rico/XP, tela de Conciliação.
  - CDBs fora da B3, para qualquer banco: o usuário informa 5 campos (valor, data,
    vencimento, indexador, taxa) e o backend calcula o saldo pela série do CDI.
    Formulário curto (com "duplicar" para aportes recorrentes), planilha modelo para
    lote, conferência periódica do saldo informado pelo banco (diverge → sinaliza).
  - Logo depois, como diferencial: print do app do banco → IA extrai os campos →
    usuário confirma (opcional; constar na política de privacidade). Open Finance só
    com receita.
- **v0.4 Insights e proventos**: feed de insights, calendário e histórico de proventos,
  tabela `dividend_announcement`.
- **v0.5 Gastos**: faturas Itaú (atual) e Rico (histórico), categorização por regras,
  KPIs customizáveis, taxa de poupança.
- **v0.6 Pluggy**: cartão e conta Itaú via Open Finance, sincronização agendada.
- **v0.7 IR**: apuração mensal, DARF, rascunho de Bens e Direitos.
- **v1.0 Deploy**: autenticação, ambientes demo e prod, backups, README de portfólio
  com demo pública e dataset sintético. Frontend na Vercel; backend no Google Cloud
  Run. Custo esperado: zero.
- **Depois**: categorização com ML, alertas por push (PWA), novos insights.
