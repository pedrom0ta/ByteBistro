# Cliente web ByteBistro

O Django renderiza o cardápio em português e mantém o carrinho na sessão do navegador. O modo demonstrativo funciona em um único processo local. Catálogo, preços, desconto promocional e taxa de entrega são exemplos. Os pedidos, endereços e alterações de status feitos durante o uso ficam gravados no SQLite do cliente.

## Primeira execução

Use Python 3.11 ou 3.12 com pip. A partir da pasta `client`, no PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

Abra [o site local](http://127.0.0.1:8000/). Em Linux/macOS, use `.venv/bin/python` no lugar do executável em `Scripts`. O Django é a dependência da aplicação. As imagens, CSS, ícones e JavaScript são servidos localmente.

## Experimentar os fluxos

### Painel do restaurante

Após migrar o banco, crie a primeira conta de administrador a partir de `client`. O Django solicitará as credenciais no terminal.

```powershell
.\.venv\Scripts\python manage.py createsuperuser
```

Entre em [Painel ByteBistro](http://127.0.0.1:8000/painel/). Use a porta do servidor se ela for diferente. A seção **Funcionários** permite ao administrador cadastrar perfis e controlar o acesso. Gerentes administram a operação, atendentes operam pedidos e consultam mesas, e a cozinha acessa a fila de preparo. O login da equipe usa credenciais próprias.

Em outra janela, faça um pedido pelo site público. A central consulta novos pedidos a cada quatro segundos. Aceite-o ou recuse-o com um motivo. Pedidos aceitos entram na cozinha. Marque como pronto e conclua na mesa, ou registre a saída e a entrega no delivery. O cliente vê o andamento pelo próprio acompanhamento. Para contabilizar o valor recebido, registre o recebimento confirmado nos detalhes do pedido concluído.

As migrações importam os seis produtos e mesas iniciais. O painel usa os mesmos registros SQLite do site. A imagem de produto aceita arquivo já presente em `static/images/` ou URL HTTPS. O cadastro de mesas inclui uma chave estável reservada para o futuro QR Code. Horários e previsão de preparo são informações cadastradas. Para abrir ou fechar pedidos, use o controle explícito em **Configurações**.

Os módulos ficam em `shop/staff_views.py`, `shop/staff_forms.py`, `shop/operations.py` e `shop/storefront.py`. A interface usa `templates/staff/`, `static/css/operations.css` e `static/js/operations.js`. O histórico de etapas e as movimentações de estoque registram responsável e horário. Atualizações antigas anteriores ao painel preservam a etapa existente. As migrações registram a data de recebimento desses pedidos, pois o banco anterior guardava apenas a etapa atual.

Na integração futura, o backend GraphQL deverá assumir permissões, transições, eventos e gestão de catálogo. A consulta periódica pode ser substituída por eventos ou subscriptions. Pagamento eletrônico e estorno dependem do provedor. O estoque é movimentado manualmente até existir vínculo entre receitas e insumos.

### Site do cliente

1. Na página inicial, abra a oferta ou o cardápio. A busca aceita termos sem acento, e as categorias filtram os resultados. Abra um produto, personalize e ajuste a quantidade. Os adicionais e o desconto entram no total apresentado.
2. No carrinho, edite quantidades ou remova itens. Em **Continuar pedido**, escolha a modalidade.
3. Para comer no restaurante, selecione uma das seis mesas e confirme. O pedido aparece no histórico dessa sessão.
4. Para delivery, use um número de celular brasileiro fictício com DDD. No terminal que executa o Django, procure a mensagem **SMS local** com o código de seis dígitos. O código vale cinco minutos. Um novo número passa pelo cadastro rápido. Um número já cadastrado retorna ao checkout com seus endereços. O carrinho acompanha ambas as rotas.
5. Selecione ou cadastre o endereço e escolha o pagamento na entrega. A taxa demonstrativa é R$ 6,90. Pix, cartão e dinheiro registram a preferência do cliente. A cobrança é realizada na entrega.
6. Abra **Pedidos** para rever os itens, os valores e a etapa registrada. Em **Conta**, consulte endereços, pagamentos e ajuda ou encerre a sessão.

### Atualizar o andamento

Em um segundo terminal, na pasta `client`, use o número exibido no acompanhamento:

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
| `shop/sms.py` | Emissão, verificação, limites e provedor de desenvolvimento |
| `shop/management/commands/` | Avanço manual da etapa do pedido |
| `templates/`, `templates/components/` | Telas, navegação, cards e resumos reutilizáveis |
| `static/` | Fotografias, marca, estilos e comportamento do navegador |
| `shop/tests.py` | Testes automatizados dos fluxos |

## Recursos visuais

A marca ByteBistro foi recortada do cabeçalho da referência fornecida. As fotografias do catálogo estão em `static/images/` e têm as seguintes fontes:

- [Hambúrguer](https://images.unsplash.com/photo-1568901346375-23c9450c58cd)
- [Pizza](https://images.unsplash.com/photo-1579751626657-72bc17010498)
- [Massa](https://images.unsplash.com/photo-1473093295043-cdd812d0e601)
- [Suco](https://images.unsplash.com/photo-1613478223719-2ab802602423)
- [Batatas](https://images.unsplash.com/photo-1573080496219-bb080dd4f877)
- [Brownie](https://images.unsplash.com/photo-1606313564200-e75d5e30476c)

## Integração futura

O repositório original define o contrato arquitetural Django → HTTP/GraphQL → Node.js/Apollo → Prisma → PostgreSQL. O checkout inicial continha documentação de planejamento em `backend/`, `client/` e `database/`. A implementação Django ocupa a pasta já reservada ao cliente.

Quando o esquema Apollo estiver disponível:

1. Implemente o adaptador HTTP em `shop/` e leia o endpoint e as credenciais de variáveis de ambiente do processo Django. Use HTTPS, timeout e tratamento de erros de transporte e do campo GraphQL `errors`.
2. Substitua as operações locais de catálogo, perfil/endereço, histórico, cotação e criação de pedido pelas queries e mutations do esquema publicado. Mantenha a representação de valores em centavos na interface e valide a conversão no adaptador. O backend deve recalcular preço, desconto, taxa e disponibilidade.
3. Encaminhe a chave única do checkout para a mutation de criação. O serviço que grava o pedido deve impor unicidade e devolver o mesmo pedido em uma repetição autorizada. Propague a identidade verificada no servidor e confira o proprietário nas consultas de histórico e status.
4. Configure `SMS_PROVIDER` com o caminho Python de uma classe que implemente `issue(phone) -> challenge` e `verify(challenge, code) -> bool`. O provedor de produção deve emitir e verificar o SMS no serviço real. O provedor de console exige modo de desenvolvimento. Use cache compartilhado para limites, expiração e uso único em múltiplas instâncias.
5. Substitua a consulta local de status por uma query do backend. O endpoint JSON consumido pela Fetch API também pode evoluir para eventos ou subscriptions.

O banco `demo.sqlite3`, a chave local `.local.key` e as sessões pertencem à demonstração. Use apenas dados fictícios. Para execução fora do desenvolvimento, configure `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, hosts e cookies seguros, um serviço de identidade e armazenamento compartilhado. Integrações com SMS comercial, pagamentos e API distribuída ficam para a etapa seguinte.
