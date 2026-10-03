# Roadmap

Entregas em **fatias verticais**: cada versão vai do banco até a tela e rende um post.
O resumo com o status atual fica no `CLAUDE.md`; aqui ficam os detalhes.

- **v0.1 Carteira B3**: schema (ADR 0001), multiusuário (ADR 0002), gerador sintético,
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
