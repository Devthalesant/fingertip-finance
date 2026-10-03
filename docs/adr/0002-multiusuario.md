# ADR 0002: Multiusuário desde a v0.1

- **Status:** aceito
- **Data:** 2026-10-02

## Contexto

O app nasceu para um investidor só (ADR 0001, decisão 7: "sem tabela de usuário"). O
plano mudou: a parte de investimentos vira produto, com mensalidade, aberto a outros
investidores. Gastos e Open Finance (Pluggy, cujo plano grátis é só para uso pessoal)
continuam como módulo pessoal do dono, por enquanto.

O schema inicial já está aplicado no demo, mas sem dados e sem código que dependa dele.
Adicionar o dono de cada linha agora custa uma migration; depois de parser, API e telas
prontos, custaria reescrever consultas e testes.

## Decisão

1. **Tabela `app_user`.** `id`, `email` (único), `display_name`, `auth_provider` +
   `auth_subject` (únicos juntos: a identidade no Google/GitHub), `is_admin`,
   `created_at`. Sem plano nem pagamento por enquanto: isso entra quando houver
   validação (ver Consequências).
2. **Dois tipos de tabela.**
   - **Catálogo compartilhado** (fato de mercado, igual para todo mundo, curado pelo
     admin): `institution`, `institution_alias`, `asset`, `asset_alias`,
     `fixed_income_security`, `corporate_event`, `subscription_offer`, `price`,
     `fx_rate`. Um desdobro cadastrado uma vez vale para todos os usuários.
   - **Dados do usuário** (ganham `user_id NOT NULL`, com índice): `account`,
     `import_file`, `raw_row`, `ledger_entry`, `position_snapshot`.
3. **`user_id` repetido em toda tabela do usuário**, mesmo quando daria para descobrir
   por join (ex.: `raw_row` → `import_file`). Toda consulta filtra por uma coluna só, e
   a regra fica fácil de conferir e de reforçar no banco (item 6).
4. **Unicidades passam a ser por usuário.**
   - `import_file`: `(user_id, file_sha256)`.
   - `raw_row`: `(user_id, source, row_hash)`. Sem isso, duas pessoas com uma linha
     idêntica no extrato (mesmo dia, ativo e valor) colidiriam, e a segunda perderia o
     lançamento.
   - `account`: `(user_id, institution_id, kind, label)`.
5. **Ativo privado.** `asset` ganha `owner_user_id` opcional: vazio = catálogo
   (ações, FIIs, Tesouro, títulos com código B3); preenchido = ativo só daquele usuário
   (CDB de banco que não aparece na B3, ativo lançado à mão). Unicidade de
   `canonical_code` passa a ser `(owner_user_id, canonical_code)`, com nulos iguais
   entre si. Aliases só para ativos do catálogo.
6. **Isolamento em duas camadas.**
   - **Aplicação:** a API resolve o usuário a partir do token, e toda consulta a
     dados do usuário passa por uma função que já aplica o filtro por `user_id`.
     Testes garantem que um usuário não enxerga dados de outro.
   - **Banco (v1.0):** Row-Level Security do Postgres nas tabelas do usuário, como rede
     de segurança caso uma consulta esqueça o filtro.
7. **Ativo novo vindo de importação** continua entrando como `A_CLASSIFICAR`, mas a
   classificação de um ativo do catálogo é feita pelo admin (vale para todos). Para
   isso ser raro, o catálogo é pré-carregado com a lista pública de instrumentos da B3
   e da CVM.
8. **Módulos pessoais por permissão.** Gastos e Pluggy ficam liberados só para
   `is_admin` (ou uma lista de recursos por usuário, quando houver mais de um caso).
   As tabelas desses módulos já nascem com `user_id`.
9. **Login em beta fechado.** Cadastro aceito só para e-mails convidados (lista no
   backend). Substitui a regra "login aceita só a conta do dono".
10. **Migration nova, não edição da inicial.** A `d1a99da658fc` já foi aplicada; uma
    segunda migration cria `app_user` e adiciona as colunas. Como as tabelas estão
    vazias, as colunas entram direto como `NOT NULL`.

## Consequências

- Todo endpoint e todo job passam a receber o usuário; testes ganham uma fixture com
  dois usuários para provar o isolamento.
- O catálogo compartilhado vira uma vantagem do produto (curadoria de eventos
  corporativos uma vez só), mas exige uma tela ou script de admin para manter.
- Antes de abrir para terceiros: termos de uso, política de privacidade (LGPD),
  exclusão de conta com apagamento dos dados, e aviso de que insights são descritivos
  (não recomendação de investimento) e de que a apuração de IR não substitui um
  contador.
- Antes de cobrar: conferir as licenças das fontes de cotação para uso comercial
  (brapi e afins) e escolher o meio de pagamento.
- Este ADR substitui a decisão 7 do ADR 0001.
