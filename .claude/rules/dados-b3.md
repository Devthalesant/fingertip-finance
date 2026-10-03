---
paths:
  - "backend/app/parsers/**"
  - "backend/app/ledger/**"
  - "backend/app/engine/**"
  - "backend/sample_data/**"
  - "backend/tests/**/*b3*"
  - "backend/tests/**/*sample_data*"
  - "backend/tests/**/*parser*"
  - "backend/tests/**/*ledger*"
  - "scratch/**"
---

# Dados da B3: modelagem e armadilhas (não redescobrir)

## Decisões de modelagem
1. **Ledger em camadas** (ADR 0001): arquivo (hash) → linha bruta imutável (hash) →
   lançamento normalizado (derivado, com `parser_version`). Posição, PM e resultado são
   sempre calculados, nunca gravados como verdade.
2. **Hash de linha inclui índice de ocorrência**: o extrato tem linhas idênticas
   legítimas (mesmo dia, ativo, tipo e valor). Hash = conteúdo normalizado + fonte +
   ordem da ocorrência no arquivo.
3. **PM por investidor e ativo, não por corretora** (Receita). Custódia e custo são
   dimensões separadas; transferência entre corretoras mantém o custo.
4. **Custo de aquisição inclui corretagem e emolumentos**, que vêm das notas de
   corretagem (o extrato da B3 não traz).
5. **Consolidados mensais/anuais são checkpoints**: quantidade calculada ≠ snapshot →
   sinalizar.
6. **Mesma posição em duas fontes** (CDB na B3 e no banco): deduplicar por data + valor
   + vencimento (`duplicate_of_id`).
7. **Eventos corporativos em tabela curada**, alimentada quando surge caso novo.
8. **Aliases e classes de ativo em tabela**, nunca pelo sufixo: "11" pode ser FII, unit
   (TAEE11) ou ETF (BOVA11); "34" é BDR.
9. **Direitos de subscrição têm ciclo próprio** (recebido, cedido, exercido, expirado).
10. **Um parser por fonte**, isolado, testado com fixtures sintéticas (`sample_data/`).

## Extrato de movimentação: formato
- Colunas: Entrada/Saída, Data, Movimentação, Produto, Instituição, Quantidade, Preço
  unitário, Valor da Operação. Aba `Movimentação`.
- Data como **texto** `dd/mm/aaaa`; mais nova primeiro; ausente = texto `-`;
  `Credito`/`Debito` sem acento. openpyxl avisa "no default style" (silenciar).
- Produto: `TICKER - NOME`; renda fixa `TIPO - CÓDIGO - EMISSOR`; Tesouro por extenso.
- Nomes de instituição variam (ponto final, espaço duplo): normalizar por alias.
- Rótulos de renda fixa misturam caixa e acento (`AMORTIZAÇÃO`, `AMORTIZACAO
  PROGRAMADA`, `COMPRA / VENDA`, `COMPRA/VENDA`).

## Extrato: semântica
- **Aluguel** usa o rótulo da compra/venda (`Transferência - Liquidação`). Saída a débito
  **sem preço**; par interno de `Transferência` no mesmo dia e corretora; retorno
  posterior da mesma quantidade (preço só referência). Não é venda, não mexe no PM.
  `Empréstimo` sem valor = registro; com valor = remuneração. `Reembolso` = provento
  pago pelo tomador.
- `Transferência` com corretoras diferentes = transferência de custódia.
- **JCP vem líquido**: preço = bruto por ação, valor já sem 15% de IR. Dividendo e
  rendimento vêm brutos.
- Eventos vêm a crédito, sem preço. Desdobro e bonificação trazem as ações
  **recebidas**; grupamento traz a quantidade **resultante** (com fração, que sai em
  `Fração em Ativos` e volta em `Leilão de Fração` com valor).
- Troca de ticker: só um crédito de `Atualização` no ticker novo. "Atualização" também
  pode ser ajuste de quantidade ou conversão de recibo: tratar pela tabela de eventos.
- Grupamento muda a quantidade, não o custo total.
- Bonificação: a B3 não informa o custo atribuído (assumir 0 e sinalizar; o real vem do
  aviso aos acionistas). Cisão: a B3 não informa a divisão de custo (premissa: migra
  integralmente, sinalizar).
- Subscrição: direito → solicitação → exercido (pagamento, com preço) → recibo →
  atualização (recibo vira cota). Contar recibo **e** atualização dobra a quantidade.
- Resultado realizado é **bruto** (antes do IR).

## Consolidado mensal
- Abas: Posição - Ações / Empréstimos / Fundos / Renda Fixa, Proventos Recebidos,
  Negociações. Aba sem conteúdo não aparece.
- Produto com espaços sobrando no fim; aba termina com linha vazia, "Total" e o valor;
  quantidade de proventos como texto; célula vazia e `""` misturadas.
- Renda fixa: alguns títulos trazem o valor em duas colunas sem nome, fora de CURVA, e o
  **Total ignora esses títulos**. Não confiar no Total.

## CSVs do protótipo (`data/processed/`, locais; só colunas, nunca valores)
- `b3_ledger.csv`: data, tipo, tipo_original, ativo, ticker_original, codigo_titulo,
  classe, instituicao, entrada_saida, quantidade, preco_brl, valor_brl, afeta_posicao,
  qtd_apos, pm_apos, resultado_realizado_brl, obs, fonte.
- `b3_posicao_<data>.csv`: data_ref, ativo, classe, instituicao, quantidade, pm_brl,
  custo_total_brl, preco_brl, valor_mercado_brl, resultado_nao_realizado_brl,
  resultado_pct, proventos_acumulados_brl, indexador, pct_indexador, vencimento, obs,
  fonte.
- `scratch/build_b3.py` tem dados reais embutidos: reaproveitar só regras, nunca
  tickers, valores ou códigos.
