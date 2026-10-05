# ADR 0003: Identidade do ativo (troca de ticker e lançamento manual)

- **Status:** aceito
- **Data:** 2026-10-05

## Contexto

O motor de PM (`app/engine/positions.py`) trata a troca de ticker como dois ativos: a
posição de VIIA3 "muda de casa" para BHIA3 na data do evento, levando quantidade e
custo. O comentário do modelo dizia o contrário ("troca de ticker não cria ativo novo",
um ativo só com o ticker antigo como alias). As duas formas funcionam, mas precisam
combinar antes de ligar o banco ao motor.

Também faltava definir como o usuário escolhe o ativo num lançamento manual: texto livre
abriria espaço para tickers digitados errado, ativos duplicados no catálogo e
lançamentos que nunca casam com o extrato importado (`duplicate_of_id`).

## Decisão

1. **Troca de ticker = dois ativos ligados por um evento curado.** VIIA3 e BHIA3 são
   linhas próprias em `asset`; a ligação é um `corporate_event` do tipo `TROCA_TICKER`
   (`source_asset_id` → `target_asset_id`, `ex_date`). O motor move a posição na data.
2. **`asset_alias` fica só para grafias do mesmo ticker** (variações de código na
   fonte), não para troca de ticker.
3. **Lançamento manual escolhe um ativo existente.** A tela pesquisa no catálogo e o
   usuário seleciona; não há ticker em texto livre. A busca inclui tickers antigos, com
   aviso ("antigo, hoje BHIA3"), para lançar compras anteriores à troca. Ativo que
   falta no catálogo entra pela importação (`A_CLASSIFICAR`) ou por pedido de inclusão
   ao admin.
4. **Em aberto:** renda fixa fora da B3 (ex.: CDB de banco) não tem ticker para
   pesquisar. Como ela entra será decidido à parte (v0.3).

## Consequências

- O histórico mostra o ticker da época (a compra foi de VIIA3, a venda de BHIA3), como
  no extrato e no informe de rendimentos.
- Cotações e proventos de cada ticker ficam no próprio ativo, sem regra de vigência.
- Cada troca de ticker precisa estar cadastrada; sem ela, o motor sinaliza
  `ATUALIZACAO_SEM_EVENTO` (melhor avisar do que somar quantidade errada).
- O catálogo guarda tickers que não negociam mais; visões "da empresa" (ganho total,
  proventos acumulados) seguem a corrente de eventos para juntar os tickers.
- Com o ativo sempre vindo do catálogo, casar lançamento manual com importado vira
  comparar `asset_id`, data e quantidade, sem adivinhar pelo texto.
