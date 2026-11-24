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
| Web | Django com Gunicorn e PostgreSQL. |
| API | Apollo com Prisma. O contêiner fica na rede privada do host web. |
| Worker | Publicador da outbox e consumidor SQS no mesmo processo. Usa PostgreSQL, SQS e SNS. |

As imagens executam com usuário sem privilégios. O bootstrap carrega os segredos em execução, configura os logs e inicia os contêineres por digest. As migrações usam um executor separado. [Contrato das imagens](../../infrastructure/terraform/README.md#contrato-das-imagens)

[Build e imagens Docker](https://docs.docker.com/build/building/best-practices/) · [Estado da implantação](status.md)
