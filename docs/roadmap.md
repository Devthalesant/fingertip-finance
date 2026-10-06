# Roadmap

Entregas em **fatias verticais**: cada versão vai do banco até a tela e rende um post.
O resumo com o status atual fica no `CLAUDE.md`; aqui ficam os detalhes.

## Próximos passos (atualizado em 05/10/2026)

Feito em 05/10: bancos locais e `APP_ENV`; fixture `db_session`; a linha de montagem
da v0.1, sem banco nas três primeiras peças:
`app/parsers/b3_movimentacao.py` (leitor) → `app/ledger/classify.py` (classificador) →
`app/engine/positions.py` (motor de PM, prova contra o gabarito + Hypothesis) e
`app/ledger/importer.py` (grava as 3 camadas; reimportar não duplica; ledger refeito).

1. ~~Ligar banco e motor~~ (05/10): `app/ledger/portfolio.py` lê lançamentos e eventos
   curados; a prova do gabarito roda em memória **e** pelo banco
   (`sample_data/catalog.py` semeia catálogo e eventos da história).
2. Endpoints (carteira, importação), design, scaffold do frontend, tela Carteira, CI.

## Pendências e lembretes
- Skills na prática (parser e motor): `gabarito`, `test-driven-development` e
  `property-based-testing` orientaram certo; a sabotagem (mutação manual) achou um
  teste tautológico. Testes formais com o skill-creator ficaram para depois.
- Lançamento manual × ledger refeito: o `importer` apaga e refaz os lançamentos
  importados. O manual sempre aponta para um ativo do catálogo (ADR 0003), então o
  casamento é por `asset_id`, data e quantidade; falta decidir qual lado guarda o
  `duplicate_of_id` para não quebrar ao refazer.
  O casamento deve tolerar diferença de data (negociação em D, liquidação em D+2): outros
  apps duplicam a compra manual por comparar só a data.
- Linha alterada pela B3 entre dois exports (06/10): pesquisa não achou relato, mas o
  Kinvo não importa proventos e eventos da B3 "por causa da qualidade dos dados". O
  `importer` já guarda as duas versões e devolve `suspected_duplicates` (mesma data,
  sentido, movimentação e produto, hash diferente). Falta a tela/insight de conferência e
  testar com dois exports reais de mesmo período feitos em datas diferentes.
- **Lacuna no schema (resolver antes de cadastrar a 2ª emissão de um FII):**
  `subscription_offer.right_asset_id` é único, mas FII reusa o mesmo ticker de direito
  (ex.: KNRI12) a cada emissão. Uma 2ª oferta do KNRI não cabe. O motor não sofre (casa
  direito → recibo → ativo pelo código); é só o cadastro. Proposta: único por
  (direito, data de corte) — migration simples.
- **Primeira importação real (06/10):** o raio-x do upload só aceita peças `.xml` e
  `.rels` (o sintético é assim). Se o xlsx real da B3 trouxer outra peça (ex.: miniatura),
  a importação é recusada com `unexpected_part` no log: ajustar a lista com o nome visto.
- Nome canônico da instituição criada na importação = primeira grafia vista; o admin
  pode corrigir (a tabela de aliases é a verdade).
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
    Uso típico do dono: aporte quase todo mês, resgate quase nunca; o "duplicar"
    (mesmo banco, taxa e vencimento pré-preenchidos) é o caminho principal.
  - Explicação **muito clara** na tela: como preencher e a limitação (esse título não
    aparece nem na B3, só o usuário sabe dele; o saldo é calculado, não informado).
  - CDB que veio da B3 sem taxa: tarefa "complete a taxa" (uma vez por título), com
    passo a passo genérico de onde achar (nota de aplicação, app ou extrato do banco).
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
