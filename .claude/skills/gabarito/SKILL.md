---
name: gabarito
description: Método do Fingertip Finance para testar cálculos financeiros com dados sintéticos e gabarito feito à mão. Use sempre que for criar ou alterar cenários em backend/sample_data/ (scenario.py, expected.py, b3_format.py, b3_consolidated.py), escrever testes do parser da B3, do motor de PM, de proventos, de renda fixa ou de IR, conferir se um resultado do motor "bate", ou incluir um ativo, evento corporativo ou formato de arquivo novo nos dados de teste — mesmo que o pedido não diga "gabarito".
---

# Gabarito: prova sintética + respostas calculadas à mão

O projeto testa matemática financeira como um professor corrige prova: inventa a
história de um investidor fictício (a **prova**, em arquivos no formato exato da B3) e
calcula à mão as respostas (o **gabarito**). O motor do app faz a prova e os testes
comparam. Isso só funciona se as duas metades forem independentes.

## Onde fica cada coisa (`backend/sample_data/`)

| Arquivo | Papel |
|---|---|
| `scenario.py` | a história, um grupo de cenários por função (`trades`, `loans`, ...) |
| `expected.py` | o gabarito: posições (custo), vendas, proventos, conciliação |
| `b3_format.py`, `b3_consolidated.py` | o formato dos arquivos da B3, com as esquisitices |
| `generate.py` | grava os xlsx em `sample_data/out/` (ignorado pelo Git) |

## Regras e por quê

1. **O gabarito nunca é gerado por código do app.** Se o motor calculasse o gabarito,
   um erro de PM apareceria nos dois lados e o teste passaria. Escreva os números
   literais, com a conta em comentário (`# 50 × 39 = 1.950 − 1.550 = lucro de 400`).
   Os testes de `expected.py` só conferem a aritmética interna (resultado = valor −
   custo), nunca recalculam o PM.
2. **Números redondos.** O dono confere tudo de cabeça ou na calculadora; preços como
   R$ 35,00 e quantidades como 100 tornam a revisão rápida. Use centavos quebrados só
   onde o formato exige (ex.: preços de fechamento do consolidado).
3. **Tickers e eventos reais; operações inventadas.** Eventos corporativos (desdobro,
   grupamento, bonificação, troca de ticker, subscrição) usam proporção, datas, custo
   atribuído e preço de subscrição de fonte oficial (aviso aos acionistas, fato
   relevante, CVM, B3), citados no comentário. Quantidades, preços e proventos são
   inventados e plausíveis. Nunca usar a carteira real do dono.
4. **Ao incluir ou manter um ativo, confira os eventos reais do período.** Se o
   investidor fictício tem o ativo durante um evento real, o extrato precisa mostrá-lo
   — senão o demo contradiz o catálogo real. Ajustar a data da compra é uma saída
   legítima (ex.: WEGE3 comprada depois do desdobro de 27/04/2021).
5. **Formato fiel, sem expor dados reais.** Para descobrir como a B3 grava algo, nunca
   abra valores de `data/`. Use máscara (letra → `A`, dígito → `9`, sequências longas
   → `A*`) e contagens agregadas (ex.: "quantas linhas de JCP têm valor = q × p × 0,85").
   Só com pedido explícito do dono para ler `data/`. Registre o que descobrir em
   `.claude/rules/dados-b3.md`.
6. **Determinismo.** Mesma história → mesmos bytes (sem data de geração no arquivo),
   porque o `import_file` reconhece arquivo repetido pelo SHA-256.
7. **O dono valida o gabarito antes de ele valer.** Ao criar ou mudar cenários,
   apresente o gabarito na conversa como tabela (data, operação, conta, resultado,
   posição/custo depois) e espere o ok. Diga também o que o cenário testa (a
   pegadinha). Mensagens intermediárias podem não chegar ao dono: repita as tabelas na
   resposta final.

## Fluxo para um cenário novo

1. Escolha a pegadinha que o cenário prova (ex.: "aluguel não mexe no PM").
2. Se envolver evento real, pesquise a fonte oficial e anote no comentário.
3. Se envolver formato novo, confira o formato real com máscara.
4. Escreva a função do grupo em `scenario.py` (uma operação da história pode virar
   várias linhas do extrato) e inclua-a em `movement_rows()`.
5. Escreva o gabarito em `expected.py` com a conta em comentário.
6. Acrescente um teste que prove que o cenário está no extrato (sem recalcular).
7. Rode `uv run pytest` e `uv run ruff check .` (em `backend/`), mostre as tabelas ao
   dono e só então commite.

## Gabarito + propriedades (Hypothesis)

O gabarito prova **exemplos** conhecidos; testes de propriedade provam **regras que
valem sempre**, com milhares de casos gerados. Use os dois no motor (skill
`property-based-testing` para o como). Invariantes do domínio:

| Propriedade | Regra |
|---|---|
| Desdobro / grupamento | custo total não muda; quantidade × fator |
| Venda | PM não muda; custo cai proporcionalmente |
| Aluguel (sai e volta) | posição e PM iguais aos de antes |
| Transferência entre corretoras | custo e PM iguais; só a custódia muda |
| Custódia × custo | soma das posições por corretora = posição total |
| Reimportação | importar o mesmo arquivo de novo não muda nada |
| Recibo de subscrição | cota nova entra uma vez (recibo + atualização ≠ dobro) |

`Decimal` sempre (nunca `float`), inclusive nas estratégias do Hypothesis. Adicionar o
`hypothesis` como dependência de desenvolvimento exige ok do dono.
