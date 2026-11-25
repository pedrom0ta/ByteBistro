# ByteBistro — System Design e Arquitetura de Software

## 1. Visão geral

O ByteBistro é um sistema de cardápio digital e gerenciamento de pedidos desenvolvido para permitir que clientes visualizem produtos, selecionem itens e realizem pedidos por meio de uma interface web.

Na versão atual, o Django executa a interface web, o painel e as regras de negócio, com persistência em SQLite pelo ORM Django. O checkout já registra pedidos e permite acompanhar seu andamento e gerenciá-los no painel. [Arquitetura atual](system-architecture.md)

A configuração distribuída implementa a consulta de status via GraphQL e o processamento assíncrono de pedidos. O Terraform define a infraestrutura AWS, cuja entrada pública e frotas ainda aguardam ativação.

### Objetivos do sistema

- Disponibilizar um cardápio digital acessível pela web.
- Permitir a visualização e seleção de produtos.
- Gerenciar o carrinho e os pedidos.
- Centralizar as regras de negócio no backend.
- Garantir persistência e integridade dos dados.
- Permitir processamento assíncrono de tarefas.
- Preparar a aplicação para escalabilidade horizontal.
- Oferecer uma infraestrutura segura e monitorável.

## 2. Arquitetura da aplicação

| Componente | Tecnologia | Responsabilidade |
|---|---|---|
| Aplicação web | Django, `urllib.request` e `boto3` (AWS) | Vitrine, painel, sessão, regras de negócio, checkout, consulta de status via API (`BYTEBISTRO_GRAPHQL_URL`) e envio de OTP por SMS (`ConsoleProvider` local / `SnsSmsProvider` via AWS SNS) |
| API de status | Node.js, TypeScript e Apollo Server | Consulta GraphQL autenticada de status do pedido (`POST /graphql`) e health check sem autenticação (`GET /healthz`) na porta `4000` |
| Worker | Node.js, Prisma, SQS e SNS | Publicação da outbox no SQS, envio de notificações enriquecidas ao SNS e registro de `"notified"` em `shop_orderevent` |
| Persistência | SQLite na demonstração e PostgreSQL na configuração distribuída | Django gerencia modelos e migrações. Prisma consulta pedidos e processa a outbox e eventos de notificação. |

O projeto inclui Dockerfiles para web, API e worker. [Guia Docker](../deployment/docker-guide.md)

### 2.1. Cliente web — Django

O Django renderiza páginas, mantém sessão e permissões e valida as requisições do cliente. Quando `BYTEBISTRO_GRAPHQL_URL` está configurada (apontando na AWS para o ALB interno em `http://${api_alb_dns}:4000/graphql`), o adaptador consulta o status via HTTP/GraphQL com token de serviço, dados da sessão e timeout. Na configuração AWS (`config/aws_settings.py`), a verificação de telefone no delivery usa `SnsSmsProvider` (`shop/sms.py`, com `boto3` e `SMS_COUNTRY_CODE = "+55"`). [Adaptador](../../apps/web/shop/graphql.py)

### 2.2. Backend — Node.js e TypeScript

