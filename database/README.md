# Database

## Banco de dados atual

- **PostgreSQL**

## ORM

- **Prisma**

## Responsabilidade

Armazenamento dos dados do sistema (restaurantes, menus, produtos e pedidos), com acesso mediado exclusivamente pelo backend através do Prisma.

## Limitação arquitetural

O PostgreSQL entra como uma solução para a escalabilidade horizontal. Se tivermos várias instâncias do backend, todas elas podem acessar o mesmo banco de dados PostgreSQL. Assim, independentemente de qual servidor receber a requisição, ele trabalha com a mesma fonte de dados

## Evolução possível

Como proposta de evolução arquitetural, discute-se a substituição do SQLite por um banco de dados compartilhado, como o **PostgreSQL**, permitindo que múltiplas instâncias do backend acessem uma única fonte de dados consistente.

> Esta migração é uma **proposta futura** e não representa uma funcionalidade implementada na versão atual do projeto. Mais detalhes em [`docs/arquitetura/arquitetura-futura.md`](../docs/arquitetura/arquitetura-futura.md).

## Status

🟡 Em fase de planejamento.
