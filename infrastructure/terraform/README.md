# Infraestrutura AWS do ByteBistro

Esta configuração descreve a topologia do [diagrama AWS](../../docs/architecture/aws-architecture.md) como código. A demonstração pública usa uma EC2 independente com Django. A imagem web do ambiente distribuído usa PostgreSQL com TLS verificado, chama a API Apollo/Prisma (`api`) por meio de um ALB interno (`aws_lb.api`) e envia SMS transacional OTP via AWS SNS (`SnsSmsProvider`). O Django mantém o checkout e as migrações, enquanto `worker` processa os eventos de outbox via SQS e SNS e registra notificações no histórico do pedido. [Estado da implantação](../../docs/deployment/status.md)

| Camada | Recursos definidos |
| --- | --- |
| Entrada | Route 53 (`domain` e `hosted_zone_id` obrigatórios), ACM (`edge` em `us-east-1` e `origin` na região), CloudFront (`https-only`), AWS WAFv2 (`AWSManagedRulesCommonRuleSet` com bloqueio ativo por padrão via `waf_enforce = true` e rate-limit de 2000 req/IP) e ALB público (HTTPS na porta `443`). |
| Rede | VPC com duas AZs, Internet Gateway, NAT por AZ, sub-redes públicas, privadas e isoladas de dados, ALB interno (`aws_lb.api`, `internal = true`, sub-redes privadas, HTTP na porta `4000`) entre `web` e `api`, endpoint gateway S3 e seis grupos de segurança da aplicação (`alb`, `internal_alb`, `web`, `api`, `worker`, `db`, além do SG de migração). |
| Computação | Três repositórios ECR (`web`, `api`, `worker`) e, com `runtime` preenchido (apenas os três digests), AMI Amazon Linux 2023 resolvida via SSM Parameter Store (`data.aws_ssm_parameter.fleet_ami`), três IAM Roles/Instance Profiles independentes, três Launch Templates e **três ASGs desacoplados (`web`, `api` e `worker`)** em sub-redes privadas (mínimo de 2 instâncias cada = 6 EC2). |
| Dados e mensageria | RDS PostgreSQL 16 Multi-AZ, S3 privado, SQS Standard com DLQ, tópico SNS `notifications` criptografado com KMS (com assinatura de e-mail opcional via `notification_email` / `aws_sns_topic_subscription.notifications`), tópico de alarmes separado (`ops_email`) e envio direto de SMS OTP via AWS SNS pela frota `web`. |
| Segurança e operação | IAM por frota, segredos pré-provisionados em `${var.name}/runtime/{web,api,worker}`, logs e alarmes CloudWatch (incluindo `HealthyHostCount` para `web` em `${var.name}-web-unhealthy` e `api` em `${var.name}-api-unhealthy`), auditoria CloudTrail e backup diário de RDS via AWS Backup. |
| Publicação | CodeBuild constrói as três imagens, publica estáticos no S3 e executa migrações em uma tarefa separada na VPC (com alternativa em EC2 temporária via `migration_release` em `migration-host.tf`). |

O Route 53 aponta `var.domain` (`A`/`AAAA`) para o CloudFront e `origin.<var.domain>` (`A`) para o ALB público (`aws_lb.web`). O ACM emite e valida por DNS os certificados `edge` (`us-east-1`) e `origin` (região). O CloudFront usa `origin_protocol_policy = "https-only"` (`cloudfront_default_certificate = false`), mantém WAFv2 ativo (`waf_enforce = true` aplica `none {}` em `AWSManagedRulesCommonRuleSet`, ou `count {}` se `false`, além do limite de taxa por IP), desabilita cache na origem dinâmica (`Managed-CachingDisabled`) e serve `/static/*` do S3 via OAC (`Managed-CachingOptimized`). O ALB público escuta apenas na porta `443` (`ELBSecurityPolicy-TLS13-1-2-2021-06`), restringe o grupo de segurança à prefix list gerenciada do CloudFront e exige o cabeçalho secreto `X-ByteBistro-Origin`. SQS e SNS são serviços regionais acessados via API. [Restrição da origem ALB](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/restrict-access-to-load-balancer.html)

## Preparação

