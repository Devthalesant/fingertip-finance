---
paths:
  - "frontend/**"
---

# Frontend e design

## Stack (`frontend/`, Node LTS, npm; versões estáveis atuais no scaffold)
- Next.js (App Router) + TypeScript `strict`. PWA instalável. Mobile-first.
- Tailwind CSS + shadcn/ui. Gráficos: shadcn/ui Charts (Recharts); Lightweight Charts
  para a série de preço do ativo.
- TanStack Query (cache e atualização reativa).
- `openapi-typescript` + `openapi-fetch`: cliente tipado gerado do OpenAPI do FastAPI.
  Mudou a API, regenera os tipos.
- ESLint + Prettier; Vitest + Testing Library; Playwright depois.

## Regras
- Nenhum cálculo financeiro: PM, resultado, rentabilidade e insights vêm prontos da API.
  Valores monetários chegam como string decimal; formatar com
  `Intl.NumberFormat("pt-BR")`.
- `NEXT_PUBLIC_*` vai para o navegador: nunca segredo. A única prevista é a URL da API.
- Nunca falar direto com o banco nem com APIs que exigem credencial.
- Modo "ocultar valores" (privacidade e prints para o LinkedIn).
- Insights são dados tipados do backend (tipo, severidade, título, ativo, explicação,
  data); o frontend só renderiza o feed.

## Design (definir antes do scaffold)
- Em andamento: decisões dos rounds em `docs/roadmap.md` ("Retomar aqui"). Direção
  aprovada (ainda não congelada): IBM Plex Sans (+ Condensed nas tabelas), alta/baixa em
  azul/laranja + ▲▼. Congelar os tokens num ADR antes do scaffold.
- Identidade com tokens de cor, dark mode desde o início, números tabulares.
- Telas: Visão geral, Carteira, Ativo, Proventos, Renda fixa, Exterior, IR, Gastos,
  Conciliação.
- Alta/baixa com cor **e** ícone; valores alinhados à direita; estados de carregamento
  e vazio pensados.
