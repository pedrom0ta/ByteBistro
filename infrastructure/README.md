# Infraestrutura

Para executar a demonstração, consulte o [guia local](../apps/web/README.md). O [guia Docker](../docs/deployment/docker-guide.md) descreve as imagens do Django, da API e do worker.

A infraestrutura AWS está definida em [Terraform](terraform/README.md). Os scripts em [`release/`](release/) empacotam o código, publicam imagens e arquivos estáticos e executam as migrações.

O [estado da implantação](../docs/deployment/status.md) registra a demonstração pública e o rollout distribuído. O [atualizador da demonstração](release/update-demo.py) atende a EC2 nativa com Django e SQLite.
