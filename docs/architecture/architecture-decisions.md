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
| Status | Proposta |
| Contexto | O domínio atualmente roda no Django. |
| Problema | Estabelecer uma API de domínio consumida pela interface. |
| Decisão | Usar monólito modular Node.js com tipos TypeScript, schema Apollo e resolvers que delegam aos serviços. |
| Alternativas consideradas | Continuar com Django para o domínio ou expor API REST. |
| Consequências positivas | Contrato tipado e responsabilidades explícitas. |
| Consequências negativas | Novo runtime, curva operacional e migração de regras e testes. |

## ADR-003 — Comunicação interna Django–Apollo

| Campo | Registro |
| --- | --- |
| Status | Proposta |
| Contexto | O navegador atende fluxos protegidos por sessão e CSRF. |
| Problema | Preservar a interface e restringir o acesso ao domínio. |
| Decisão | Django chama Apollo por HTTP/GraphQL na rede interna do host, com identidade contextual, limites e timeouts. |
| Alternativas consideradas | Apollo público, frotas separadas ou chamadas locais no monólito. |
| Consequências positivas | API interna e uma borda web. |
| Consequências negativas | Web e API escalam juntas inicialmente; falhas precisam de tratamento explícito. |

## ADR-004 — Prisma e PostgreSQL

| Campo | Registro |
| --- | --- |
| Status | Proposta |
| Contexto | SQLite é local e o Django possui o esquema atual. |
| Problema | Compartilhar estado entre réplicas e recuperar falhas de banco. |
| Decisão | Prisma gere o domínio em um PostgreSQL compartilhado. Se necessário, Django mantém esquema separado para sessões e identidade. |
| Alternativas consideradas | Manter SQLite ou usar o ORM Django com PostgreSQL. |
| Consequências positivas | Persistência compartilhada e transações. |
| Consequências negativas | Custo contínuo, migração de dados e necessidade de controlar conexões. |

## ADR-005 — Docker

| Campo | Registro |
| --- | --- |
| Status | Proposta |
| Contexto | Os ambientes precisam ser reproduzíveis. |
| Problema | Distribuir todos os processos de forma consistente para hosts substituíveis. |
| Decisão | Empacotar processos em imagens Docker e implantar imagens identificadas por digest. |
| Alternativas consideradas | Instalação por scripts no host ou imagens de máquina com aplicação embutida. |
| Consequências positivas | Releases rastreáveis e rollback de imagem. |
| Consequências negativas | Manutenção de imagens e bootstrap dependente de rede, disco e credenciais do registro. |

## ADR-007 — Mensageria com outbox e fila de falhas

| Campo | Registro |
| --- | --- |
| Status | Proposta |
| Contexto | Pedido confirmado deve sobreviver a indisponibilidade de integrações. |
| Problema | Publicar eventos após commit e distribuir notificações fora do checkout. |
| Decisão | Gravar outbox em transação, publicar em uma fila e notificar por consumidores idempotentes, com fila de falhas. |
| Alternativas consideradas | Publicação síncrona, fila FIFO ou apenas polling do banco. |
| Consequências positivas | Isolamento de falhas e reprocessamento controlado. |
| Consequências negativas | Consistência eventual, duplicatas possíveis e necessidade de operar a DLQ. |

## Decisões em aberto

Definir capacidade, retenção e objetivos de recuperação. Fechar identidade entre serviços, cache compartilhado, plano de migração, política de notificação e exigência de ordem por pedido. Validar isolamento de credenciais entre contêineres.
