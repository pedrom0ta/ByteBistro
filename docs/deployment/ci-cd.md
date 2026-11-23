# Integração e entrega contínuas

O pipeline GitHub Actions é uma proposta. Em pull requests, executar os testes Django e validar a documentação. Quando o backend estiver implementado, acrescentar lint e testes de integração com PostgreSQL. Em releases, construir, verificar e publicar as imagens com identificação por commit e digest.

Validar em homologação usando os mesmos digests previstos para a promoção. Executar migrações em etapa controlada, verificar saúde e testar vitrine, checkout e painel. Em caso de falha, interromper a promoção e avaliar o retorno à versão anterior conforme a compatibilidade do esquema.
