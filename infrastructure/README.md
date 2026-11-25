# Infraestrutura

Para executar a demonstração, consulte o [guia local](../apps/web/README.md). O [guia Docker](../docs/deployment/docker-guide.md) descreve as imagens do Django, da API e do worker.

A infraestrutura AWS está definida em [Terraform](terraform/README.md). Os scripts em [`release/`](release/) empacotam o código, publicam imagens e arquivos estáticos e executam as migrações.
