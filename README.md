# ByteBistro

Projeto da disciplina de Sistemas Distribuídos para gestão de cardápios e pedidos em restaurantes.

- **Equipe** Pedro Antonio, Tauan Gomes e Augusto Fagner
- **Professor** Levi Costa

## Diagrama de infraestrutura AWS

O diagrama mostra a configuração distribuída definida em Terraform. A demonstração pública roda em uma EC2 separada. [Detalhes do diagrama](docs/architecture/aws-architecture.md)

```mermaid
flowchart TB
    USER["CLIENTE<br/>Navegador Web"]

    subgraph ENTRY["1. ENTRADA E DISTRIBUIÇÃO"]
        R53["Route 53<br/>Domínio próprio (opcional)"]
        CF["CloudFront<br/>Distribuição"]
        WAF["AWS WAF<br/>Proteção"]
        ACM["ACM<br/>Domínio próprio (opcional)"]
        ALB["Application Load Balancer"]

        R53 --> CF --> ALB
        WAF -. Protege .-> CF
        ACM -. HTTPS .-> CF
    end

    subgraph VPC["2. AWS VPC — DUAS ZONAS DE DISPONIBILIDADE"]
        subgraph PUBLIC["SUB-REDES PÚBLICAS"]
            NAT["NAT Gateways<br/>Saída para internet"]
        end

        subgraph APP["SUB-REDES PRIVADAS — EC2 / AUTO SCALING"]
            WEB["Django<br/>Vitrine, painel e checkout"]
            API["Node.js + Apollo<br/>Consulta GraphQL de status"]
            WORKER["Worker<br/>Publicador e consumidor"]
            WEB -->|Consulta de status| API
        end

        subgraph DATA["CAMADA PRIVADA DE DADOS"]
            RDS[("RDS PostgreSQL<br/>Multi-AZ")]
        end

        ALB --> WEB
        WEB -->|Pedidos e outbox| RDS
        API -->|Leitura| RDS
        WORKER -->|Outbox| RDS
        NAT -. Saída .-> APP
    end

    subgraph MESSAGING["3. MENSAGERIA GERENCIADA"]
        SQS["SQS<br/>Fila de eventos"]
        DLQ["SQS DLQ<br/>Falhas repetidas"]
        SNS["SNS<br/>Notificações"]
        SQS -. Redrive .-> DLQ
    end

    WORKER -->|Publica| SQS
    SQS -->|Entrega| WORKER
    WORKER -->|Notifica| SNS

    subgraph STORAGE["4. ARMAZENAMENTO"]
        S3["Amazon S3<br/>Imagens e arquivos"]
        ECR["Amazon ECR<br/>Imagens Docker"]
    end

    CF --> S3
    ECR -. Imagens para EC2 .-> APP

    subgraph SECURITY["5. SEGURANÇA E OPERAÇÃO"]
        IAM["IAM<br/>Permissões"]
        SM["Secrets Manager<br/>Credenciais"]
        CW["CloudWatch<br/>Logs, métricas e alarmes"]
        CT["CloudTrail<br/>Auditoria"]
        BACKUP["AWS Backup<br/>Proteção de dados"]
    end

    IAM -. Autoriza acesso .-> APP
    SM -. Fornece segredos .-> APP
    APP -. Logs e métricas .-> CW
    RDS -. Métricas .-> CW
    CT -. Auditoria .-> CW
    RDS -. Backup .-> BACKUP

    USER -->|HTTPS| CF
    USER -. DNS com domínio próprio .-> R53
```

## Entrega acadêmica

- **Cliente.** Cardápio com busca e categorias, personalização de itens, carrinho, pedidos na mesa ou por delivery e acompanhamento.
- **Equipe do restaurante.** Painel com acesso por perfil, fila de pedidos, cozinha, mesas, catálogo, estoque e registro de recebimentos.
- **Demonstração.** A versão local roda com Django e SQLite e permite testar o delivery com o código de verificação no terminal. A vitrine também pode ser acessada na EC2. [Demonstração pública](https://54.209.48.237/)
- **Integração distribuída.** O projeto implementa consulta de status via Apollo/GraphQL e Prisma com PostgreSQL e um worker para SQS/SNS. As três imagens do release foram publicadas no ECR.

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
- [Docker](docs/deployment/docker-guide.md) e [implantação na AWS](infrastructure/terraform/README.md)
- [Requisitos funcionais](docs/requisitos/requisitos-funcionais.md) e [não funcionais](docs/requisitos/requisitos-nao-funcionais.md)
- [Roteiro de apresentação](docs/apresentacao/README.md) e [resumo da entrega acadêmica](docs/apresentacao/material-academico.md)
