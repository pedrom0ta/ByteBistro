# Roteiro de apresentação do ByteBistro

Apresentação da disciplina de Sistemas Distribuídos. Para demonstrar a revisão do repositório, execute o Django localmente e crie a conta do painel antes da apresentação. [Guia local](../../apps/web/README.md)

## 1. Problema e solução — 1 minuto

Apresente o problema de receber e acompanhar pedidos em restaurantes. Mostre como o ByteBistro conecta o cardápio digital ao painel da equipe.

## 2. Demonstração — 4 minutos

1. Abra o cardápio e selecione uma categoria e um produto.
2. Adicione o produto ao carrinho e confirme um pedido na mesa.
3. Abra o painel em outra janela com a conta criada para a demonstração. Em **Pedidos**, aceite o pedido. Em **Cozinha**, marque-o como pronto.
4. Volte à tela de acompanhamento do cliente e confira o status. Conclua o pedido no painel e mostre o histórico de transições.

[Como executar a demonstração](../../apps/web/README.md)

## 3. System Design e arquitetura AWS — 3 minutos

Mostre o que o Django executa no MVP e o ponto em que a integração usa Apollo/GraphQL para consultar o status no PostgreSQL. Use o diagrama para explicar a outbox, o worker, o SQS e o SNS. Apresente a EC2 de demonstração e o estado do rollout distribuído com CloudFront separadamente. [Estado da implantação](../deployment/status.md)

[System Design](../architecture/system-design.md) · [Diagrama AWS](../architecture/aws-architecture.md) · [Terraform](../../infrastructure/terraform/README.md)

## 4. Validação e encerramento — 2 minutos

Apresente as verificações de reenvio de checkout, permissões do painel, acompanhamento privado e concorrência. Mostre os resultados da integração local com Apollo e PostgreSQL. [Verificações do projeto](../deployment/ci-cd.md) · [Estado da implantação](../deployment/status.md)
