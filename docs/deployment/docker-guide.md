# Estratégia Docker

O ambiente atual usa Python, Django e SQLite, conforme o [guia local](../../client/README.md). O empacotamento abaixo é proposto.

| Ambiente | Processos e dependências |
| --- | --- |
| Desenvolvimento após integração | Compose orquestra Django, Apollo, PostgreSQL e, quando implementado, publicador e worker. Persistir dados locais em volume de desenvolvimento e usar dependências de teste para mensageria. |
| Homologação e produção | Executar Django e Apollo como processos separados. Publicador e consumidor serão processos independentes, com PostgreSQL e mensageria como dependências. |

Construir imagens com dependências fixadas, estágios de build quando úteis e usuário sem privilégios. Receber variáveis em execução, carregar segredos em execução, escrever logs em stdout e usar health checks. Configurar reinício de processos e desligamento gracioso. Publicar imagens versionadas e identificar cada release por digest. Rodar migrações em executor controlado, antes da troca da frota e conforme a compatibilidade do esquema.

[Build e imagens Docker](https://docs.docker.com/build/building/best-practices/) · [Docker Compose](https://docs.docker.com/compose/)
