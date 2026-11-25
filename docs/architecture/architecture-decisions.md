# Registros de decisões arquiteturais

**Proposta** aguarda validação. **Aceita** indica aprovação registrada. **Implementada** indica evidência no código. **Substituída** aponta para um registro posterior. As alternativas abaixo registram opções avaliadas para esta documentação.

## ADR-001 — Django como interface web

| Campo | Registro |
| --- | --- |
| Status | Implementada |
| Contexto | O checkout já usa Django para vitrine e painel. |
| Problema | Entregar a experiência do restaurante no navegador. |
| Decisão | Manter Django e templates renderizados no servidor. |
| Alternativas consideradas | Cliente desktop ou front-end SPA. |
| Consequências positivas | Interface e autenticação local integradas. |
| Consequências negativas | O desenho distribuído exige separar o domínio e compartilhar sessões. |

## ADR-002 — Node.js, TypeScript e Apollo GraphQL

| Campo | Registro |
| --- | --- |
| Status | Implementada para a consulta de status |
| Contexto | As escritas de negócio rodam no Django. |
| Problema | Disponibilizar uma consulta tipada de status para a aplicação web. |
| Decisão | Usar Node.js, TypeScript e Apollo Server para expor `orderStatus`. A migração das escritas de domínio é uma proposta separada. |
| Alternativas consideradas | Continuar com Django para o domínio ou expor API REST. |
| Consequências positivas | Contrato tipado e responsabilidades explícitas. |
| Consequências negativas | Novo runtime, curva operacional e migração de regras e testes. |

## ADR-003 — Comunicação interna Django–Apollo

| Campo | Registro |
| --- | --- |
| Status | Implementada no código e definida com ALB interno no Terraform |
| Contexto | O navegador atende fluxos protegidos por sessão e CSRF. |
| Problema | Preservar a interface e restringir o acesso ao domínio. |
| Decisão | Django chama Apollo por HTTP/GraphQL com token de serviço, identidade da sessão e timeout. Na AWS, as frotas executam em ASGs separados (`web` e `api`) e a chamada passa pelo ALB interno (`aws_lb.api`, porta `4000`, health check `GET /healthz`). |
| Alternativas consideradas | Apollo público, co-locação de Django e Apollo no mesmo host EC2 ou chamadas locais no monólito. |
| Consequências positivas | API interna isolada atrás do ALB interno, uma única borda web pública e escala independente entre `web` e `api`. |
| Consequências negativas | Salto adicional de rede via ALB interno e necessidade de health check dedicado (`GET /healthz`), timeout e tratamento explícito de indisponibilidade (`503`). |

## ADR-004 — Prisma e PostgreSQL

| Campo | Registro |
| --- | --- |
| Status | Implementada para a configuração distribuída |
| Contexto | SQLite é local e o Django possui o esquema atual. |
| Problema | Compartilhar estado entre réplicas e recuperar falhas de banco. |
| Decisão | Django gerencia o esquema do PostgreSQL compartilhado. Prisma lê `shop_order` na API (status) e no worker (metadados da notificação), processa a `shop_orderoutbox` e registra `action = "notified"` em `shop_orderevent`. |
| Alternativas consideradas | Manter SQLite ou usar o ORM Django com PostgreSQL. |
| Consequências positivas | Persistência compartilhada e transações. |
| Consequências negativas | Custo contínuo, migração de dados e necessidade de controlar conexões. |

## ADR-005 — Docker

| Campo | Registro |
| --- | --- |
| Status | Implementada no empacotamento do release |
| Contexto | Os ambientes precisam ser reproduzíveis. |
| Problema | Distribuir todos os processos de forma consistente para hosts substituíveis. |
| Decisão | Empacotar processos em imagens Docker e implantar imagens identificadas por digest. |
| Alternativas consideradas | Instalação por scripts no host ou imagens de máquina com aplicação embutida. |
| Consequências positivas | Releases rastreáveis e rollback de imagem. |
| Consequências negativas | Manutenção de imagens e bootstrap dependente de rede, disco e credenciais do registro. |

## ADR-007 — Mensageria com outbox e fila de falhas

| Campo | Registro |
| --- | --- |
| Status | Implementada no código e no Terraform |
| Contexto | Pedido confirmado deve sobreviver a indisponibilidade de integrações. |
| Problema | Publicar eventos após commit e distribuir notificações fora do checkout. |
| Decisão | O Django grava a outbox na transação do pedido. O worker publica e consome no SQS, enriquece o evento `order.created`, publica no SNS (com assinatura opcional via `notification_email`) e registra `"notified"` em `shop_orderevent` na mesma transação que marca `notifiedAt`. O SQS envia falhas repetidas para uma DLQ. |
| Alternativas consideradas | Publicação síncrona, fila FIFO ou apenas polling do banco. |
| Consequências positivas | Isolamento de falhas e reprocessamento controlado. |
| Consequências negativas | Consistência eventual, duplicatas possíveis e necessidade de operar a DLQ. |

## ADR-008 — Borda pública HTTPS obrigatória e WAF ativo

| Campo | Registro |
| --- | --- |
| Status | Implementada no Terraform |
| Contexto | A entrada pública precisa de domínio gerenciado, TLS de ponta a ponta e proteção ativa contra requisições maliciosas. |
| Problema | Evitar exposição HTTP sem domínio próprio ou WAF apenas em modo passivo. |
| Decisão | Exigir `domain` e `hosted_zone_id` (Route 53 e certificados ACM em `us-east-1` e na região), CloudFront com `origin_protocol_policy = "https-only"` para o ALB público na porta `443` (com `X-ByteBistro-Origin`) e AWS WAFv2 com `AWSManagedRulesCommonRuleSet` em modo de bloqueio por padrão (`waf_enforce = true`) e limite por IP. |
| Alternativas consideradas | Modo HTTP padrão pelo domínio CloudFront ou WAF permanente em modo `count`. |
| Consequências positivas | TLS obrigatório de ponta a ponta, validação DNS automatizada e proteção ativa na borda. |
| Consequências negativas | Exige zona pública delegada no Route 53 antes do provisionamento base. |

## ADR-009 — Verificação de telefone por SMS via AWS SNS

| Campo | Registro |
| --- | --- |
| Status | Implementada em `apps/web` e no Terraform |
| Contexto | O checkout de delivery exige verificação OTP por telefone, e `ConsoleProvider` falha com `DEBUG = False`. |
| Problema | Viabilizar envio real de SMS transacional em produção sem quebrar o fluxo local de demonstração. |
| Decisão | Manter `ConsoleProvider` em `config/settings.py` para desenvolvimento local e configurar `SnsSmsProvider` (`boto3` com AWS SNS `Transactional`, normalização E.164 com `SMS_COUNTRY_CODE = "+55"`) como padrão em `config/aws_settings.py`, com permissão `sns:Publish` na role IAM da frota `web`. |
| Alternativas consideradas | Manter apenas provedor de console ou contratar gateway de SMS externo fora da AWS. |
| Consequências positivas | Entrega nativa via AWS SNS sem credenciais adicionais além da role IAM da frota `web`. |
| Consequências negativas | Depende de limites de envio e verificação da conta AWS SNS para entrega real em produção. |

## Decisões em aberto

Validar capacidade e objetivos de recuperação, política de retenção/notificação e exigência de ordem por pedido. Homologar a mensageria SQS/SNS e o envio real de SMS/e-mail em ambiente ativo, além de verificar a restauração de backup.
