# Integração e entrega contínuas

O [workflow do GitHub Actions](../../.github/workflows/ci.yml) é configurado para pull requests e pushes para `main`. Ele verifica migrações e executa os testes Django, compila e testa os serviços TypeScript com o Prisma Client gerado e valida a sintaxe dos scripts e a integridade do ZIP de release.

O Terraform define o CodeBuild para publicar as imagens e seus digests no ECR. A migração usa o mesmo pacote de fontes. [Publicação e migração](../../infrastructure/terraform/README.md#publicação-e-migração)

Validar em homologação usando os mesmos digests previstos para a promoção. Executar migrações em etapa controlada, verificar saúde e testar vitrine, checkout e painel. Em caso de falha, interromper a promoção e avaliar o retorno à versão anterior conforme a compatibilidade do esquema.
