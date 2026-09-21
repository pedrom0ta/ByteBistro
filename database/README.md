# Database

## Banco de dados atual

- **PostgreSQL**

## ORM

- **Prisma**

## Responsabilidade

Armazenamento dos dados do sistema (restaurantes, menus, produtos e pedidos), com acesso mediado exclusivamente pelo backend através do Prisma.

## Limitação arquitetural

O SQLite é um banco de dados local, baseado em arquivo. Isso significa que, caso múltiplas instâncias do backend sejam executadas futuramente, cada uma com seu próprio arquivo de banco, poderá haver inconsistência entre os dados armazenados em cada instância.

## Evolução possível

Como proposta de evolução arquitetural, discute-se a substituição do SQLite por um banco de dados compartilhado, como o **PostgreSQL**, permitindo que múltiplas instâncias do backend acessem uma única fonte de dados consistente.

> Esta migração é uma **proposta futura** e não representa uma funcionalidade implementada na versão atual do projeto. Mais detalhes em [`docs/arquitetura/arquitetura-futura.md`](../docs/arquitetura/arquitetura-futura.md).

## Status

🟡 Em fase de planejamento.