O Apollo expõe a query `orderStatus` em `POST /graphql` (protegida por `Authorization: Bearer <GRAPHQL_SERVICE_TOKEN>`) e um endpoint de saúde sem autenticação `GET /healthz` (HTTP `200`) para `aws_lb_target_group.api`. O resolver consulta o pedido por ID e limita o resultado à sessão ou conta informada pelo Django. A transferência das escritas de negócio é uma evolução. [Serviços](../../apps/services/README.md) · [Contrato proposto](system-architecture.md#contrato-proposto)

### 2.3. Persistência — PostgreSQL

O Django grava pedidos no PostgreSQL e aplica as migrações. A API acessa o PostgreSQL via Prisma para ler o status em `shop_order`. O worker lê metadados do pedido em `shop_order`, consulta e atualiza `shop_orderoutbox` e registra `action = "notified"` em `shop_orderevent`. [Banco de dados](database.md)

## 3. Comunicação entre os componentes

Na demonstração, o navegador envia formulários e consultas de status ao Django. As views chamam serviços Python no mesmo processo e acessam o SQLite via ORM.

Na configuração distribuída, o navegador consulta o mesmo endereço de acompanhamento no Django. Na configuração AWS, o Django envia a query `orderStatus` ao ALB interno (porta `4000`), que encaminha à frota `api` (Apollo). O resolver consulta o PostgreSQL via Prisma e o Django devolve o JSON ao navegador. Uma sessão sem acesso recebe 404. Uma falha temporária da API recebe 503.

## 4. Fluxo de realização de pedidos

O processo de realização de um pedido representa um dos principais fluxos de negócio do ByteBistro.

### Fluxo atual

O Django mantém o carrinho em sessão, valida o destino e recalcula preços no servidor. O checkout grava o pedido e seu evento inicial na mesma transação SQLite. Reenvios autorizados com o mesmo token retornam o pedido existente. A equipe altera a etapa pelo painel e o navegador consulta o status periodicamente. [Serviço de checkout](../../apps/web/shop/services.py) · [Acompanhamento](../../apps/web/shop/views.py)

### Fluxo na configuração distribuída

O Django valida e grava o pedido no PostgreSQL. Com a outbox habilitada, grava também o evento a ser publicado, na mesma transação. O worker processa esse evento depois do commit, fora da requisição de checkout.

## 5. Arquitetura de mensageria

A configuração distribuída usa Amazon SQS, Amazon SNS e uma frota de workers independente da frota web.

O SQS recebe tarefas que não precisam ser executadas durante a requisição principal.

Os workers consomem as mensagens e executam o processamento em segundo plano.

O SNS pode distribuir notificações para diferentes consumidores.

A Dead Letter Queue (DLQ) recebe mensagens que não conseguiram ser processadas após as tentativas configuradas.

O worker publica o evento no SQS, consome a fila, lê os metadados do pedido em `shop_order` (`mode`, `total`, `payment`, `created`), publica no tópico SNS `notifications` (`Subject` e payload JSON `order.created` com `id`, `type`, `orderId`, `orderNumber`, `mode`, `totalCents`, `payment` e `createdAt`, atendendo assinaturas como `notification_email` via `aws_sns_topic_subscription.notifications`) e, na mesma transação em que marca `notifiedAt`, grava `action = "notified"` (`"Notificação enviada"` em `OrderEvent.label`) em `shop_orderevent`. Ele usa um identificador estável por evento e exclui a mensagem após o processamento. Assinantes devem deduplicar pelo identificador, pois uma falha entre a publicação ao SNS e a confirmação no banco pode causar reentrega.

Também devem ser considerados:

- Idempotência.
- Retentativas com backoff.
- Visibility Timeout.
- Monitoramento de mensagens.
- Tratamento de falhas.

## 6. Arquitetura de infraestrutura AWS

[Diagrama AWS completo](aws-architecture.md)

A infraestrutura proposta utiliza serviços gerenciados e computação em instâncias EC2.

A arquitetura distribui a aplicação em uma VPC com duas zonas de disponibilidade. O ALB público (`aws_lb.web`, em sub-redes públicas, HTTPS `443`) recebe o tráfego de origem do CloudFront e encaminha as requisições para a frota `web` (`8000`). O ALB interno (`aws_lb.api`, `internal = true`, em sub-redes privadas, HTTP `4000`) recebe chamadas do `web` (`BYTEBISTRO_GRAPHQL_URL=http://${api_alb_dns}:4000/graphql`) e encaminha para a frota `api` (`4000`). Todas as três frotas da aplicação e o banco ficam em sub-redes privadas.

### 6.1. Entrada e distribuição de tráfego

**Amazon Route 53** — gerenciamento obrigatório do domínio (`var.domain`, `var.hosted_zone_id`), registros `A`/`AAAA` para o CloudFront, registro `A` `origin.<domínio>` para o ALB público e validação DNS dos certificados ACM.

**Amazon CloudFront** — distribuição de conteúdo e ponto de entrada HTTPS obrigatório (`redirect-to-https`, certificado ACM `edge` em `us-east-1`), encaminhando requisições dinâmicas por `https-only` para `origin.<domínio>:443` com cabeçalho secreto `X-ByteBistro-Origin` e servindo `/static/*` do S3 via OAC.

**AWS WAF** — proteção ativa (`aws_wafv2_web_acl.edge`) contra requisições maliciosas e ataques comuns à aplicação web, aplicando `AWSManagedRulesCommonRuleSet` em modo de bloqueio por padrão (`waf_enforce = true` -> `none {}`) e limite de taxa (`2000` requisições por IP).

**AWS Certificate Manager** — gerenciamento obrigatório de dois certificados validados por DNS no Route 53: `edge` em `us-east-1` (CloudFront) e `origin` na região da aplicação (ALB público).

**Application Load Balancer** — dois balanceadores gerenciados: ALB público (`aws_lb.web`, sub-redes públicas, listener HTTPS `443` com `ELBSecurityPolicy-TLS13-1-2-2021-06` e health check `/healthz/` na frota `web:8000`) e ALB interno (`aws_lb.api`, sub-redes privadas, listener HTTP `4000` e health check `GET /healthz` sem autenticação na frota `api:4000`).

### 6.2. Camada de aplicação

**Amazon EC2** — executa os containers das três frotas em instâncias Amazon Linux 2023 resolvidas automaticamente via SSM Parameter Store (`data.aws_ssm_parameter.fleet_ami`).

**Auto Scaling Group** — três grupos independentes (`web`, `api` e `worker`, mínimo de 2 e máximo de 6 instâncias por frota quando `var.runtime != null`, total mínimo de 6 instâncias), cada um com IAM Role, Launch Template, segredo gerenciado (`aws_secretsmanager_secret.runtime[service].arn`) e política de CPU dedicados (além de escalonamento por backlog SQS no `worker`).

**Amazon ECR** — armazena as três imagens Docker (`web`, `api`, `worker`) identificadas por digest em `var.runtime`.

Django (`web`), API Node.js + Apollo (`api`) e workers (`worker`) executam em frotas próprias e desacopladas, escalando de forma independente entre entrada web, consultas GraphQL (via ALB interno na porta `4000`) e processamento assíncrono. [Decisões arquiteturais](architecture-decisions.md)

### 6.3. Camada de dados

**Amazon RDS PostgreSQL** — banco de dados gerenciado.

**Multi-AZ** mantém uma réplica de espera em outra zona para failover na modalidade de instância proposta.

**Amazon S3** — armazenamento de imagens e arquivos, sem depender do disco local das instâncias EC2.

### 6.4. Mensageria

**Amazon SQS** — fila de processamento assíncrono.

**Amazon SNS** — distribuição de notificações no tópico criptografado com KMS `aws_sns_topic.notifications` (com assinatura opcional via `var.notification_email` / `aws_sns_topic_subscription.notifications`), tópico separado de alarmes (`var.ops_email`) e envio direto de SMS OTP transacional pela frota `web` (`SnsSmsProvider` com permissão `sns:Publish`).

**Dead Letter Queue** — armazenamento de mensagens que falharam repetidamente.

### 6.5. Segurança e monitoramento

**AWS IAM** — gerenciamento de permissões e identidades.

**AWS Secrets Manager** — armazenamento de credenciais e segredos.

**Amazon CloudWatch** — monitoramento de logs, métricas e alarmes.

**AWS CloudTrail** — registro de atividades e chamadas de API na conta AWS.

### 6.6. Automação

**Docker** — padronização dos ambientes.

**Terraform** — criação e gerenciamento da infraestrutura como código.

**GitHub Actions** — workflow de testes, compilação e verificação do ZIP de release.

**CodeBuild** — pipeline definido para publicar imagens e executar a migração em um job separado. O último release foi publicado com Docker local por causa da cota da conta. [CI/CD](../deployment/ci-cd.md)

## 7. Escalabilidade e disponibilidade

A arquitetura proposta prevê escalabilidade horizontal para permitir o crescimento da aplicação.

Os Application Load Balancers (público para `web` e interno para `api`) distribuem o tráfego entre as instâncias EC2 disponíveis.

Os três Auto Scaling Groups independentes (`web`, `api` e `worker`, com `min_size = 2` por frota, mínimo de 6 EC2s quando `var.runtime != null`) podem adicionar ou remover instâncias de acordo com métricas de CPU e volume da fila SQS.

A utilização de duas zonas de disponibilidade reduz a dependência de uma única zona.

O RDS Multi-AZ oferece uma configuração de banco de dados com alta disponibilidade.

As instâncias da aplicação devem ser tratadas como recursos substituíveis. Arquivos importantes, sessões compartilhadas e dados persistentes não devem depender exclusivamente do armazenamento local de uma EC2.

## 8. Segurança

O painel atual usa autenticação por sessão, grupos de acesso e proteção CSRF. Clientes acompanham apenas pedidos associados à própria sessão ou conta. [Rotas e controles](../../apps/web/shop/staff_views.py)

Para a infraestrutura proposta, estão previstos os seguintes controles.

- Comunicação HTTPS obrigatória de ponta a ponta (Route 53 e ACM em `us-east-1`/região, CloudFront com `redirect-to-https` e `https-only` até o ALB público na porta `443` com cabeçalho `X-ByteBistro-Origin`).
- Controle de acesso por IAM com roles isoladas para `web`, `api` e `worker`.
- Credenciais armazenadas no Secrets Manager e referenciadas diretamente por frota.
- Banco de dados em sub-redes isoladas privadas.
- Security Groups com permissões restritas (incluindo isolamento da `api` atrás do ALB interno na porta `4000`).
- Proteção ativa da camada web com AWS WAFv2 (`waf_enforce = true` bloqueando `AWSManagedRulesCommonRuleSet` e rate-limit por IP).
- Armazenamento privado no S3.
- Separação entre recursos públicos e privados.

## 9. Observabilidade

O Terraform define grupos de logs e alarmes do CloudWatch para os seguintes indicadores.

- Alvos saudáveis nos Target Groups `web` (`${var.name}-web-unhealthy`) e `api` (`${var.name}-api-unhealthy`) quando as frotas estiverem ativas.
- Espaço livre no RDS.
- Mensagens na DLQ e idade da mensagem mais antiga no SQS.

As políticas de escalabilidade usam CPU e volume da fila. [Monitoramento](../../infrastructure/terraform/operations.tf) · [Políticas das frotas](../../infrastructure/terraform/compute.tf)

## 10. Considerações finais

O ByteBistro já separa apresentação, lógica de negócio e persistência em módulos Django. A evolução proposta leva as regras de negócio para uma API interna e os dados do domínio para PostgreSQL.

A proposta de infraestrutura AWS amplia essa arquitetura com balanceamento de carga, escalabilidade horizontal, armazenamento gerenciado, mensageria e monitoramento.

O resultado esperado é uma aplicação preparada para evoluir de um ambiente de desenvolvimento para uma implantação mais robusta, segura e escalável.

[Guia da infraestrutura](../../infrastructure/terraform/README.md)
