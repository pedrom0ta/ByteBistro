# Estratégia Docker

Para a demonstração com Django e SQLite, siga o [guia local](../../apps/web/README.md). As imagens para AWS usam os contextos de build abaixo. Execute na raiz do repositório.

```sh
docker build -t bytebistro-web:local ./apps/web
docker build --target api -t bytebistro-api:local ./apps/services
docker build --target worker -t bytebistro-worker:local ./apps/services
```

O [guia de implantação na AWS](../../infrastructure/terraform/README.md) descreve as dependências e a configuração para executar as imagens.

## Processos do ambiente distribuído

| Imagem | O que executa |
| --- | --- |
| Web | Django com Gunicorn (porta `8000`) e PostgreSQL. Comunica-se com a API pelo ALB interno (`BYTEBISTRO_GRAPHQL_URL`), envia SMS via AWS SNS (`SnsSmsProvider`, `boto3` em `requirements-aws.txt`) e grava a outbox. |
| API | Node.js com Apollo Server e Prisma (porta `4000`). Executa em Auto Scaling Group próprio (`api`), expõe `GET /healthz` sem autenticação e `POST /graphql` atrás do ALB interno. |
| Worker | Publicador da outbox e consumidor SQS em Auto Scaling Group próprio (`worker`). Lê `shop_order`, atualiza `shop_orderoutbox`, publica no SNS e registra `"notified"` em `shop_orderevent`. |

As imagens executam com usuário sem privilégios. Cada frota (`web`, `api`, `worker`) roda em seu próprio Auto Scaling Group de EC2, puxando apenas o respectivo digest de `var.runtime` (`web_digest`, `api_digest`, `worker_digest`) e o respectivo segredo de `aws_secretsmanager_secret.runtime[service]`. O bootstrap carrega os segredos em execução, configura os logs e inicia os contêineres por digest. As migrações usam um executor separado. [Contrato das imagens](../../infrastructure/terraform/README.md#contrato-das-imagens)

[Build e imagens Docker](https://docs.docker.com/build/building/best-practices/)
