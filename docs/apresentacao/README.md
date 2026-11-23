# Roteiro de apresentação do ByteBistro

**Status** ✅ Roteiro completo

## 1. Problema e proposta — 1 minuto

Apresente o problema de receber e acompanhar pedidos em restaurantes. Mostre como o ByteBistro conecta o cardápio digital ao painel da equipe.

## 2. Demonstração — 4 minutos

1. Abra o cardápio e selecione uma categoria e um produto.
2. Adicione o produto ao carrinho e confirme um pedido na mesa.
3. Abra o painel em outra janela com um usuário de demonstração. Aceite o pedido e marque-o como pronto.
4. Volte à tela do cliente e mostre a atualização do status. Explique que o fluxo atual roda em Django e SQLite.

[Como executar a demonstração](../../client/README.md)

## 3. System Design e arquitetura AWS — 3 minutos

Mostre como a aplicação atual grava pedidos e controla suas transições. Depois, apresente a arquitetura proposta com Django, Apollo/GraphQL e PostgreSQL. Use o diagrama AWS para explicar a entrada HTTPS, a distribuição em duas zonas, o banco Multi-AZ e o fluxo assíncrono com SQS, workers e SNS. Apresente o Terraform como infraestrutura preparada para provisionamento.

[System Design](../architecture/system-design.md) · [Diagrama AWS](../architecture/aws-architecture.md) · [Terraform](../../infrastructure/terraform/README.md)

## 4. Validação e encerramento — 2 minutos

Apresente a cobertura da suíte Django, incluindo reenvio de checkout, permissões do painel e concorrência no aceite. Encerre com os próximos passos de integração e implantação e reserve tempo para perguntas.