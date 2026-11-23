# ByteBistro — System Design e Arquitetura de Software

## 1. Visão geral

O ByteBistro é um sistema de cardápio digital e gerenciamento de pedidos desenvolvido para permitir que clientes visualizem produtos, selecionem itens e realizem pedidos por meio de uma interface web.

Na versão atual, o Django executa a interface web, o painel e as regras de negócio, com persistência em SQLite pelo ORM Django. O checkout já registra pedidos e permite acompanhar seu andamento e gerenciá-los no painel. [Arquitetura atual](system-architecture.md)

A arquitetura distribuída é uma proposta que separa interface, backend e persistência para preparar a aplicação para operar em uma infraestrutura escalável e de alta disponibilidade na Amazon Web Services (AWS).

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

A arquitetura lógica proposta é dividida em três componentes principais:

| Componente | Tecnologia | Responsabilidade |
|---|---|---|
| Cliente web | Django e Requests | Interface e comunicação com a API |
| Backend | Node.js, TypeScript e Apollo Server | Regras de negócio e processamento das requisições |
| Persistência | Prisma ORM e PostgreSQL | Acesso e armazenamento dos dados |

O uso de Docker é proposto para padronizar os ambientes e executar os serviços em contêineres.

### 2.1. Cliente web — Django

Na arquitetura proposta, o Django representa a camada de apresentação da aplicação.

É responsável por disponibilizar as páginas, receber as interações dos usuários e encaminhar as solicitações ao backend.

O Django deverá chamar a API interna por HTTP com operações GraphQL. Requests é a biblioteca proposta para o adaptador.

### 2.2. Backend — Node.js e TypeScript

O backend proposto centralizará o processamento das operações do sistema.

O Apollo Server disponibiliza a API GraphQL, enquanto os resolvers recebem as operações e encaminham o processamento para as respectivas regras de negócio.

Essa separação permite que a interface e a lógica de negócio evoluam de maneira independente.

### 2.3. Persistência — PostgreSQL

O PostgreSQL é responsável pelo armazenamento persistente das informações.

O Prisma ORM atua como camada de acesso ao banco de dados, permitindo que o backend consulte, insira, atualize e exclua registros.

O banco de dados não deve ser acessado diretamente pelo cliente web.

## 3. Comunicação entre os componentes

Hoje, o navegador envia formulários e consultas de status ao Django. As views chamam serviços Python no mesmo processo e acessam o SQLite via ORM. Na arquitetura distribuída proposta, o fluxo será o seguinte.

1. O usuário acessa o ByteBistro pelo navegador.
2. O Django disponibiliza a interface web.
3. Quando necessário, o Django realiza uma requisição HTTP para o backend.
4. O Apollo Server recebe a operação GraphQL.
5. Os resolvers encaminham a operação para a lógica correspondente.
6. O Prisma ORM executa as operações no PostgreSQL.
7. O backend retorna o resultado.
8. O Django apresenta a resposta ao usuário.

Essa organização mantém a persistência e as regras de negócio centralizadas no backend.

## 4. Fluxo de realização de pedidos

O processo de realização de um pedido representa um dos principais fluxos de negócio do ByteBistro.

### Fluxo atual

O Django mantém o carrinho em sessão, valida o destino e recalcula preços no servidor. O checkout grava o pedido e seu evento inicial na mesma transação SQLite. Reenvios autorizados com o mesmo token retornam o pedido existente. A equipe altera a etapa pelo painel e o navegador consulta o status periodicamente. [Serviço de checkout](../../client/shop/services.py) · [Acompanhamento](../../client/shop/views.py)

### Fluxo proposto

1. O cliente acessa o cardápio.
2. Visualiza as categorias e os produtos disponíveis.
3. Seleciona os produtos desejados.
4. Adiciona os itens ao carrinho.
5. Confirma o pedido.
6. A aplicação envia a solicitação ao backend.
7. O backend valida os dados recebidos.
8. O pedido é registrado no PostgreSQL.
9. Após a confirmação da persistência, tarefas complementares podem ser encaminhadas para processamento assíncrono.
10. Os workers executam essas tarefas.
11. O sistema pode distribuir notificações e atualizar informações do pedido.

O processamento assíncrono é uma evolução arquitetural proposta para evitar que operações secundárias aumentem o tempo de resposta das requisições principais.

## 5. Arquitetura de mensageria

A proposta utiliza Amazon SQS, Amazon SNS e workers independentes.

O SQS recebe tarefas que não precisam ser executadas durante a requisição principal.

Os workers consomem as mensagens e executam o processamento em segundo plano.

O SNS pode distribuir notificações para diferentes consumidores.

A Dead Letter Queue (DLQ) recebe mensagens que não conseguiram ser processadas após as tentativas configuradas.

Com Transactional Outbox, o backend grava o pedido e o evento na mesma transação PostgreSQL. Depois do commit, um publicador encaminha o evento ao SQS. Como uma entrega pode se repetir, o worker deve usar um identificador estável por evento e excluir a mensagem somente depois de concluir o processamento.

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

**GitHub Actions** — automação de testes, build e implantação.

## 7. Escalabilidade e disponibilidade

A arquitetura proposta prevê escalabilidade horizontal para permitir o crescimento da aplicação.

O Application Load Balancer distribui o tráfego entre as instâncias EC2 disponíveis.

O Auto Scaling Group pode adicionar ou remover instâncias de acordo com métricas e políticas configuradas.

A utilização de duas zonas de disponibilidade reduz a dependência de uma única zona.

O RDS Multi-AZ oferece uma configuração de banco de dados com alta disponibilidade.

As instâncias da aplicação devem ser tratadas como recursos substituíveis. Arquivos importantes, sessões compartilhadas e dados persistentes não devem depender exclusivamente do armazenamento local de uma EC2.

## 8. Segurança

O painel atual usa autenticação por sessão, grupos de acesso e proteção CSRF. Clientes acompanham apenas pedidos associados à própria sessão ou conta. [Rotas e controles](../../client/shop/staff_views.py)

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

Na proposta, o CloudWatch acompanhará os seguintes indicadores.

- CPU das instâncias e memória coletada por agente.
- Saúde das instâncias.
- Requisições e erros.
- Logs da aplicação.
- Métricas do RDS.
- Quantidade de mensagens nas filas.
- Falhas de processamento.
- Alarmes de infraestrutura.

## 10. Considerações finais

O ByteBistro já separa apresentação, lógica de negócio e persistência em módulos Django. A evolução proposta leva as regras de negócio para uma API interna e os dados do domínio para PostgreSQL.

A proposta de infraestrutura AWS amplia essa arquitetura com balanceamento de carga, escalabilidade horizontal, armazenamento gerenciado, mensageria e monitoramento.

O resultado esperado é uma aplicação preparada para evoluir de um ambiente de desenvolvimento para uma implantação mais robusta, segura e escalável.

**Estado de implementação.** O backend Node.js, o adaptador Requests, GraphQL, Prisma, PostgreSQL, Docker e os recursos AWS descritos neste documento são planejados.
