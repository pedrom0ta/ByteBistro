# ByteBistro

Projeto da disciplina de Sistemas Distribuídos para gestão de cardápios e pedidos em restaurantes.

- **Equipe** Pedro Antonio, Tauan Gomes e Augusto Fagner
- **Professor** Levi Costa

## Diagrama de infraestrutura AWS

O diagrama mostra a configuração distribuída definida em Terraform (três frotas desacopladas em Auto Scaling, ALB interno, borda HTTPS/WAF ativa e mensageria SQS/SNS). A demonstração pública roda em uma EC2 separada. [Detalhes do diagrama](docs/architecture/aws-architecture.md) · [Estado da implantação](docs/deployment/status.md)

```mermaid
flowchart TB
    USER["CLIENTE<br/>Navegador Web"]

    subgraph ENTRY["1. ENTRADA E DISTRIBUIÇÃO (HTTPS + WAF ATIVOS)"]
        R53["Route 53<br/>Domínio obrigatório (var.domain)"]
        CF["CloudFront<br/>Distribuição (https-only)"]
        WAF["AWS WAFv2<br/>Bloqueio ativo + Rate Limit"]
        ACM_EDGE["ACM (us-east-1)<br/>Certificado Edge obrigatório"]
        ACM_ORIGIN["ACM (Região)<br/>Certificado Origin obrigatório"]

        R53 --> CF
        WAF -. "Bloqueio ativo" .-> CF
        ACM_EDGE -. "TLS Edge" .-> CF
    end

    subgraph VPC["2. AWS VPC — DUAS ZONAS DE DISPONIBILIDADE"]
        subgraph PUBLIC["SUB-REDES PÚBLICAS"]
            ALB_PUB["ALB Público<br/>HTTPS :443 (/healthz/)"]
            NAT["NAT Gateways<br/>Saída HTTPS :443"]
        end

        subgraph PRIVATE["SUB-REDES PRIVADAS — 3 ASGs (min 2..6 EC2 cada)"]
            ASG_WEB["ASG web<br/>Django :8000"]
            ALB_INT["ALB Interno (internal = true)<br/>HTTP :4000 (/healthz)"]
            ASG_API["ASG api<br/>Node.js + Apollo :4000"]
            ASG_WORKER["ASG worker<br/>Outbox, SQS e SNS"]

            ASG_WEB -->|"HTTP :4000 /graphql"| ALB_INT
            ALB_INT -->|"HTTP :4000"| ASG_API
        end

        subgraph DATA["SUB-REDES ISOLADAS DE DADOS"]
            RDS[("RDS PostgreSQL 16<br/>Multi-AZ (:5432)")]
        end

        ALB_PUB -->|"HTTP :8000"| ASG_WEB
        ASG_WEB -->|"Pedidos, cache e outbox :5432"| RDS
        ASG_API -->|"Leitura shop_order :5432"| RDS
        ASG_WORKER -->|"Outbox, shop_order e shop_orderevent :5432"| RDS
        NAT -. "Saída HTTPS :443" .-> PRIVATE
    end

    CF -->|"HTTPS :443 + Header secreto"| ALB_PUB
    ACM_ORIGIN -. "TLS :443" .-> ALB_PUB

    subgraph MESSAGING["3. MENSAGERIA E NOTIFICAÇÕES"]
        SQS["SQS<br/>Fila de eventos"]
        DLQ["SQS DLQ<br/>Falhas repetidas"]
        SNS_NOTIF["SNS Notificações (KMS)<br/>Evento order.created"]
        SUB_EMAIL["Assinatura E-mail<br/>notification_email (opcional)"]
        SNS_SMS["AWS SNS SMS<br/>OTP Transacional (+55)"]
        SQS -. "Redrive" .-> DLQ
    end

    ASG_WORKER -->|"Publica"| SQS
    SQS -->|"Consome"| ASG_WORKER
    ASG_WORKER -->|"order.created"| SNS_NOTIF
    SNS_NOTIF -->|"E-mail"| SUB_EMAIL
    ASG_WEB -->|"SMS OTP (sns:Publish)"| SNS_SMS

    subgraph STORAGE["4. ARMAZENAMENTO"]
        S3["Amazon S3<br/>Estáticos (OAC) e auditoria"]
        ECR["Amazon ECR<br/>3 imagens (web, api, worker)"]
    end

    CF -->|"/static/* (OAC)"| S3
    ECR -. "Pull 3 imagens" .-> PRIVATE

    subgraph SECURITY["5. SEGURANÇA, CONFIGURAÇÃO E OPERAÇÃO"]
        IAM["IAM<br/>3 roles isoladas (web, api, worker)"]
        SSM["SSM Parameter Store<br/>AMI AL2023 automática"]
        SM["Secrets Manager<br/>Segredos runtime e RDS"]
        CW["CloudWatch<br/>Logs e alarmes HealthyHostCount (web/api)"]
        CT["CloudTrail<br/>Auditoria multi-região"]
        BACKUP["AWS Backup<br/>Backup diário do RDS"]
    end

    IAM -. "Autoriza acessos" .-> PRIVATE
    SSM -. "Resolve AMI AL2023" .-> PRIVATE
    SM -. "Injeta segredos" .-> PRIVATE
    PRIVATE -. "Logs e métricas" .-> CW
    RDS -. "Métricas" .-> CW
    CT -. "Logs" .-> S3
    CT -. "Métricas" .-> CW
    RDS -. "Backup diário" .-> BACKUP

    USER -->|"DNS obrigatório"| R53
    USER -->|"HTTPS"| CF
```

