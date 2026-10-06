# ADR 0004: API da v0.1, autenticação e upload seguro

- **Status:** aceito
- **Data:** 2026-10-06

## Contexto

A API é a primeira porta do app aberta para a internet. Ela precisa saber quem chama
(ADR 0002: toda consulta filtra por `user_id`) e vai receber arquivos enviados pelo
usuário (o extrato da B3), que podem ser malformados ou maliciosos. O login acontece no
frontend (Auth.js com Google/GitHub), que ainda não existe; o token de sessão do
Auth.js é um JWE criptografado, pensado para ser lido só pelo Next.js.

## Decisão

1. **Endpoints da v0.1.** `GET /health` (único sem login), `GET /me`, `GET /portfolio`
   (posições com custo, PM e custódia por corretora, mais os avisos do motor),
   `POST /imports/b3-movements` (upload do xlsx) e `GET /imports` (histórico). Valor de
   mercado fica para a v0.2; vendas e proventos ganham endpoints quando houver tela.
   Dinheiro e quantidade como string decimal.
2. **Crachá assinado entre Next.js e FastAPI.** Depois do login, o servidor do Next.js
   emite um JWT HS256 de vida curta (≤ 5 min) com `iss = fingertip-web`,
   `aud = fingertip-api`, `email`, `provider` e `sub` (id da pessoa no provedor),
   assinado com `API_JWT_SECRET` (só no backend e no servidor do Next, nunca no
   navegador). O FastAPI confere assinatura, algoritmo, validade, emissor e
   destinatário; acha o `app_user` pelo e-mail convidado, grava provedor e `sub` no
   primeiro acesso e exige que batam nos seguintes. Falha → 401 genérico; e-mail não
   convidado → 403 genérico (sem dizer o motivo).
3. **Isolamento testado.** Todo endpoint tem teste com dois usuários provando que um
   não vê o outro. RLS no banco (ADR 0002) entra quando houver o primeiro usuário além
   do dono, não só na v1.0.
4. **Upload em camadas.**
   1. Antes de abrir: tamanho contado na entrada (5 MB, corta ao passar); assinatura
      de zip (`PK`); índice do zip inspecionado sem descompactar (teto de 50 MB
      descompactado, taxa de compressão máxima, só as peças esperadas de um xlsx; recusa
      macro, link externo, objeto embutido, `..` no caminho e zip dentro de zip).
   2. Ao abrir: `defusedxml` (bombas de entidade, XML externo); fórmulas nunca
      calculadas (openpyxl lê o valor salvo); teto de colunas, linhas e tamanho de
      célula.
   3. Quarentena: leitura num processo separado com prazo; teto de memória no Linux
      (servidor e CI).
   4. Conteúdo é dado: todo export para planilha neutraliza texto iniciado por `=`,
      `+`, `-` ou `@`; o frontend nunca renderiza HTML vindo de dados.
   5. Arquivo lido em memória e descartado; log com motivo e tamanho, nunca conteúdo.
   Cada camada tem teste com um arquivo malicioso sintético gerado no próprio teste.
   Antivírus fica de fora: ninguém abre o arquivo num computador.
5. **Demais proteções.** Erro genérico para fora (detalhe só no log, sem valores);
   CORS liberado só para o domínio do frontend; limite de requisições por usuário,
   mais apertado no upload (em memória no beta, com uma instância só).
6. **Dependências novas:** `pyjwt`, `python-multipart`, `defusedxml`.
7. **Escala: medir antes de otimizar.** Teste de tempo de cada endpoint com volume
   grande de dados sintéticos (10 anos de operações).

## Consequências

- O frontend só precisa emitir o crachá; a API já nasce autenticada e testável com
  crachás fabricados nos testes.
- `API_JWT_SECRET` é mais um segredo a guardar nos dois lados e a trocar se vazar.
- Limites conhecidos, a revisitar quando o teste de volume apontar:
  - a carteira é recalculada do zero a cada acesso (solução: guardar o resultado e
    recalcular só quando entra lançamento);
  - cada importação refaz todos os lançamentos da pessoa (escolha por correção);
  - o gravador percorre todas as instituições ao achar uma grafia nova (trocar por
    busca no banco antes de abrir para terceiros);
  - o upload é processado durante a requisição (se demorar, vira fila);
  - o limite de requisições em memória não vale com várias instâncias (mover para o
    banco).
