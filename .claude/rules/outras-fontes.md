---
paths:
  - "backend/app/parsers/**"
  - "backend/app/integrations/**"
  - "backend/sample_data/**"
---

# Fontes de dados além da B3

| Fonte | O que traz | Status |
|---|---|---|
| B3, extrato de movimentação (xlsx) | ativos custodiados na B3, 2020+, todas as corretoras | em `data/raw` |
| B3, consolidados mensais e anuais (xlsx) | snapshots de posição e proventos | em `data/raw` |
| Itaú, internet banking | CDBs que não aparecem na B3 | manual (print) |
| Nomad, extratos mensais e relatório de IR (PDF) | exterior (USD), dividendos, IR retido | em `data/raw` |
| Rico/XP, notas de corretagem e extratos | corretagem, emolumentos, histórico anterior | a obter |
| Itaú, fatura do cartão (CSV/OFX) | gastos atuais | a obter; depois Pluggy |
| Rico, faturas do cartão | histórico de gastos | a obter |

## Renda fixa bancária
- CDBs de aportes pequenos podem não aparecer na B3: fonte é o banco e, depois, o Open
  Finance (Pluggy, plano pessoal "Meu Pluggy").
- A taxa contratada (% do CDI) não vem nos relatórios da B3: dado manual por título.
- CSV local `cdbs_itau_<data>.csv`: instituicao, produto, data_aplicacao, vencimento,
  valor_aplicado, indexador, pct_indexador, liquidez_diaria_desde, saldo_bruto,
  saldo_liquido, aparece_na_b3, fonte.

## Exterior (Nomad)
- O template antigo do extrato mensal mostra dividendo **líquido** da retenção de 30%; o
  novo, **bruto**. Normalizar para bruto + IR retido; conferir com o resumo do mês.
- Restituição de IR retido ("refund NRA W/H") é evento próprio, não dividendo.
- Custo em USD e dólar médio vêm do relatório anual de IR (saldo inicial).
- Transferência de custódia entre corretoras não é compra nem venda.
- Os PDFs têm nome e endereço do dono: nunca ler sem pedido explícito.
- CSV local `nomad_ledger_<ano>.csv`: data, data_liquidacao, tipo, ativo, quantidade,
  preco_usd, valor_bruto_usd, ir_retido_usd, valor_liquido_usd, custo_brl, dolar_medio,
  fonte.

## Cartão de crédito (validar quando houver dados)
- Parcelada: cada parcela cai numa fatura; separar competência (compra) de caixa
  (fatura).
- Estornos e créditos na fatura não são receita.
- Internacional: IOF e câmbio da data de fechamento.
- Pagamento da fatura na conta corrente não é gasto (não contar duas vezes).
