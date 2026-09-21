# Client

## Responsabilidade

O client do ByteBistro é responsável por:

- Fornecer a interface gráfica utilizada pelo usuário
- Permitir a interação com o sistema (visualização do menu, seleção de produtos, montagem do carrinho e envio de pedidos)
- Realizar a comunicação com a API do backend

## Tecnologia

- **Python**
- **Tkinter** — biblioteca utilizada para a interface gráfica

## Comunicação

O client se comunica exclusivamente com o backend via HTTP/GraphQL, não possuindo acesso direto ao banco de dados. Mais detalhes em [`docs/arquitetura/arquitetura-atual.md`](../docs/arquitetura/arquitetura-atual.md).

## Status

🟡 Em fase de planejamento. Ainda não há implementação de código nesta pasta — a estrutura de pastas e arquivos do client será adicionada conforme o desenvolvimento avançar.
