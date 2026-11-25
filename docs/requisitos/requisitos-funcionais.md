# Requisitos funcionais

O MVP cobre o fluxo de um estabelecimento, da configuração do cardápio ao acompanhamento de pedidos pelo cliente e pela equipe.

| Requisito | Escopo implementado |
| --- | --- |
| RF01 — Gestão do restaurante | A equipe autorizada gerencia nome, endereço, contato, horários, taxa de entrega, tempo estimado de preparo, formas de pagamento e disponibilidade de pedidos. |
| RF02 — Gestão do cardápio | O cardápio do estabelecimento reúne categorias ordenáveis. O cliente pode navegar por categoria e buscar produtos pelo nome, categoria ou descrição. |
| RF03 — Gestão de produtos | A equipe pode cadastrar, editar, arquivar e controlar a disponibilidade de produtos. Cada produto inclui categoria, descrição, preço, desconto, imagem, opções e adicionais. |
| RF04 — Carrinho | O cliente personaliza itens, altera quantidades e remove produtos. O servidor recalcula preços, adicionais, descontos e taxas. |
| RF05 — Checkout | O cliente confirma o pedido em uma mesa ativa ou informa um endereço de entrega após a verificação do telefone. Enviar o mesmo token novamente recupera o pedido existente quando o cliente tem acesso. |
| RF06 — Comunicação interna | Na configuração distribuída, o Django consulta o status na API Apollo (frota `api`) via ALB interno (`http://${api_alb_dns}:4000/graphql`) por HTTP/GraphQL com autenticação Bearer. A API também expõe `GET /healthz` sem autenticação para o Target Group. Checkout e operação continuam no Django. |
| RF07 — Persistência | O ORM Django mantém os dados no SQLite da demonstração e no PostgreSQL da configuração distribuída. O Prisma acessa `shop_order` (API e worker), `shop_orderoutbox` e `shop_orderevent` (`action = "notified"` no worker). |
| RF08 — Acompanhamento | A sessão ou conta que tem acesso ao pedido pode consultar seus itens e andamento. No fluxo local de delivery (`ConsoleProvider`), o código OTP é exibido no terminal; na configuração AWS (`SnsSmsProvider`), o SMS é enviado via AWS SNS. O histórico também registra `"Notificação enviada"` quando o worker publica no SNS. |
| RF09 — Operação do restaurante | O painel tem permissões por perfil, fila de pedidos, cozinha, mesas, estoque e relatórios. A equipe registra transições e confirma o recebimento de pagamentos. |

As formas de pagamento registram a preferência e o recebimento presencial ou na entrega. A verificação OTP por SMS em produção utiliza `SnsSmsProvider` via AWS SNS (`boto3` em `apps/web/requirements-aws.txt`, padrão em `config/aws_settings.py`). A cobrança eletrônica (gateway de pagamento online) permanece como evolução.

[Rotas](../../apps/web/config/urls.py) · [Formulários da equipe](../../apps/web/shop/staff_forms.py) · [Modelos](../../apps/web/shop/models.py) · [Arquitetura](../architecture/system-architecture.md)
