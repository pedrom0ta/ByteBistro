# Diagrama de infraestrutura AWS

O diagrama apresenta a configuração distribuída definida no Terraform para duas zonas de disponibilidade. A demonstração pública usa uma EC2 independente. [Estado da implantação](../deployment/status.md) [System Design](system-design.md#6-arquitetura-de-infraestrutura-aws) · [Fonte Mermaid editável](diagrams/aws-infrastructure.mmd)

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

O ALB usa sub-redes públicas. SQS, DLQ e SNS são serviços gerenciados externos às sub-redes. Com domínio próprio, o Route 53 resolve o nome e o ACM fornece o certificado. No modo padrão, o navegador usa o endereço HTTPS do CloudFront. O Django grava a outbox junto com o pedido, e o worker encaminha o evento ao SQS depois do commit. [Estratégia de outbox](system-design.md#5-arquitetura-de-mensageria)
