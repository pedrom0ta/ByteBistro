# Banco de dados

A demonstração usa SQLite e o ambiente AWS usa PostgreSQL. O Django define os [modelos](../../apps/web/shop/models.py) e aplica as [migrações](../../apps/web/shop/migrations/) em ambos os ambientes.

O [schema Prisma](../../apps/services/prisma/schema.prisma) mapeia as tabelas que a API consulta para obter o status dos pedidos e que o worker usa para processar os eventos de outbox. [Modelo relacional](README.md#banco-de-dados)
