# Requisitos não funcionais

| Requisito | Implementação e validação |
| --- | --- |
| RNF01 — Comunicação | A consulta interna de status usa HTTP/GraphQL. O adaptador limita o tempo de espera e trata erros de transporte e de resposta. |
| RNF02 — Serviços | A API de status e o worker são escritos em TypeScript e executados em Node.js. A API usa Apollo Server. |
| RNF03 — Interface web | Django renderiza os templates HTML e entrega a vitrine e o painel, com CSS e JavaScript. |
| RNF04 — Persistência | A demonstração usa SQLite. A configuração distribuída usa PostgreSQL via Django e Prisma, com migrações gerenciadas pelo Django. |
| RNF05 — Hospedagem | A demonstração pública está na EC2. O ambiente com CloudFront, ALB e frotas é definido em Terraform e aguarda ativação. |
| RNF06 — Organização | A aplicação web, os serviços distribuídos, a infraestrutura e a documentação têm diretórios próprios. |
| RNF07 — Versionamento e verificação | O código é versionado no GitHub. O workflow foi configurado para pull requests e pushes para a `main`, com verificações de Django, Node e empacotamento. |
| RNF08 — Segurança | A aplicação usa sessões, permissões do painel, proteção CSRF e acesso ao pedido pela própria sessão ou conta. A configuração distribuída prevê rede segmentada, IAM, Secrets Manager e TLS no banco. |
| RNF09 — Escalabilidade | O Terraform define ALB, frotas web e worker separadas e RDS Multi-AZ. A capacidade sob carga permanece por medir. |
| RNF10 — Resiliência | Checkout idempotente, outbox transacional e retentativas são contemplados na implementação. O Terraform declara DLQ, alarmes e backup do RDS. A homologação da mensageria e o teste de restauração permanecem em aberto. |

Os objetivos de latência, throughput e recuperação ainda aguardam definição e testes.

[System Design](../architecture/system-design.md) · [Estado da implantação](../deployment/status.md) · [CI/CD](../deployment/ci-cd.md)