## Entrega acadêmica

- **Cliente.** Cardápio com busca e categorias, personalização de itens, carrinho, pedidos na mesa ou por delivery e acompanhamento.
- **Equipe do restaurante.** Painel com acesso por perfil, fila de pedidos, cozinha, mesas, catálogo, estoque e registro de recebimentos.
- **Demonstração.** A versão local roda com Django e SQLite e permite testar o delivery com o código de verificação no terminal. A vitrine também pode ser acessada na EC2. [Demonstração pública](https://54.209.48.237/)
- **Integração distribuída.** O projeto desacopla Django (`web`), API Apollo/GraphQL (`api`, via ALB interno na porta `4000`) e `worker` SQS/SNS com Prisma e PostgreSQL, além de envio de SMS transacional via AWS SNS (`SnsSmsProvider`) em produção e borda com Route 53, ACM, CloudFront (`https-only`) e WAF ativo no Terraform. As três imagens do release foram publicadas no ECR. [Estado da implantação](docs/deployment/status.md)

## Executar localmente

A demonstração usa Django e SQLite. Com Python 3.11 ou 3.12, execute na raiz do repositório no PowerShell.

```powershell
cd apps/web
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

Abra a [vitrine](http://127.0.0.1:8000/). Para acessar o [painel](http://127.0.0.1:8000/painel/), crie uma conta com `.\.venv\Scripts\python manage.py createsuperuser` em `apps/web`. Execute `.\.venv\Scripts\python manage.py test` para rodar os testes do Django.

Para uma avaliação rápida, envie um pedido na mesa, aceite-o no painel, marque-o como pronto e confira a atualização na tela do cliente. [Roteiro de avaliação](docs/apresentacao/README.md#2-demonstração--4-minutos)

## Estrutura do repositório

| Pasta | Conteúdo |
| --- | --- |
| [`apps/web/`](apps/web/README.md) | Aplicação Django, templates, arquivos estáticos, testes e migrações. |
| [`apps/services/`](apps/services/README.md) | API GraphQL, worker de pedidos e schema Prisma. |
| [`infrastructure/`](infrastructure/README.md) | Terraform para AWS e scripts de empacotamento, build e migração. |
| [`docs/`](docs/) | Arquitetura, implantação, requisitos, negócio e apresentação acadêmica. |

## Documentação

- [Arquitetura, decisões e diagramas](docs/architecture/README.md)
- [Docker](docs/deployment/docker-guide.md), [implantação na AWS](infrastructure/terraform/README.md) e [estado da implantação](docs/deployment/status.md)
- [Requisitos funcionais](docs/requisitos/requisitos-funcionais.md) e [não funcionais](docs/requisitos/requisitos-nao-funcionais.md)
- [Roteiro de apresentação](docs/apresentacao/README.md) e [resumo da entrega acadêmica](docs/apresentacao/material-academico.md)
