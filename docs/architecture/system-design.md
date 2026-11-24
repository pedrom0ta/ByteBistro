# ByteBistro — System Design e Arquitetura de Software

## 1. Visão geral

O ByteBistro é um sistema de cardápio digital e gerenciamento de pedidos desenvolvido para permitir que clientes visualizem produtos, selecionem itens e realizem pedidos por meio de uma interface web.

Na versão atual, o Django executa a interface web, o painel e as regras de negócio, com persistência em SQLite pelo ORM Django. O checkout já registra pedidos e permite acompanhar seu andamento e gerenciá-los no painel. [Arquitetura atual](system-architecture.md)

A configuração distribuída implementa a consulta de status via GraphQL e o processamento assíncrono de pedidos. O Terraform define a infraestrutura AWS, cuja entrada pública e frotas ainda aguardam ativação. [Estado da implantação](../deployment/status.md)

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
| Aplicação web | Django e `urllib.request` | Vitrine, painel, sessão, regras de negócio, checkout e consulta de status pela API quando configurada |
| API de status | Node.js, TypeScript e Apollo Server | Consulta autenticada de status do pedido |
| Worker | Node.js, Prisma, SQS e SNS | Publicação da outbox e encaminhamento de notificações |
| Persistência | SQLite na demonstração e PostgreSQL na configuração distribuída | Django gerencia modelos e migrações. Prisma consulta pedidos e processa a outbox. |

O projeto inclui Dockerfiles para web, API e worker. [Guia Docker](../deployment/docker-guide.md)

### 2.1. Cliente web — Django

O Django renderiza páginas, mantém sessão e permissões e valida as requisições do cliente. Quando `BYTEBISTRO_GRAPHQL_URL` está configurada, o adaptador consulta o status via HTTP/GraphQL com token de serviço, dados da sessão e timeout. [Adaptador](../../apps/web/shop/graphql.py)

### 2.2. Backend — Node.js e TypeScript

