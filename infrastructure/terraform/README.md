# Infraestrutura AWS do ByteBistro

Esta configuração descreve a topologia do [diagrama AWS](../../docs/architecture/aws-architecture.md) como código. A demonstração pública usa uma EC2 independente com Django. A imagem web do ambiente distribuído usa PostgreSQL com TLS verificado. O Django mantém o checkout e as migrações. Apollo/Prisma consulta o status e o worker processa os eventos de outbox via SQS e SNS. [Estado da implantação](../../docs/deployment/status.md)

| Camada | Recursos definidos |
| --- | --- |
| Entrada | CloudFront, WAF e ALB público. Route 53 e ACM são usados no modo com domínio próprio. |
| Rede | VPC com duas AZs, Internet Gateway, NAT por AZ, sub-redes públicas, privadas e de dados, endpoint gateway S3 e grupos de segurança. |
| Computação | Três repositórios ECR e, com `runtime` preenchido, Launch Templates e ASGs web e worker. Cada host web executa Django e Apollo. |
| Dados e mensageria | RDS PostgreSQL 16 Multi-AZ, S3 privado, SQS Standard com DLQ, SNS para notificações e tópico de alarmes separado. |
| Segurança e operação | IAM por frota, segredos em Secrets Manager, logs e alarmes CloudWatch, auditoria CloudTrail e backup diário de RDS via AWS Backup. |
| Publicação | CodeBuild constrói as três imagens, publica estáticos no S3 e executa migrações em uma tarefa separada na VPC. |

No modo padrão, o endereço público é `https://<distribuição>.cloudfront.net`, com certificado gerenciado pelo CloudFront. Nesse modo, CloudFront conecta ao ALB por HTTP. Com domínio próprio, Route 53 aponta para a distribuição, ACM emite os certificados e o enlace entre CloudFront e ALB usa HTTPS. Nos dois modos, o grupo de segurança do ALB restringe a origem à lista gerenciada do CloudFront e o listener exige um cabeçalho reservado. CloudFront mantém o cache desativado para a aplicação e serve `/static/*` do S3 via OAC. SQS e SNS são serviços regionais acessados via API. [Certificado padrão do CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesGeneral.html) · [Restrição da origem ALB](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/restrict-access-to-load-balancer.html)

## Preparação

