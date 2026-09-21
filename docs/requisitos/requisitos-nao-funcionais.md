# Requisitos Não Funcionais

Este documento lista os requisitos não funcionais planejados para o ByteBistro. Itens ainda não definidos com precisão estão marcados como **"a definir"**.

## RNF01 — Comunicação
A comunicação entre cliente e backend deve ocorrer via HTTP, utilizando GraphQL como linguagem de consulta.

## RNF02 — Tecnologia do Backend
O backend deve ser desenvolvido em Node.js com TypeScript, utilizando Apollo Server para expor a API GraphQL.

## RNF03 — Tecnologia do Cliente
O cliente deve ser desenvolvido em Python, utilizando Tkinter para a interface gráfica.

## RNF04 — Persistência
O sistema deve utilizar SQLite como banco de dados na versão atual, com acesso via Prisma ORM.

## RNF05 — Hospedagem
O sistema deve estar preparado para ser hospedado em uma instância AWS EC2.

## RNF06 — Organização do Código
O código deve ser organizado de forma modular, separando claramente as responsabilidades de cliente, backend, banco de dados e infraestrutura.

## RNF07 — Versionamento
O projeto deve utilizar Git e GitHub para controle de versão, seguindo a organização de branches definida no README principal.

## RNF08 — Segurança (conceitual)
Conceitos de segurança (autenticação, autorização, secrets, tokens, firewall, Security Group, segmentação de rede) devem ser considerados na evolução do sistema.
*Nível de implementação: a definir.*

## RNF09 — Escalabilidade (conceitual)
O sistema deve ser discutido academicamente quanto à sua capacidade de evoluir para suportar escalabilidade vertical e horizontal.
*Implementação: a definir, tratada como evolução futura.*

## RNF10 — Resiliência (conceitual)
Conceitos de resiliência (retry, circuit breaker, filas, DLQ, backup, disaster recovery) devem ser discutidos como parte da evolução arquitetural do sistema.
*Implementação: a definir, tratada como evolução futura.*

## Observações

- Requisitos de desempenho (tempo de resposta, throughput) ainda não foram definidos: **a definir**.
- Este documento reflete o estágio atual de planejamento do projeto e poderá ser atualizado conforme o desenvolvimento avança.