O Apollo expõe a query `orderStatus`. O resolver consulta o pedido por ID e limita o resultado à sessão ou conta informada pelo Django. A transferência das escritas de negócio é uma evolução. [Serviços](../../apps/services/README.md) · [Contrato proposto](system-architecture.md#contrato-proposto)

### 2.3. Persistência — PostgreSQL

O Django grava pedidos no PostgreSQL e aplica as migrações. A API acessa o PostgreSQL via Prisma para ler o status. O worker consulta e atualiza a outbox. [Banco de dados](database.md)

## 3. Comunicação entre os componentes

Na demonstração, o navegador envia formulários e consultas de status ao Django. As views chamam serviços Python no mesmo processo e acessam o SQLite via ORM.

Na configuração distribuída, o navegador consulta o mesmo endereço de acompanhamento no Django. O Django envia a query `orderStatus` ao Apollo. O resolver consulta o PostgreSQL via Prisma e o Django devolve o JSON ao navegador. Uma sessão sem acesso recebe 404. Uma falha temporária da API recebe 503.

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

O worker publica o evento no SQS, consome a fila e notifica o SNS. Ele usa um identificador estável por evento e exclui a mensagem após o processamento. Assinantes devem deduplicar pelo identificador, pois uma falha entre a publicação ao SNS e a confirmação no banco pode causar reentrega.

Também devem ser considerados:

- Idempotência.
- Retentativas com backoff.
- Visibility Timeout.
- Monitoramento de mensagens.
- Tratamento de falhas.

## 6. Arquitetura de infraestrutura AWS

[Diagrama AWS completo](aws-architecture.md)

A infraestrutura proposta utiliza serviços gerenciados e computação em instâncias EC2.

A proposta distribui a aplicação em uma VPC com duas zonas de disponibilidade. O ALB recebe o tráfego de origem do CloudFront e encaminha as requisições às instâncias saudáveis. As instâncias da aplicação e o banco ficam em sub-redes privadas.

### 6.1. Entrada e distribuição de tráfego

**Amazon Route 53** — gerenciamento do domínio e resolução DNS.

**Amazon CloudFront** — distribuição de conteúdo e ponto de entrada da aplicação.

**AWS WAF** — proteção contra requisições maliciosas e ataques comuns à aplicação web.

**AWS Certificate Manager** — gerenciamento dos certificados HTTPS.

**Application Load Balancer** — distribuição das requisições entre as instâncias disponíveis.

### 6.2. Camada de aplicação

**Amazon EC2** — executa os containers da aplicação.

**Auto Scaling Group** — aumenta ou reduz a quantidade de instâncias conforme a demanda e as políticas configuradas.

**Amazon ECR** — armazena as imagens Docker utilizadas na implantação.

Django, API Node.js e workers terão responsabilidades distintas. A frota de workers poderá escalar separadamente do tráfego web. Separar Django e Node.js em frotas próprias é uma evolução a validar conforme a demanda. [Decisões arquiteturais](architecture-decisions.md)

### 6.3. Camada de dados

**Amazon RDS PostgreSQL** — banco de dados gerenciado.

**Multi-AZ** mantém uma réplica de espera em outra zona para failover na modalidade de instância proposta.

**Amazon S3** — armazenamento de imagens e arquivos, sem depender do disco local das instâncias EC2.

### 6.4. Mensageria

**Amazon SQS** — fila de processamento assíncrono.

**Amazon SNS** — distribuição de notificações.

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

**CodeBuild** — pipeline definido para publicar imagens e executar a migração em um job separado. O último release foi publicado com Docker local por causa da cota da conta. [CI/CD](../deployment/ci-cd.md) · [Estado da implantação](../deployment/status.md)

## 7. Escalabilidade e disponibilidade

A arquitetura proposta prevê escalabilidade horizontal para permitir o crescimento da aplicação.

O Application Load Balancer distribui o tráfego entre as instâncias EC2 disponíveis.

O Auto Scaling Group pode adicionar ou remover instâncias de acordo com métricas e políticas configuradas.

A utilização de duas zonas de disponibilidade reduz a dependência de uma única zona.

O RDS Multi-AZ oferece uma configuração de banco de dados com alta disponibilidade.

As instâncias da aplicação devem ser tratadas como recursos substituíveis. Arquivos importantes, sessões compartilhadas e dados persistentes não devem depender exclusivamente do armazenamento local de uma EC2.

## 8. Segurança

O painel atual usa autenticação por sessão, grupos de acesso e proteção CSRF. Clientes acompanham apenas pedidos associados à própria sessão ou conta. [Rotas e controles](../../apps/web/shop/staff_views.py)

Para a infraestrutura proposta, estão previstos os seguintes controles.

- Comunicação HTTPS.
- Controle de acesso por IAM.
- Credenciais armazenadas no Secrets Manager.
- Banco de dados em sub-redes privadas.
- Security Groups com permissões restritas.
- Proteção da camada web com WAF.
- Armazenamento privado no S3.
- Separação entre recursos públicos e privados.

## 9. Observabilidade

O Terraform define grupos de logs e alarmes do CloudWatch para os seguintes indicadores.

- Alvos web saudáveis quando a frota estiver ativa.
- Espaço livre no RDS.
- Mensagens na DLQ e idade da mensagem mais antiga no SQS.

As políticas de escalabilidade usam CPU e volume da fila. [Monitoramento](../../infrastructure/terraform/operations.tf) · [Políticas das frotas](../../infrastructure/terraform/compute.tf)

## 10. Considerações finais

O ByteBistro já separa apresentação, lógica de negócio e persistência em módulos Django. A evolução proposta leva as regras de negócio para uma API interna e os dados do domínio para PostgreSQL.

A proposta de infraestrutura AWS amplia essa arquitetura com balanceamento de carga, escalabilidade horizontal, armazenamento gerenciado, mensageria e monitoramento.

O resultado esperado é uma aplicação preparada para evoluir de um ambiente de desenvolvimento para uma implantação mais robusta, segura e escalável.

[Guia da infraestrutura](../../infrastructure/terraform/README.md) · [Estado da implantação](../deployment/status.md)