- Escolher região e nome do ambiente. Para usar o endereço do CloudFront, deixar `domain` e `hosted_zone_id` comentados ou ausentes. Para usar domínio próprio, informar ambos e usar uma zona pública existente e delegada. O Terraform cria registros para o domínio público e `origin.<domínio>`.
- Configurar estado remoto criptografado e versionado antes de usar a configuração em equipe. O bucket de estado deve existir previamente. Usar chave de estado por ambiente e bloqueio nativo do backend S3. O estado contém o valor do cabeçalho da origem e deve ter acesso restrito. [Backend S3 do Terraform](https://developer.hashicorp.com/terraform/language/backend/s3)
- Usar credenciais temporárias e permissões de implantação. Conferir cotas, incluindo os grupos de segurança que consomem a lista de prefixos gerenciada do CloudFront.
- Revisar o orçamento antes de aplicar. Dois NAT Gateways, ALB, CloudFront/WAF conforme modalidade, armazenamento e RDS Multi-AZ podem gerar cobrança já na fase inicial. A ativação das frotas acrescenta quatro EC2 no mínimo. [AWS Pricing Calculator](https://calculator.aws/)

## Revisão e ativação

1. Copiar `terraform.tfvars.example` para `terraform.tfvars` e configurar o ambiente. Inicializar com `terraform init -backend-config=backend.hcl` (use `backend.hcl.example` como modelo), validar com `terraform validate` e revisar `terraform plan -out=base.tfplan`. Revisar o backend antes de implantar.
2. Após aprovar e aplicar a base, publicar imagens Linux x86_64 nos três repositórios ECR. Publicar assets sob `static/` no bucket indicado em `assets_bucket`. Com `runtime = null`, o endpoint dinâmico fica sem alvos.
3. Provisionar usuários PostgreSQL de aplicação e migração, com acesso privado e TLS, e preparar os segredos de execução. Usar o segredo de administrador gerado pelo RDS para inicialização controlada. Os processos devem receber credenciais de privilégio mínimo.
4. Preparar AMI Linux com Docker, AWS CLI v2, Python 3 e SSM Agent. Usar volume raiz criptografado na AMI ou por configuração padrão da conta. Preencher `runtime` com AMI, digests e ARNs de segredos. Gerar outro plano e revisar antes de aplicar.
5. Consultar `terraform output -raw application_url` para obter o link. Conferir alvos saudáveis em ambas as AZs, autenticação e cookies via CloudFront, entrega de arquivos, checkout, atualização no painel, processamento da fila, DLQ e restauração de backup. Confirmar a assinatura de e-mail operacional, se configurada, e definir assinantes para o tópico de notificações da aplicação.

## Contrato das imagens

| Imagem | Contrato |
| --- | --- |
| `web` | Django WSGI em `0.0.0.0:8000`, com sessão e cache compartilhados no PostgreSQL. O `/healthz/` verifica a conexão com o banco e responde ao ALB pelo IP privado. |
| `api` | Apollo ouvindo em `0.0.0.0:4000`, com consulta autenticada de status em `/graphql`. Usa credencial de leitura do banco e permanece na rede Docker privada do host. |
| `worker` | Executa o publicador da outbox e o consumidor, com reinício em falha e idempotência. O bootstrap injeta `BYTEBISTRO_QUEUE_URL` e `BYTEBISTRO_NOTIFICATION_TOPIC_ARN`. |

Os segredos de runtime devem estar na mesma conta e região, em JSON plano com valores string de uma linha. Use a chave padrão do Secrets Manager ou conceda `kms:Decrypt` específico se adotar chave própria. Django e Apollo compartilham o perfil IAM do host. A frota worker tem perfil separado. O uso de SSM para diagnóstico depende do agente na AMI e da saída HTTPS da VPC.

O ambiente novo inicia com os dados das migrações Django. A validação por SMS continua dependente de um provedor real para o delivery. Use mudanças de esquema compatíveis durante o rollout. Para reverter um release compatível, volte os digests e revise o plano de atualização das instâncias.

## Imagem Django

Na raiz do repositório, construa a imagem web com:

```powershell
docker build --platform linux/amd64 -t bytebistro-web:local ./apps/web
```

O segredo `web` deve fornecer `DJANGO_SECRET_KEY`, `PGHOST`, `PGDATABASE`, `PGUSER` e `PGPASSWORD`. Use o endpoint DNS do RDS como `PGHOST` para permitir a verificação de TLS. O contêiner usa o conjunto de certificados da AWS e a porta PostgreSQL 5432 por padrão. O usuário do Django deve ter acesso apenas às tabelas sob responsabilidade desse serviço.

Execute as migrações em uma etapa controlada, usando acesso privado ao banco. Publique o conteúdo de `apps/web/static/` sob o prefixo `static/` no bucket `assets_bucket`, preservando os caminhos dos arquivos.

## Publicação e migração

Na raiz do repositório, gere o ZIP e derive a tag do seu conteúdo com Python 3.11 ou superior.

```powershell
$releaseTag = python infrastructure/release/archive.py release.zip --print-tag
```

Envie esse ZIP a `release-source/<tag>.zip` no bucket de assets. Inicie o projeto `bytebistro-build` com esse objeto S3 como origem e a variável `RELEASE_TAG` preenchida com `$releaseTag`. Ao repetir o build do mesmo ZIP, o pipeline reutiliza as imagens que já existem no ECR para a tag. As imagens são construídas para `linux/amd64`. Após resolver os três digests, o build envia os estáticos ao S3 e grava o mapa em `releases/<tag>.json`.

O projeto `bytebistro-migrate` usa o mesmo pacote, roda em uma sub-rede privada e cria os usuários PostgreSQL, os valores dos segredos de runtime, as tabelas Django e a tabela do cache compartilhado. Execute-o antes de ativar as frotas. Se o CodeBuild estiver sem cota, construa as imagens localmente e execute a migração a partir de um executor temporário com acesso privado ao RDS e permissões equivalentes às do projeto de migração.

Valores de segredos são gerados no ambiente de migração. Mantenha no Terraform apenas os ARNs. Em caso de falhas no provisionamento, consulte o estado gerenciado e execute um novo plano após corrigir a restrição da conta.

### Publicação local quando o CodeBuild tem cota zero

Use o Docker com BuildKit e a tag do ZIP já enviado a `release-source/`. Na raiz do repositório, preencha `$registry` com o host do ECR obtido em `terraform output -json ecr_repositories`. Os comandos abaixo são para PowerShell e usam os nomes padrão dos repositórios.

```powershell
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $registry
docker buildx build --platform linux/amd64 --push -t "${registry}/bytebistro/web:${releaseTag}" ./apps/web
docker buildx build --platform linux/amd64 --push --target api -t "${registry}/bytebistro/api:${releaseTag}" ./apps/services
docker buildx build --platform linux/amd64 --push --target worker -t "${registry}/bytebistro/worker:${releaseTag}" ./apps/services
```

Em caso de timeout, consulte `aws ecr describe-images` antes de repetir. O ECR usa tags imutáveis, então repita apenas o comando da imagem que ainda estiver ausente. Depois, sincronize `apps/web/static/` com `s3://<bucket-de-assets>/static/` e grave `releases/<tag>.json` com as chaves `web`, `api` e `worker` e os digests retornados pelo ECR. Use esses digests no `runtime` do Terraform.

### Liberação da entrada pública

Se o CloudFront retornar HTTP 403 com `Your account must be verified before you can add new CloudFront resources`, encaminhe a mensagem e o Request ID ao AWS Support em **Account and billing**. Os artefatos podem ser publicados enquanto a conta aguarda verificação. Depois da liberação, gere um novo plano com o `runtime` do release e confira a disponibilidade da distribuição e a saúde dos alvos antes de divulgar a URL. [Abertura de chamados no AWS Support](https://docs.aws.amazon.com/awssupport/latest/user/case-management.html)
