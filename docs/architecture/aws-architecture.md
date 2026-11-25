# Diagrama de infraestrutura AWS

O diagrama apresenta a configuração distribuída definida no Terraform para duas zonas de disponibilidade. [System Design](system-design.md#6-arquitetura-de-infraestrutura-aws) · [Fonte Mermaid editável](diagrams/aws-infrastructure.mmd)

```mermaid
flowchart TB
    USER["CLIENTE<br/>Navegador Web"]

    subgraph ENTRY["1. ENTRADA E DISTRIBUIÇÃO (HTTPS + WAF ATIVOS)"]
        R53["Route 53<br/>var.domain e origin.&lt;domain&gt;"]
        CF["CloudFront<br/>Distribuição (https-only)"]
        WAF["AWS WAFv2<br/>Bloqueio ativo + Rate Limit"]
        ACM_EDGE["ACM (us-east-1)<br/>Certificado Edge obrigatório"]
        ACM_ORIGIN["ACM (Região)<br/>Certificado Origin obrigatório"]

        R53 -->|"A/AAAA (var.domain)"| CF
        WAF -. "Bloqueio ativo" .-> CF
        ACM_EDGE -. "TLS Edge" .-> CF
    end

    subgraph VPC["2. AWS VPC — DUAS ZONAS DE DISPONIBILIDADE"]
        IGW["Internet Gateway (IGW)<br/>Rota 0.0.0.0/0 pública"]

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

        VPCE_S3["VPC Gateway Endpoint (S3)<br/>Rota privada S3"]

        subgraph DATA["SUB-REDES ISOLADAS DE DADOS"]
            RDS[("RDS PostgreSQL 16<br/>Multi-AZ (:5432)")]
        end

        IGW -->|"Rota pública"| ALB_PUB
        NAT -->|"Saída 0.0.0.0/0"| IGW
        ALB_PUB -->|"HTTP :8000"| ASG_WEB
        ASG_WEB -->|"Pedidos, cache e outbox :5432"| RDS
        ASG_API -->|"Leitura shop_order :5432"| RDS
        ASG_WORKER -->|"Outbox, shop_order e shop_orderevent :5432"| RDS
        PRIVATE -. "Saída HTTPS :443" .-> NAT
        PRIVATE -. "Rota privada S3" .-> VPCE_S3
    end

    R53 -->|"A Alias (origin.&lt;domain&gt;)"| ALB_PUB
    CF -->|"HTTPS :443 + Header secreto"| ALB_PUB
    ACM_ORIGIN -. "TLS :443" .-> ALB_PUB

    subgraph MESSAGING["3. MENSAGERIA E NOTIFICAÇÕES"]
        SQS["SQS<br/>Fila de eventos (jobs)"]
        DLQ["SQS DLQ<br/>Falhas repetidas (dead)"]
        SNS_NOTIF["SNS Notificações (KMS)<br/>Evento order.created"]
        SUB_EMAIL["Assinatura E-mail obrigatória<br/>notification_email"]
        SNS_ALARMS["SNS Alarmes<br/>bytebistro-alarms"]
        SUB_OPS["Assinatura E-mail obrigatória<br/>ops_email"]
        SNS_SMS["AWS SNS SMS<br/>OTP Transacional (+55)"]

        SQS -. "Redrive" .-> DLQ
        SNS_NOTIF -->|"E-mail"| SUB_EMAIL
        SNS_ALARMS -->|"E-mail"| SUB_OPS
    end

    ASG_WORKER -->|"Publica"| SQS
    SQS -->|"Consome"| ASG_WORKER
    ASG_WORKER -->|"order.created"| SNS_NOTIF
    ASG_WEB -->|"SMS OTP (sns:Publish)"| SNS_SMS

    subgraph STORAGE["4. ARMAZENAMENTO"]
        S3_ASSETS["S3 Assets<br/>/static/* (OAC) e artefatos de release"]
        S3_AUDIT["S3 Audit<br/>Logs do CloudTrail"]
        ECR["Amazon ECR<br/>3 imagens (web, api, worker)"]
    end

    CF -->|"/static/* (OAC)"| S3_ASSETS
    VPCE_S3 -->|"Acesso privado"| S3_ASSETS
    ECR -. "Pull 3 imagens" .-> PRIVATE

    subgraph SECURITY["5. SEGURANÇA, CONFIGURAÇÃO E OPERAÇÃO"]
        IAM["IAM<br/>3 roles isoladas (web, api, worker)"]
        KMS["AWS KMS<br/>Chave de criptografia SNS"]
        SSM["SSM Parameter Store<br/>AMI AL2023 automática"]
        SM["Secrets Manager<br/>Segredos runtime e RDS"]
        CW["CloudWatch<br/>Logs e alarmes HealthyHostCount (web/api)"]
        CT["CloudTrail<br/>Auditoria multi-região"]
        BACKUP["AWS Backup<br/>Backup diário do RDS"]
    end

    IAM -. "Autoriza acessos" .-> PRIVATE
    KMS -. "Criptografa" .-> SNS_NOTIF
    KMS -. "Autorizado via IAM" .-> ASG_WORKER
    SSM -. "Resolve AMI AL2023" .-> PRIVATE
    SM -. "Injeta segredos" .-> PRIVATE
    PRIVATE -. "Logs e métricas" .-> CW
    RDS -. "Métricas" .-> CW
    CW -->|"Alarmes"| SNS_ALARMS
    CT -. "Logs" .-> S3_AUDIT
    CT -. "Métricas" .-> CW
    RDS -. "Backup diário" .-> BACKUP

    subgraph DELIVERY["6. ENTREGA E MIGRAÇÃO"]
        CB["CodeBuild<br/>Projetos build e migrate"]
        MIG_EC2["EC2 temporária de migração (fallback)<br/>Instância sob demanda (migration_release)"]
    end

    CB -->|"Push 3 imagens"| ECR
    CB -->|"Source, /static/* e releases"| S3_ASSETS
    CB -->|"Migrações :5432"| RDS
    CB -. "Lê/grava segredos" .-> SM
    CB -. "Logs de release" .-> CW
    MIG_EC2 -->|"Source e resultado"| S3_ASSETS
    MIG_EC2 -->|"Migrações :5432"| RDS
    MIG_EC2 -. "Lê/grava segredos" .-> SM

    USER -->|"DNS obrigatório"| R53
    USER -->|"HTTPS"| CF
```

- **Camada de entrada (R2)**: `var.domain` e `var.hosted_zone_id` são obrigatórios. O Route 53 resolve o domínio público (`A`/`AAAA` para o CloudFront), aponta `origin.<domínio>` (`A` Alias) para o ALB público e valida dois certificados ACM via DNS: um em `us-east-1` (`edge`) para o CloudFront e outro regional (`origin.<domínio>`) para o ALB público. O AWS WAFv2 aplica `AWSManagedRulesCommonRuleSet` em modo de bloqueio ativo por padrão (`waf_enforce = true`, `none {}`) e limite de taxa (`2000` requisições por IP). O CloudFront encaminha o tráfego dinâmico para o ALB público exclusivamente por HTTPS (`origin_protocol_policy = "https-only"` na porta `443`) com o cabeçalho secreto `X-ByteBistro-Origin`, enquanto `/static/*` é servido do bucket `S3 Assets` via OAC.
- **Rede, 3 ASGs e ALB interno (R1)**: A VPC abrange duas zonas de disponibilidade com `Internet Gateway (IGW)` conectado às sub-redes públicas (`ALB Público` e `NAT Gateways`), sub-redes privadas (frotas e `ALB Interno`) com saída HTTPS via NAT Gateways e `VPC Gateway Endpoint (S3)` para acesso privado ao bucket `S3 Assets`, além de sub-redes isoladas de dados (`RDS PostgreSQL 16 Multi-AZ`). Cada serviço executa em seu próprio Auto Scaling Group (`web`, `api` e `worker`, mínimo de 2 e máximo de 6 instâncias EC2 por frota quando `var.runtime != null`, total mínimo de 6 instâncias), com IAM Role, Launch Template e política de CPU dedicados (além de escalonamento por backlog SQS no `worker`). O ALB público (`443`) encaminha para o Target Group `web` (`HTTP :8000`, health check `/healthz/`). O Django (`web`) consulta a API Node.js + Apollo por meio do ALB interno (`aws_lb.api`, `internal = true`, sub-redes privadas, `HTTP :4000`, `BYTEBISTRO_GRAPHQL_URL=http://<api_alb_dns>:4000/graphql`), cujo Target Group verifica `GET /healthz` (HTTP `200` sem autenticação) enquanto `POST /graphql` exige `Authorization: Bearer`.
- **Mensageria, notificações e SMS (R3)**: O Django grava pedidos, cache (`PostgresCache`) e registros de outbox no RDS; o `worker` encaminha eventos da outbox ao SQS (`jobs`, com redrive para a DLQ `dead`) e consome a fila lendo `shop_order`, publicando payloads enriquecidos `order.created` no tópico `SNS Notificações` (`bytebistro-notifications`, criptografado com `AWS KMS` e autorizado via IAM para o `ASG worker`) com assinatura de e-mail obrigatória `notification_email`, além de gravar o evento `"notified"` em `shop_orderevent`. Para verificação por telefone em produção, a frota `web` usa `SnsSmsProvider` (`boto3` com `sns:Publish`) para enviar SMS transacionais diretamente pelo AWS SNS. Os alarmes do CloudWatch disparam notificações no tópico `SNS Alarmes` (`bytebistro-alarms`) conectado à assinatura de e-mail obrigatória `ops_email`. [Estratégia de outbox](system-design.md#5-arquitetura-de-mensageria)
- **Armazenamento, operação e segurança (R4)**: A camada de armazenamento separa dois buckets S3 privados e versionados — `S3 Assets` (`/static/*` via CloudFront OAC e artefatos de release) e `S3 Audit` (logs imutáveis do CloudTrail) — além dos 3 repositórios imutáveis do Amazon ECR (`web`, `api`, `worker`). Os Launch Templates resolvem automaticamente a AMI Amazon Linux 2023 via SSM Parameter Store (`data.aws_ssm_parameter.fleet_ami`) e injetam os segredos de runtime de `aws_secretsmanager_secret.runtime` (além da senha mestre gerenciada do RDS no Secrets Manager). A chave `AWS KMS` com rotação automática protege o tópico `SNS Notificações` e é autorizada via IAM para a frota `worker` (`kms:ViaService` para SNS). O CloudWatch centraliza logs (serviços, release e CloudTrail) e alarmes — incluindo `HealthyHostCount` para os Target Groups `web` e `api`, idade/DLQ do SQS e armazenamento livre do RDS — enquanto o CloudTrail multi-região registra auditoria no `S3 Audit` e no CloudWatch, e o AWS Backup executa backups diários do PostgreSQL.
- **Entrega e migração**: O `AWS CodeBuild` executa dois projetos gerenciados: `build` (lê o pacote em `S3 Assets`, publica as 3 imagens no `ECR` e envia `/static/*` e artefatos ao `S3 Assets`) e `migrate` (executa nas sub-redes privadas da VPC, lê/atualiza segredos no `Secrets Manager` e aplica migrações no `RDS PostgreSQL`). Como contingência quando o CodeBuild está indisponível, `var.migration_release` provisiona uma `EC2 temporária de migração` (`t3.micro` em sub-rede privada, com desligamento automático) que lê o artefato em `S3 Assets`, acessa o `Secrets Manager`, aplica as migrações no `RDS PostgreSQL` e grava o resultado em `S3 Assets`.
