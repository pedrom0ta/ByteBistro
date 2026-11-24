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

- **Comunicação síncrona.** O Django consulta o status na API interna Apollo por HTTP/GraphQL. O PostgreSQL é compartilhado no desenho distribuído, com as escritas de negócio e migrações a cargo do Django.
- **Idempotência e concorrência.** A repetição de um checkout autorizado com o mesmo token preserva o pedido original. A consulta de status filtra pela sessão ou conta e o fluxo de operação valida a etapa anterior.
- **Processamento assíncrono.** A outbox é gravada na transação do pedido na configuração distribuída. O worker publica no SQS e encaminha notificações pelo SNS, com uma DLQ para falhas repetidas.
- **Escalabilidade e disponibilidade.** O Terraform descreve ALB, frotas web e worker, RDS Multi-AZ, CloudFront e monitoramento. A demonstração pública atual usa uma EC2 separada.

[System Design](../architecture/system-design.md) · [Decisões arquiteturais](../architecture/architecture-decisions.md) · [Estado da implantação](../deployment/status.md)

## Validação e limites

A suíte cobre o checkout, a operação do painel e o contrato da consulta de status. A integração Django–Apollo–PostgreSQL foi exercitada localmente. A validação distribuída na AWS depende da ativação das frotas e da homologação do processamento no SQS/SNS. SMS comercial e cobrança eletrônica permanecem como evolução do produto.

[Requisitos funcionais](../requisitos/requisitos-funcionais.md) · [Requisitos não funcionais](../requisitos/requisitos-nao-funcionais.md) · [CI/CD](../deployment/ci-cd.md)
