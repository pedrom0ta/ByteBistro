# Requisitos não funcionais

| Requisito | Implementação e validação |
| --- | --- |
| RNF01 — Comunicação | A consulta interna de status usa HTTP/GraphQL; na AWS, o Django acessa a frota `api` pelo ALB interno (`aws_lb.api`, porta `4000`), onde a API expõe `GET /healthz` (`200`) sem autenticação e `POST /graphql` autenticado. O adaptador limita o tempo de espera e trata erros de transporte e de resposta. |
| RNF02 — Serviços | A API de status e o worker são escritos em TypeScript e executados em Node.js. A API usa Apollo Server. |
| RNF03 — Interface web | Django renderiza os templates HTML e entrega a vitrine e o painel, com CSS e JavaScript. |
| RNF04 — Persistência | A demonstração usa SQLite. A configuração distribuída usa PostgreSQL via Django e Prisma, com migrações gerenciadas pelo Django. |
| RNF05 — Hospedagem | A demonstração pública está na EC2. O ambiente com Route 53, ACM, CloudFront (`https-only`), WAF ativo, ALB público, ALB interno e três frotas em Auto Scaling (`web`, `api`, `worker`) é definido em Terraform (com AMI AL2023 via SSM e segredos automáticos) e aguarda ativação. |
| RNF06 — Organização | A aplicação web, os serviços distribuídos, a infraestrutura e a documentação têm diretórios próprios. |
| RNF07 — Versionamento e verificação | O código é versionado no GitHub. O workflow foi configurado para pull requests e pushes para a `main`, com verificações de Django, Node e empacotamento. |
| RNF08 — Segurança | A aplicação usa sessões, permissões do painel, proteção CSRF e acesso ao pedido pela própria sessão ou conta. A configuração distribuída impõe HTTPS obrigatório de ponta a ponta (Route 53, ACM, CloudFront `redirect-to-https` / `https-only` até o ALB público na porta `443` com `X-ByteBistro-Origin`), AWS WAFv2 com bloqueio ativo por padrão (`waf_enforce = true`), isolamento da `api` atrás do ALB interno em sub-redes privadas, roles IAM dedicadas por frota (`sns:Publish` em `web`, KMS + SQS/SNS em `worker`), Secrets Manager e TLS no banco. |
| RNF09 — Escalabilidade | O Terraform define ALB público, ALB interno, três frotas separadas em Auto Scaling (`web`, `api` e `worker`, mínimo de 2 instâncias cada) e RDS Multi-AZ. A capacidade sob carga permanece por medir. |
| RNF10 — Resiliência | Checkout idempotente, outbox transacional e retentativas são contemplados na implementação. O Terraform declara DLQ, alarmes CloudWatch (incluindo `HealthyHostCount` para os Target Groups `web` e `api`), assinatura opcional de notificações (`notification_email` em `aws_sns_topic_subscription.notifications`) e backup do RDS. A homologação da mensageria e o teste de restauração permanecem em aberto. |

Os objetivos de latência, throughput e recuperação ainda aguardam definição e testes.

[System Design](../architecture/system-design.md) · [CI/CD](../deployment/ci-cd.md)
