# API GraphQL e worker

O serviço Node.js e TypeScript implementa a consulta interna de status de pedido com Apollo Server e Prisma. O Django mantém as regras de negócio, as migrações do banco e o controle da identidade da sessão. Na configuração AWS, o navegador consulta o Django, que repassa a consulta ao Apollo com autenticação de serviço.

Na confirmação do pedido, o Django pode gravar uma entrada de outbox na mesma transação. O worker publica no SQS, consome a fila e publica no SNS. Ele usa o ID do evento para detectar reentregas. Uma interrupção após o SNS aceitar a mensagem e antes da confirmação no banco pode repetir a notificação. Assinantes devem deduplicar por ID do evento.

Em `apps/services`, execute `npm ci` e `npm run build` para gerar o Prisma Client e compilar o TypeScript. As imagens usam os alvos Docker `api` e `worker`. [Contrato e publicação na AWS](../../infrastructure/terraform/README.md)

Execute `npm test` nessa pasta para compilar o código e verificar o contrato de acompanhamento e os filtros de acesso. Os testes usam um repositório simulado em memória.
