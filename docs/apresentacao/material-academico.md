# Resumo da entrega acadêmica

- **Disciplina** Sistemas Distribuídos
- **Professor** Levi Costa
- **Equipe** Pedro Antonio, Tauan Gomes e Augusto Fagner

## Problema e objetivo

O ByteBistro reúne cardápio, checkout e operação do restaurante. O cliente pode enviar um pedido e acompanhar seu andamento. A equipe controla disponibilidade, preparo, entrega e registro de recebimentos em um painel.

[Domínio do projeto](../negocio/escolha-do-dominio.md) · [Proposta de valor](../negocio/proposta-de-valor.md)

## Entrega demonstrável

A apresentação percorre o fluxo **cardápio → carrinho → pedido na mesa → aceite → preparo → acompanhamento**. A demonstração usa Django e SQLite com dados iniciais incluídos nas migrações. O delivery também pode ser demonstrado localmente com código de verificação no terminal.

[Roteiro da apresentação](README.md) · [Execução local](../../apps/web/README.md)

## Conceitos de sistemas distribuídos

- **Comunicação síncrona.** Na configuração AWS, o Django consulta o status na frota desacoplada `api` (Apollo) por meio do ALB interno (`aws_lb.api`, porta `4000`, com `GET /healthz` para saúde dos alvos e `POST /graphql` com token Bearer). O PostgreSQL é compartilhado no desenho distribuído, mantendo as escritas de negócio e migrações no Django enquanto o worker registra `"notified"` em `shop_orderevent`.
- **Idempotência e concorrência.** A repetição de um checkout autorizado com o mesmo token preserva o pedido original. A consulta de status filtra pela sessão ou conta e o fluxo de operação valida a etapa anterior.
- **Processamento assíncrono.** A outbox é gravada na transação do pedido na configuração distribuída. O worker publica no SQS, lê `shop_order`, publica o evento enriquecido `order.created` no SNS (com assinatura opcional via `notification_email`) e grava `action = "notified"` em `shop_orderevent` na mesma transação em que marca `notifiedAt`, com uma DLQ para falhas repetidas.
- **Escalabilidade e disponibilidade.** O Terraform descreve entrada obrigatória com Route 53, ACM, CloudFront (`https-only`) e WAF ativo, ALB público (HTTPS `443`), ALB interno (HTTP `4000`), três frotas desacopladas em Auto Scaling (`web`, `api` e `worker`), RDS Multi-AZ e monitoramento no CloudWatch (incluindo alarmes `HealthyHostCount` para `web` e `api`).

[System Design](../architecture/system-design.md) · [Decisões arquiteturais](../architecture/architecture-decisions.md)

## Validação e limites

A suíte cobre o checkout, a operação do painel, o endpoint `GET /healthz` e `POST /graphql` da API, o enriquecimento SNS/`OrderEvent` no worker e testes com mock do cliente AWS SNS para `SnsSmsProvider`. A integração Django–Apollo–PostgreSQL foi exercitada localmente. A verificação OTP por SMS em produção está implementada via AWS SNS (`SnsSmsProvider` com `boto3` em `apps/web/config/aws_settings.py`); a cobrança eletrônica (gateway de pagamento) permanece como evolução do produto.

[Requisitos funcionais](../requisitos/requisitos-funcionais.md) · [Requisitos não funcionais](../requisitos/requisitos-nao-funcionais.md) · [CI/CD](../deployment/ci-cd.md)
