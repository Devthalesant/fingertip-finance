# ADR 0001: Ledger em camadas como fonte da verdade

- **Status:** aceito
- **Data:** 2026-10-01

## Contexto

Os dados de investimento chegam de várias fontes (extrato de movimentação e
consolidados da B3, PDFs da Nomad, lançamentos manuais de CDBs), com períodos
sobrepostos, nomes de instituição e tickers que mudam no tempo e linhas idênticas
legítimas. O protótipo `scratch/build_b3.py` mostrou dois problemas: grava quantidade
e PM acumulados em cada linha (um erro contamina tudo dali em diante) e trata eventos
especiais com `if` por ticker no código (cada caso novo exige mudar o parser).

## Decisão

1. **Três camadas de dados.**
   - `import_file`: o arquivo importado, identificado pelo SHA-256. O mesmo arquivo
     não entra duas vezes.
   - `raw_row`: a linha original (JSON), imutável. `row_hash` = conteúdo normalizado +
     fonte + índice de ocorrência daquele conteúdo no arquivo, único por fonte.
     Períodos sobrepostos não duplicam, e linhas idênticas legítimas não se perdem.
   - `ledger_entry`: lançamento normalizado, derivado, com `parser_version`. Pode ser
     apagado e regerado a partir das linhas brutas. Lançamentos manuais entram aqui
     com `origin = MANUAL` e sem linha bruta.
2. **Nada calculado é gravado como verdade.** Posição, PM e resultado são sempre
   recalculados pelo motor a partir do ledger. Os consolidados da B3
   (`position_snapshot`) servem só de gabarito para conciliação.
3. **Casos especiais são dados, não código.** Aliases de ticker e de instituição,
   classes de ativo, eventos corporativos (`corporate_event`) e ofertas de subscrição
   (`subscription_offer`) ficam em tabelas curadas. Premissas (ex.: custo de
   bonificação assumido zero) são marcadas em `flags` no lançamento ou
   `is_assumption` no evento, para o app sinalizar.
4. **Cada título de renda fixa é um ativo próprio**, com detalhe em
   `fixed_income_security` (indexador, taxa, vencimento, regime de IR).
5. **Estados derivados não são gravados.** O status de um direito de subscrição
   (recebido, cedido, exercido, expirado) sai dos lançamentos, como a posição.
6. **Mesmo título em duas fontes:** as duas entradas ficam gravadas; a segunda aponta
   para a primeira em `duplicate_of_id` e o motor a ignora.
7. **Sem tabela de usuário** enquanto o app for de um investidor só. *(Substituída pelo ADR 0002.)*
8. **Tipos:** valores monetários em `numeric(18,2)`; quantidade e preço unitário em
   `numeric(28,10)`; enums como texto com `CHECK`; chaves `bigint`.

## Consequências

- Corrigir um bug de parser é reprocessar, não reimportar.
- Toda tela que mostra posição depende do motor de cálculo; ele precisa ser rápido e
  bem testado (fixtures em `sample_data/`).
- Casos novos (troca de ticker, cisão) exigem cadastrar uma linha, não mudar código.
- Mais tabelas e joins do que um CSV único, em troca de rastreabilidade: todo número
  na tela pode ser explicado até a linha do arquivo de origem.
- Proventos anunciados (`dividend_announcement`), gastos e benchmarks ficam para as
  versões em que forem usados, em migrations próprias.
