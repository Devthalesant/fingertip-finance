---
paths:
  - "backend/app/tax/**"
  - "backend/app/ir/**"
  - "backend/tests/**/*tax*"
---

# IR (fontes: IN RFB 1.585/2015 e P&R IRPF 2026)

## Ações (mercado à vista, operações comuns)
- 15% sobre o ganho líquido do mês (DARF). Resultado realizado do motor é bruto.
- Isenção: vendas de ações no mês até R$ 20 mil → lucro isento (art. 59). Não vale para
  day trade, ETF de ações, FII nem exercício de opções. Leilão de fração conta como
  venda.
- **Prejuízo de mês isento é compensável** (art. 59, § 1º).
- Perdas compensam ganhos do mesmo mês ou seguintes, sem prazo, inclusive anos
  seguintes (art. 64; P&R 709, 711). Nunca meses anteriores (P&R 710).
- Day trade só com day trade; operação comum só com operação comum.
- Lucro de mês isento **não consome** o prejuízo acumulado (vai para Rendimentos
  Isentos). Interpretação aceita, não texto literal: validar com contador.
- Gabarito sintético: prejuízo de CVCB3 (mar/2022, −1.500) abate o lucro de PETR4
  (mai/2023, +3.000) → base 1.500 → DARF de R$ 225.

## Outras categorias (detalhar na v0.7)
- FIIs: categoria própria, sem isenção. Rendimentos de FII isentos para PF.
- JCP: 15% retido na fonte. Dividendos isentos.
- Renda fixa: LCA/LCI isentas; CDB na tabela regressiva.
- Exterior: Lei 14.754/2023, 15% sobre o resultado anual líquido; consolidação em BRL
  pela PTAX da data.
