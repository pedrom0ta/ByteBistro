# Cliente web ByteBistro

O Django renderiza o cardápio em português e mantém o carrinho na sessão do navegador. O modo demonstrativo funciona em um único processo local. Catálogo, preços, desconto promocional e taxa de entrega são exemplos. Os pedidos, endereços e alterações de status feitos durante o uso ficam gravados no SQLite do cliente.

## Primeira execução

Use Python 3.11 ou 3.12 com pip. A partir da pasta `apps/web`, no PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

Abra [o site local](http://127.0.0.1:8000/). Em Linux/macOS, use `.venv/bin/python` no lugar do executável em `Scripts`. O Django é a dependência da aplicação. As imagens, CSS, ícones e JavaScript são servidos localmente.

## Experimentar os fluxos

### Painel do restaurante

Após migrar o banco, crie a primeira conta de administrador a partir de `apps/web`. O Django solicitará as credenciais no terminal.

```powershell
.\.venv\Scripts\python manage.py createsuperuser
```

Entre em [Painel ByteBistro](http://127.0.0.1:8000/painel/). Use a porta do servidor se ela for diferente. A seção **Funcionários** permite ao administrador cadastrar perfis e controlar o acesso. Gerentes administram a operação, atendentes operam pedidos e consultam mesas, e a cozinha acessa a fila de preparo. O login da equipe usa credenciais próprias.

Em outra janela, faça um pedido pelo site público. A central consulta novos pedidos a cada quatro segundos. Aceite-o ou recuse-o com um motivo. Pedidos aceitos entram na cozinha. Marque como pronto e conclua na mesa, ou registre a saída e a entrega no delivery. O cliente vê o andamento pelo próprio acompanhamento. Para contabilizar o valor recebido, registre o recebimento confirmado nos detalhes do pedido concluído.

As migrações importam os seis produtos e mesas iniciais. O painel usa os mesmos registros SQLite do site. A imagem de produto aceita arquivo já presente em `static/images/` ou URL HTTPS. A equipe cadastra horários e previsão de preparo e usa **Configurações** para abrir ou fechar pedidos.

Os módulos ficam em `shop/staff_views.py`, `shop/staff_forms.py`, `shop/operations.py` e `shop/storefront.py`. A interface usa `templates/staff/`, `static/css/operations.css` e `static/js/operations.js`. O histórico de etapas e as movimentações de estoque registram responsável e horário. Atualizações antigas anteriores ao painel preservam a etapa existente. As migrações registram a data de recebimento desses pedidos, pois o banco anterior guardava apenas a etapa atual.

O painel grava permissões, transições e mudanças de catálogo no Django. A tela do cliente consulta o status periodicamente. A equipe registra movimentações de estoque e confirma recebimentos no painel.

### Site do cliente

1. Na página inicial, abra a oferta ou o cardápio. A busca aceita termos sem acento, e as categorias filtram os resultados. Abra um produto, personalize e ajuste a quantidade. Os adicionais e o desconto entram no total apresentado.
2. No carrinho, edite quantidades ou remova itens. Em **Continuar pedido**, escolha a modalidade.
3. Para comer no restaurante, selecione uma das seis mesas e confirme. O pedido aparece no histórico dessa sessão.
4. Para delivery, use um número de celular brasileiro fictício com DDD. No terminal que executa o Django, procure a mensagem **SMS local** com o código de seis dígitos. O código vale cinco minutos. Um novo número passa pelo cadastro rápido. Um número já cadastrado retorna ao checkout com seus endereços. O carrinho acompanha ambas as rotas.
5. Selecione ou cadastre o endereço e escolha o pagamento na entrega. A taxa demonstrativa é R$ 6,90. Pix, cartão e dinheiro registram a preferência do cliente. A cobrança é realizada na entrega.
6. Abra **Pedidos** para rever os itens, os valores e a etapa registrada. Em **Conta**, consulte endereços, pagamentos e ajuda ou encerre a sessão.

### Atualizar o andamento

Em um segundo terminal, na pasta `apps/web`, use o número exibido no acompanhamento:

```powershell
.\.venv\Scripts\python manage.py avancar_pedido NUMERO_DO_PEDIDO
```

Cada execução registra uma única mudança de etapa. A tela consulta o estado a cada cinco segundos e tenta novamente após uma falha de conexão. Para restaurante, a conclusão aparece quando o pedido fica pronto. Para delivery, aparece quando é entregue. O botão **Ver detalhes** abre o registro completo.

### Validação

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test shop
```

Os testes usam um banco temporário. Cobrem restaurante, delivery com cadastro e cliente existente, busca, categorias, opções, quantidades, disponibilidade, desconto, endereço, controle de acesso, OTP, confirmação repetida e conclusão.

## Estrutura

| Caminho | Responsabilidade |
| --- | --- |
| `manage.py`, `config/` | Inicialização, configuração Django e rotas |
| `shop/views.py`, `forms.py` | Navegação, formulários e validação do checkout |
| `shop/catalog.py` | Catálogo de seis categorias, opções e adicionais |
| `shop/services.py` | Carrinho, preços em centavos, histórico e confirmação |
| `shop/models.py`, `migrations/` | Persistência demonstrativa de clientes e pedidos |
| `shop/sms.py` | Emissão, verificação, limites e provedores de SMS (`ConsoleProvider` local e `SnsSmsProvider` via AWS SNS) |
| `shop/management/commands/` | Avanço manual da etapa do pedido |
| `templates/`, `templates/components/` | Telas, navegação, cards e resumos reutilizáveis |
| `static/` | Fotografias, marca, estilos e comportamento do navegador |
| `shop/tests.py`, `shop/test_operations.py` | Testes de checkout, acompanhamento e operação do restaurante |

## Recursos visuais

A marca ByteBistro foi recortada do cabeçalho da referência fornecida. As fotografias do catálogo estão em `static/images/` e têm as seguintes fontes:

- [Hambúrguer](https://images.unsplash.com/photo-1568901346375-23c9450c58cd)
- [Pizza](https://images.unsplash.com/photo-1579751626657-72bc17010498)
- [Massa](https://images.unsplash.com/photo-1473093295043-cdd812d0e601)
- [Suco](https://images.unsplash.com/photo-1613478223719-2ab802602423)
- [Batatas](https://images.unsplash.com/photo-1573080496219-bb080dd4f877)
- [Brownie](https://images.unsplash.com/photo-1606313564200-e75d5e30476c)

## Integração com a API de status

Com `BYTEBISTRO_GRAPHQL_URL` configurada (apontando na AWS para o ALB interno em `http://${api_alb_dns}:4000/graphql`), o Django consulta o status na API GraphQL em [`apps/services/`](../services/README.md). O adaptador usa `GRAPHQL_SERVICE_TOKEN`, identidade da sessão e timeout. O checkout e as operações do painel gravam pelo ORM Django. Com `BYTEBISTRO_OUTBOX_ENABLED=1`, o checkout grava a outbox na mesma transação, e o worker registra `action = "notified"` (`"Notificação enviada"` em `OrderEvent.label`) em `shop_orderevent` ao publicar no SNS.

O provedor de demonstração (`ConsoleProvider`, padrão em `config/settings.py`) exige `DEBUG=True` e exibe o código de verificação no console. Na configuração AWS (`config/aws_settings.py`, com `boto3>=1.34,<2`, `gunicorn` e `psycopg` declarados em `requirements-aws.txt`), `SMS_PROVIDER` usa por padrão `shop.sms.SnsSmsProvider`, que normaliza números brasileiros para E.164 com `SMS_COUNTRY_CODE` (padrão `+55`) e envia SMS `Transactional` via AWS SNS usando a permissão `sns:Publish` da role da frota `web`. Ambos os provedores implementam `issue(phone) -> challenge` e `verify(challenge, code) -> bool`, usando cache compartilhado no PostgreSQL na configuração distribuída.

O banco `demo.sqlite3` e a chave `.local.key` são dados locais da demonstração. Use dados fictícios.
