# Estado da implantação

Verificação da demonstração em 24 de novembro de 2026 e última consulta à infraestrutura AWS em 23 de novembro de 2026, no horário de Brasília.

| Ambiente ou etapa | Estado observado |
| --- | --- |
| Demonstração pública | A instância EC2 `bytebistro-demo` usa Nginx e responde por HTTPS. A vitrine e o cardápio retornaram HTTP 200, e o painel encaminhou para a tela de login. A rota de status ainda respondeu com o formato anterior ao release atual. [Vitrine pública](https://54.209.48.237/) |
| Artefatos do release | `release-15ebb80ce5e4cda4` tem as imagens web, API e worker no ECR. O ZIP, o manifesto de digests e os estáticos foram publicados no S3. O build foi feito com Docker local após o CodeBuild recusar a execução por cota zero. [Guia de publicação](../../infrastructure/terraform/README.md#publicação-e-migração) |
| Entrada distribuída | A AWS rejeitou a criação do CloudFront com HTTP 403 e exigiu verificação da conta. A última consulta ao ambiente encontrou o balanceador sem alvos registrados e as frotas ainda por ativar. O plano do release prevê nove criações, sem alterar ou excluir recursos existentes. |
| Revisão do código | A demonstração local usa Django e SQLite. Apollo e PostgreSQL foram exercitados em um ambiente local isolado para validar checkout, acompanhamento, reenvio e pedidos concorrentes. O processamento de mensagens pelo worker com SQS/SNS reais permanece por homologar. [Arquitetura](../architecture/system-architecture.md) |

O endereço da EC2 serve para apresentar a vitrine. Para reproduzir os fluxos e as verificações desta revisão, execute a aplicação do repositório localmente. [Instruções de execução](../../apps/web/README.md)
