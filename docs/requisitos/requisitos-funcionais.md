# Requisitos Funcionais

Este documento lista os requisitos funcionais planejados para o ByteBistro, com base no fluxo principal do sistema: **Restaurante → Menu → Produtos → Carrinho → Pedido**.

Requisitos ainda não detalhados estão marcados como **"a definir"**, conforme o andamento do planejamento do projeto.

## RF01 — Gestão de Restaurante
O sistema deve permitir o cadastro e a manutenção das informações básicas de um restaurante.
*Detalhamento dos campos: a definir.*

## RF02 — Gestão de Menu
O sistema deve permitir associar um menu a um restaurante.
*Detalhamento das regras de organização do menu: a definir.*

## RF03 — Gestão de Produtos
O sistema deve permitir o cadastro de produtos vinculados a um menu.
*Detalhamento de atributos do produto (preço, descrição, categoria etc.): a definir.*

## RF04 — Carrinho de Compras
O sistema deve permitir que o cliente selecione produtos e os adicione a um carrinho antes de finalizar um pedido.

## RF05 — Registro de Pedido
O sistema deve permitir a finalização de um pedido a partir dos itens presentes no carrinho.

## RF06 — Comunicação Cliente-Backend
O sistema deve permitir a comunicação entre o cliente (Python/Tkinter) e o backend através de requisições HTTP utilizando GraphQL.

## RF07 — Persistência de Dados
O sistema deve persistir as informações de restaurante, menu, produtos e pedidos utilizando o banco de dados definido (SQLite, via Prisma).

## Observações

- Requisitos relacionados a autenticação, autorização e controle de acesso de usuários estão **a definir**, e serão detalhados conforme o projeto avançar.
- Este documento poderá ser atualizado conforme o desenvolvimento evolui.
