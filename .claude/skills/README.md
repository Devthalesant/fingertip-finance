# Skills do projeto

Copiadas e auditadas (lidas por inteiro) antes de entrar. Versão fixa: atualizar só
copiando de novo e relendo. Nenhuma tem scripts ou hooks.

| Skill | Origem | Versão | Licença |
|---|---|---|---|
| `fastapi` | FastAPI (oficial, embutida no pacote) | fastapi 0.141.1 | MIT |
| `frontend-design` | Anthropic, github.com/anthropics/skills | `8a1541c` | Apache-2.0 |
| `property-based-testing` | Trail of Bits, github.com/trailofbits/skills | `82fe822` | CC-BY-SA-4.0 |
| `test-driven-development` | obra/superpowers (Jesse Vincent) | `8ca22db` | MIT |
| `verification-before-completion` | obra/superpowers (Jesse Vincent) | `8ca22db` | MIT |
| `gabarito` | este projeto | — | — |

Arquivos não copiados: README, evals, logo e config de outras ferramentas.

## Exceções às skills externas (decisões do projeto prevalecem)
- `fastapi`: usamos **SQLAlchemy** (ADR 0001), não SQLModel; dinheiro é **Decimal**,
  nunca `float` (os exemplos da skill usam float).
- `test-driven-development`: vale para parser, motor de cálculo e regras de IR.
  Exploração e protótipos combinados com o dono ficam fora da regra "apague o código".
