# ByteBistro

Sistema de cardápio digital e gerenciamento de pedidos para restaurantes, desenvolvido como projeto acadêmico da disciplina de **Sistemas Distribuídos**.

## Sobre o projeto

O ByteBistro é um sistema que centraliza o fluxo de atendimento de um restaurante, permitindo organizar o cardápio, os produtos disponíveis, o carrinho de compras do cliente e o registro dos pedidos em um único fluxo integrado.

## Problema

Restaurantes frequentemente lidam com processos manuais ou pouco integrados para apresentar o cardápio, registrar pedidos e organizar o atendimento. Isso pode gerar retrabalho, falhas de comunicação e dificuldade de organização das informações do estabelecimento. Mais detalhes em [`docs/negocio/problema.md`](docs/negocio/problema.md).

## Escolha do domínio

O domínio de restaurantes foi escolhido por representar um cenário prático e didático, com um fluxo de dados claro (cardápio → produto → carrinho → pedido), adequado para explorar conceitos de sistemas distribuídos. Mais detalhes em [`docs/negocio/escolha-do-dominio.md`](docs/negocio/escolha-do-dominio.md).

## Solução

O ByteBistro propõe um sistema onde o cliente visualiza o menu de um restaurante, seleciona produtos, monta um carrinho e finaliza um pedido, com o backend responsável por processar as regras de negócio e persistir as informações.

## Proposta de valor

Centralizar em um só sistema o fluxo de cardápio e pedidos, simplificando a organização do restaurante e a experiência do cliente. Mais detalhes em [`docs/negocio/proposta-de-valor.md`](docs/negocio/proposta-de-valor.md).

## Fluxo principal

```
Restaurante
   │
   ▼
  Menu
   │
   ▼
Produtos
   │
   ▼
Carrinho
   │
   ▼
 Pedido
```

## Arquitetura atual

```
Python/Tkinter
      │
      ▼
 HTTP / GraphQL
      │
      ▼
Node.js + TypeScript
      │
      ▼
  Apollo Server
      │
      ▼
    Prisma
      │
      ▼
    SQLite
```

A documentação completa está em [`docs/arquitetura/arquitetura-atual.md`](docs/arquitetura/arquitetura-atual.md).

## Tecnologias

| Área | Tecnologia |
|---|---|
| Cliente | Python + Tkinter |
| Comunicação | HTTP + GraphQL |
| Backend | Node.js + TypeScript |
| API | Apollo Server |
| ORM | Prisma |
| Banco de dados | SQLite |
| Cloud | AWS EC2 |
| Versionamento | Git + GitHub |

## Arquitetura

A arquitetura atual do sistema é um **monólito modular**. A documentação detalhada, incluindo propostas de evolução arquitetural, está disponível em:

- [`docs/arquitetura/arquitetura-atual.md`](docs/arquitetura/arquitetura-atual.md)
- [`docs/arquitetura/arquitetura-futura.md`](docs/arquitetura/arquitetura-futura.md)

## Segurança

A segurança do sistema é um conceito em planejamento e discussão para a disciplina, envolvendo:

- Autenticação
- Autorização
- Secrets
- Tokens
- Firewall
- Security Group
- Segmentação de rede
- Princípio de nunca confiar no cliente

> Esses itens representam conceitos planejados e discutidos academicamente. Nem todos estão implementados na versão atual do sistema.

## Escalabilidade

Os seguintes conceitos fazem parte da evolução arquitetural planejada para o projeto, e não da implementação atual:

- Escalabilidade vertical
- Escalabilidade horizontal
- Load Balancer
- Auto Scaling
- PostgreSQL (banco compartilhado)

## Resiliência

Da mesma forma, os conceitos abaixo são tratados como evolução futura do sistema:

- Retry
- Circuit Breaker
- Filas
- DLQ (Dead Letter Queue)
- Backup
- Disaster Recovery

## DNS

Conceitos relacionados a nomes e roteamento na internet, discutidos como parte da evolução de infraestrutura do projeto:

- Domínio
- Subdomínio
- Registros DNS
- Resolução de nomes
- Roteamento

## Status do projeto

🟡 **Em desenvolvimento**

O projeto encontra-se atualmente em fase de definição, organização da estrutura do repositório e desenvolvimento inicial.

## Organização do GitHub

O repositório utiliza, neste momento, a branch:

- `main` — branch principal do projeto

Conforme o desenvolvimento avançar, será adotado o seguinte modelo:

- `develop` — branch de integração do desenvolvimento
- Branches de funcionalidade, criadas conforme a necessidade:
  - `feature/client`
  - `feature/backend`
  - `feature/database`
  - `feature/infrastructure`
  - `feature/documentation`

Essas branches de funcionalidade serão utilizadas progressivamente, à medida que cada frente do projeto for implementada.

## Estrutura do repositório

```
ByteBistro/
├── README.md
├── .gitignore
├── LICENSE
├── docs/
│   ├── arquitetura/
│   ├── negocio/
│   ├── requisitos/
│   ├── diagramas/
│   └── apresentacao/
├── backend/
├── client/
├── database/
└── infrastructure/
```

## Equipe

- Pedro Antonio
- Tauan Gomes
- Augusto Fagner
