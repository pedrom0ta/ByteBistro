# Arquitetura Atual

Este documento descreve a arquitetura **atualmente definida** para o ByteBistro. Ele reflete o estado real de planejamento do projeto, sem incluir componentes que ainda não fazem parte do sistema.

## Visão geral

```
Python/Tkinter (Cliente)
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
     Resolvers
        │
        ▼
      Prisma
        │
        ▼
      PostgreSQL
```

## Componentes e responsabilidades

### Cliente (Python/Tkinter)
Responsável pela interface gráfica utilizada pelo usuário para interagir com o sistema: visualizar o cardápio, selecionar produtos, montar o carrinho e enviar pedidos. O cliente se comunica com o backend exclusivamente via HTTP/GraphQL.

### Comunicação (HTTP/GraphQL)
Camada de comunicação entre o cliente e o backend. As requisições e respostas trafegam via HTTP, utilizando GraphQL como linguagem de consulta e manipulação de dados.

### Backend (Node.js + TypeScript)
Responsável por receber as requisições do cliente, aplicar as regras de negócio do sistema e coordenar o acesso aos dados.

### Apollo Server
Servidor GraphQL responsável por expor o schema da API, processar as queries e mutations recebidas do cliente e direcioná-las aos resolvers correspondentes.

### Resolvers
Funções responsáveis por implementar a lógica de cada operação GraphQL (queries e mutations), conectando as requisições da API às regras de negócio e ao acesso a dados.

### Prisma
ORM utilizado para abstrair o acesso ao banco de dados, permitindo que o backend manipule os dados de forma segura e tipada.

### PostgreSQL
Banco de dados utilizado atualmente para persistência das informações do sistema.

## Princípio arquitetural importante

> **O cliente não acessa diretamente o banco de dados.**
> Todo acesso a dados passa obrigatoriamente pelo backend, que é o único responsável por aplicar as regras de negócio e realizar a comunicação com o banco de dados através do Prisma.

## Estilo arquitetural

A arquitetura atual do ByteBistro é classificada como um **monólito modular**: todo o backend é executado como uma única aplicação, porém organizado internamente em módulos com responsabilidades bem definidas (API, regras de negócio, acesso a dados). Essa abordagem é adequada à fase atual do projeto, sendo mais simples de desenvolver, testar e implantar.

## Infraestrutura atual

A aplicação é hospedada em uma instância **AWS EC2**. Mais detalhes em [`infrastructure/README.md`](../../infrastructure/README.md).

---

Para os conceitos de evolução arquitetural planejados para etapas futuras do projeto, consulte [`arquitetura-futura.md`](arquitetura-futura.md).