- Escolher região e nome do ambiente. Os parâmetros `domain` (hostname DNS minúsculo de até 56 caracteres) e `hosted_zone_id` (`^Z[A-Z0-9]+$`) são **obrigatórios** (`nullable = false`) e devem usar uma zona pública existente e delegada no Route 53; o Terraform cria os registros de `var.domain`, `origin.<var.domain>` e validação dos certificados ACM. Opcionalmente, defina `waf_enforce` (padrão `true`), `notification_email` (padrão `null`) e `ops_email` (padrão `null`).
- Configurar estado remoto criptografado e versionado antes de usar a configuração em equipe. O bucket de estado deve existir previamente. Usar chave de estado por ambiente e bloqueio nativo do backend S3. O estado contém o valor do cabeçalho da origem e deve ter acesso restrito. [Backend S3 do Terraform](https://developer.hashicorp.com/terraform/language/backend/s3)
- Usar credenciais temporárias e permissões de implantação. Conferir cotas, incluindo os grupos de segurança que consomem a lista de prefixos gerenciada do CloudFront.
- Revisar o orçamento antes de aplicar. Dois NAT Gateways, dois ALBs (público `web` e interno `api`), CloudFront/WAF/Route 53/ACM sempre ativos, armazenamento e RDS Multi-AZ podem gerar cobrança já na fase inicial. A ativação das frotas com `var.runtime` acrescenta **seis EC2 no mínimo** (3 ASGs × `min_size = 2`). [AWS Pricing Calculator](https://calculator.aws/)

## Revisão e ativação

1. Copiar `terraform.tfvars.example` para `terraform.tfvars` e configurar `region`, `domain`, `hosted_zone_id` e eventuais variáveis opcionais. Inicializar com `terraform init -backend-config=backend.hcl` (use `backend.hcl.example` como modelo), validar com `terraform validate` e revisar `terraform plan -out=base.tfplan`. Revisar o backend antes de implantar.
2. Após aprovar e aplicar a base, publicar imagens Linux x86_64 nos três repositórios ECR (`web`, `api`, `worker`). Publicar assets sob `static/` no bucket indicado em `assets_bucket`. Com `runtime = null`, os Target Groups `web` e `api` permanecem sem alvos e seus alarmes de saúde ficam desativados.
3. Executar a migração para provisionar os três usuários PostgreSQL de aplicação (`bytebistro_web`, `bytebistro_api` e `bytebistro_worker`) com acesso privado, TLS e privilégio mínimo, além de popular os três segredos `${var.name}/runtime/{web,api,worker}` (`runtime_secret_arns`). Usar o segredo de administrador gerado pelo RDS apenas para essa inicialização controlada.
4. Terraform resolve automaticamente a AMI Amazon Linux 2023 via SSM Parameter Store (`data.aws_ssm_parameter.fleet_ami` em `/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64`), referencia os segredos diretamente por `aws_secretsmanager_secret.runtime[service].arn` e instala o Docker via `bootstrap.sh.tftpl` (ative a criptografia EBS padrão da conta se desejar volume raiz criptografado por padrão). Preencher `var.runtime` apenas com `{ web_digest, api_digest, worker_digest }` (`sha256:...`), gerar outro plano e revisar antes de aplicar.
5. Consultar `terraform output -raw application_url` para o endereço público e `terraform output -raw api_alb_dns` para o DNS do ALB interno. Conferir alvos saudáveis em ambas as AZs nos dois Target Groups (`web` em `/healthz/` e `api` em `/healthz`), os alarmes `${var.name}-web-unhealthy` e `${var.name}-api-unhealthy`, autenticação e cookies via CloudFront, entrega de estáticos, checkout, envio de SMS OTP via AWS SNS, atualização no painel, processamento da fila, DLQ e restauração de backup. Confirmar as assinaturas de e-mail `ops_email` (tópico `alarms`) e `notification_email` (tópico `notifications`), quando configuradas.

## Contrato das imagens

| Imagem | Contrato |
| --- | --- |
| `web` | Django WSGI com `--publish 8000:8000` (porta `8000`), sessão e cache compartilhados no PostgreSQL. O bootstrap injeta `BYTEBISTRO_PUBLIC_HOST`, `BYTEBISTRO_ORIGIN_HOST`, `BYTEBISTRO_GRAPHQL_URL=http://${api_alb_dns}:4000/graphql` e `BYTEBISTRO_OUTBOX_ENABLED=1`. O `/healthz/` verifica a conexão com o banco para o ALB público, e o OTP de delivery usa `SnsSmsProvider` (`sns:Publish` em `*`). |
| `api` | Node.js + Apollo Server + Prisma executando em ASG próprio (`api`) com `--publish 4000:4000`. Recebe chamadas de `web` pelo ALB interno (`aws_lb.api`, porta `4000`), responde `GET /healthz` sem autenticação (HTTP `200`, sem barra final) para o Target Group `api` e atende `POST /graphql` com `Authorization: Bearer <GRAPHQL_SERVICE_TOKEN>`, lendo `shop_order` via `DATABASE_URL` (`bytebistro_api`). |
| `worker` | Executa o publicador da outbox e o consumidor SQS em ASG próprio (`worker`), com reinício em falha e idempotência. O bootstrap injeta `BYTEBISTRO_QUEUE_URL` e `BYTEBISTRO_NOTIFICATION_TOPIC_ARN`. Lê metadados de `shop_order`, publica payload enriquecido `order.created` (`id`, `type`, `orderId`, `orderNumber`, `mode`, `totalCents`, `payment`, `createdAt`) com `Subject` em `aws_sns_topic.notifications` e grava `action = "notified"` em `shop_orderevent` ao marcar `shop_orderoutbox.notifiedAt`. |

Os segredos de runtime ficam na mesma conta e região (`aws_secretsmanager_secret.runtime`), em JSON plano com valores string de uma linha. Use a chave padrão do Secrets Manager ou conceda `kms:Decrypt` específico se adotar chave própria. Cada frota possui **IAM Role e Instance Profile próprios** (`${var.name}-web`, `${var.name}-api` e `${var.name}-worker`), recebendo `AmazonSSMManagedInstanceCore`, pull restrito ao respectivo repositório ECR, `secretsmanager:GetSecretValue` no respectivo segredo `${var.name}/runtime/<service>` e logs no CloudWatch. Além disso, `web` recebe `sns:Publish` (`Resource = "*"`) para SMS OTP, e `worker` recebe permissões de SQS (`SendMessage`, `ReceiveMessage`, `DeleteMessage`, `ChangeMessageVisibility` na fila `jobs`), SNS (`sns:Publish` no tópico `notifications`) e KMS (`kms:GenerateDataKey` e `kms:Decrypt` via `sns.<região>.amazonaws.com` na chave do tópico). O uso de SSM para diagnóstico depende do agente na AL2023 e da saída HTTPS da VPC.

As migrações Django incluem os dados iniciais do ambiente. Em `apps/web/config/aws_settings.py`, `SMS_PROVIDER` já usa por padrão `shop.sms.SnsSmsProvider` (com `SMS_COUNTRY_CODE` padrão `+55`), utilizando diretamente a role IAM da frota `web` — sobrescreva `SMS_PROVIDER` apenas se optar por outro provedor. Use mudanças de esquema compatíveis durante o rollout. Para reverter um release compatível, volte os digests em `var.runtime` e revise o plano de atualização das instâncias.

## Imagem Django

Na raiz do repositório, construa a imagem web com:

```powershell
docker build --platform linux/amd64 -t bytebistro-web:local ./apps/web
```

As migrações (`infrastructure/release/migrate.py`) preenchem os três segredos em `${var.name}/runtime/{web,api,worker}`:
- `web`: `DJANGO_SECRET_KEY`, `GRAPHQL_SERVICE_TOKEN`, `PGHOST`, `PGDATABASE`, `PGUSER` (`bytebistro_web`) e `PGPASSWORD`.
- `api`: `DATABASE_URL` (`bytebistro_api`) e `GRAPHQL_SERVICE_TOKEN`.
- `worker`: `DATABASE_URL` (`bytebistro_worker`).

Use o endpoint DNS do RDS como `PGHOST` para permitir a verificação de TLS. O contêiner usa o conjunto de certificados da AWS e a porta PostgreSQL 5432 por padrão. Cada usuário recebe privilégio mínimo (`bytebistro_web`: `USAGE, CREATE ON SCHEMA public`; `bytebistro_api`: `SELECT ON shop_order`; `bytebistro_worker`: `SELECT ON shop_order`, `SELECT, UPDATE ON shop_orderoutbox`, `INSERT ON shop_orderevent` e `USAGE, SELECT` na sequência `shop_orderevent_id_seq`).

Execute as migrações em uma etapa controlada, usando acesso privado ao banco. Publique o conteúdo de `apps/web/static/` sob o prefixo `static/` no bucket `assets_bucket`, preservando os caminhos dos arquivos.

## Publicação e migração

Na raiz do repositório, gere o ZIP e derive a tag do seu conteúdo com Python 3.11 ou superior.

```powershell
$releaseTag = python infrastructure/release/archive.py release.zip --print-tag
```

Envie esse ZIP a `release-source/<tag>.zip` no bucket de assets. Inicie o projeto `bytebistro-build` com esse objeto S3 como origem e a variável `RELEASE_TAG` preenchida com `$releaseTag`. Ao repetir o build do mesmo ZIP, o pipeline reutiliza as imagens que já existem no ECR para a tag. As imagens são construídas para `linux/amd64`. Após resolver os três digests, o build envia os estáticos ao S3 e grava o mapa em `releases/<tag>.json`.

O projeto `bytebistro-migrate` usa o mesmo pacote, roda em uma sub-rede privada e cria os usuários PostgreSQL com suas concessões de tabela/sequência, os valores dos segredos de runtime, as tabelas Django e a tabela do cache compartilhado. Execute-o antes de ativar as frotas. Se o CodeBuild estiver sem cota, utilize a variável `migration_release` (`migration-host.tf`) para provisionar um executor EC2 temporário em sub-rede privada com acesso ao RDS e às permissões equivalentes às do projeto de migração.

Valores de segredos são gerados no ambiente de migração e gravados nos segredos gerenciados pelo Terraform (`output runtime_secret_arns`). Não informe ARNs de segredos nem AMI em `terraform.tfvars`, pois `compute.tf` referencia `aws_secretsmanager_secret.runtime[service].arn` e `data.aws_ssm_parameter.fleet_ami` diretamente. Em caso de falhas no provisionamento, consulte o estado gerenciado e execute um novo plano após corrigir a restrição da conta.

### Publicação local quando o CodeBuild tem cota zero

Use o Docker com BuildKit e a tag do ZIP já enviado a `release-source/`. Na raiz do repositório, preencha `$registry` com o host do ECR obtido em `terraform output -json ecr_repositories`. Os comandos abaixo são para PowerShell e usam os nomes padrão dos repositórios (ajuste `--region` conforme `var.region`).

```powershell
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $registry
docker buildx build --platform linux/amd64 --push -t "${registry}/bytebistro/web:${releaseTag}" ./apps/web
docker buildx build --platform linux/amd64 --push --target api -t "${registry}/bytebistro/api:${releaseTag}" ./apps/services
docker buildx build --platform linux/amd64 --push --target worker -t "${registry}/bytebistro/worker:${releaseTag}" ./apps/services
```

Em caso de timeout, consulte `aws ecr describe-images` antes de repetir. O ECR usa tags imutáveis, então repita apenas o comando da imagem que ainda estiver ausente. Depois, sincronize `apps/web/static/` com `s3://<bucket-de-assets>/static/` e grave `releases/<tag>.json` com as chaves `web`, `api` e `worker` e os digests retornados pelo ECR. Use esses digests em `var.runtime` (`web_digest`, `api_digest`, `worker_digest`).

### Liberação da entrada pública

Para um HTTP 403 do CloudFront com `Your account must be verified before you can add new CloudFront resources`, encaminhe a mensagem e o Request ID ao AWS Support em **Account and billing**. Gere o plano de ativação com o `runtime` do release e confira a disponibilidade das saídas `application_url` e `api_alb_dns` e a saúde dos alvos nos Target Groups `web` (`/healthz/`) e `api` (`/healthz`) antes de divulgar a URL. [Abertura de chamados no AWS Support](https://docs.aws.amazon.com/awssupport/latest/user/case-management.html)

## Referência de variáveis e saídas

| Tipo | Nome | Descrição resumida |
| --- | --- | --- |
| Variável | `region` | Região AWS (obrigatória). |
| Variável | `name` | Prefixo dos recursos (padrão `"bytebistro"`). |
| Variável | `domain` | Domínio público obrigatório no Route 53 / CloudFront (até 56 caracteres). |
| Variável | `hosted_zone_id` | ID obrigatório da zona pública no Route 53 (`^Z[A-Z0-9]+$`). |
| Variável | `waf_enforce` | Ativa bloqueio (`none {}`) em `AWSManagedRulesCommonRuleSet` (padrão `true`). |
| Variável | `runtime` | Objeto `{ web_digest, api_digest, worker_digest }` (`default = null`). |
| Variável | `instance_type` | Tipo EC2 das três frotas (padrão `"t3.small"`). |
| Variável | `db_instance_class` | Classe do RDS PostgreSQL (padrão `"db.t4g.medium"`). |
| Variável | `db_backup_retention_period` | Retenção de backups do RDS em dias (`1..35`, padrão `1`). |
| Variável | `ops_email` | E-mail opcional para alarmes do CloudWatch (`aws_sns_topic_subscription.ops`). |
| Variável | `notification_email` | E-mail opcional para notificações de pedido (`aws_sns_topic_subscription.notifications`). |
| Variável | `migration_release` | Tag opcional (`release-...`) para executor temporário de migração em EC2 (`migration-host.tf`). |
| Saída | `application_url` | URL HTTPS pública da distribuição CloudFront (`https://${var.domain}`). |
| Saída | `api_alb_dns` | DNS interno do ALB da frota `api` (`aws_lb.api.dns_name`). |
| Saída | `ecr_repositories` | Mapa de URLs dos repositórios ECR (`web`, `api`, `worker`). |
| Saída | `postgres_address` | Endereço privado do RDS PostgreSQL. |
| Saída | `postgres_admin_secret_arn` | ARN do segredo mestre do RDS no Secrets Manager. |
| Saída | `assets_bucket` | Nome do bucket S3 de estáticos e artefatos de release. |
| Saída | `queue_url` | URL da fila SQS `jobs`. |
| Saída | `notification_topic_arn` | ARN do tópico SNS `notifications`. |
| Saída | `runtime_secret_arns` | Mapa de ARNs dos segredos `${var.name}/runtime/{web,api,worker}`. |
