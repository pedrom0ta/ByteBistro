import uuid
from time import sleep
from django.conf import settings
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models import Q
from .models import Customer, Order, OrderEvent, OrderOutbox
from .stock import reserve_stock
from . import storefront

DELIVERY_FEE = 690
PAYMENTS = ["Pix", "Cartão de crédito", "Cartão de débito", "Dinheiro"]

def owner(session):
    return session.setdefault("owner", uuid.uuid4().hex)

def customer(session):
    return Customer.objects.filter(pk=session.get("customer")).first()

def orders(session):
    access = Q(owner=owner(session))
    if session.get("customer"):
        access |= Q(customer_id=session["customer"])
    return Order.objects.filter(access).order_by("-created")

def quantity(value):
    try:
        qty = int(value)
        if 1 <= qty <= 20:
            return qty
    except (ValueError, TypeError):
        pass
    raise ValueError("Escolha uma quantidade entre 1 e 20.")

def price_line(line):
    p = storefront.products().filter(slug=line["slug"]).first()
    if not p or not p.available:
        raise ValueError("Produto indisponível. Remova o item para continuar.")
    qty = quantity(line["qty"])
    if (p.options and line["option"] not in p.options) or (not p.options and line["option"]):
        raise ValueError("Selecione uma opção válida de personalização.")
    extras = dict(p.extras)
    if any(key not in extras for key in line["extras"]):
        raise ValueError("Adicional indisponível.")
    unit = p.price + sum(extras[key] for key in line["extras"])
    return dict(line, name=p.name, image=p.image, unit=unit-p.discount, total=(unit-p.discount)*qty, discount=p.discount*qty)

def summary(session):
    lines = [price_line(line) for line in session.get("cart", [])]
    partial = sum(line["total"] for line in lines)
    discount = sum(line["discount"] for line in lines)
    return dict(lines=lines, partial=partial, discount=discount, subtotal=partial+discount)

def change_cart(session, lines):
    session["cart"] = lines
    session["token"] = str(uuid.uuid4())

def add(session, p, data):
    line = dict(slug=p.slug, option=data.get("option", ""), extras=sorted(set(data.getlist("extras"))), notes=data.get("notes", "").strip(), qty=quantity(data.get("qty")))
    if len(line["notes"]) > 300:
        raise ValueError("Use até 300 caracteres nas observações.")
    price_line(line)
    lines = list(session.get("cart", []))
    lines.append(dict(line, key=uuid.uuid4().hex))
    change_cart(session, lines)

def confirm(session, token, mode, destination, payment, notes):
    if token != session.get("token") or not session.get("cart"):
        raise ValueError("O carrinho mudou. Revise seu pedido.")
    config = storefront.restaurant()
    if not config.accepting or (mode == "delivery" and not config.delivery):
        raise ValueError("Esta modalidade está temporariamente indisponível.")
    if mode == "delivery" and payment not in config.payments:
        raise ValueError("Selecione uma forma de pagamento disponível.")
    if mode == "restaurante":
        table = storefront.tables().filter(number=destination["table"]).first()
        if table is None:
            raise ValueError("Selecione uma mesa disponível.")
        destination = dict(destination, label=str(table), table_id=table.pk)
    totals = summary(session)
    fee = config.fee if mode == "delivery" else 0
    fields = dict(
        token=token, owner=owner(session), customer_id=session.get("customer"),
        mode=mode, destination=destination, payment=payment, notes=notes,
        items=totals["lines"], subtotal=totals["subtotal"],
        discount=totals["discount"], fee=fee, total=totals["partial"] + fee,
    )
    for attempt in range(4):
        try:
            with transaction.atomic():
                # Insert first so concurrent SQLite writers serialize on the unique key.
                order = Order.objects.create(**fields)
                OrderEvent.objects.create(order=order, action="received")
                reserve_stock(order, totals["lines"])
                if getattr(settings, "BYTEBISTRO_OUTBOX_ENABLED", False):
                    OrderOutbox.objects.create(order=order)
                if mode == "delivery":
                    # Serialize changes to the address list while allowing order foreign-key checks.
                    customers = Customer.objects.select_for_update(no_key=connection.features.has_select_for_no_key_update)
                    account = customers.filter(pk=fields["customer_id"]).first()
                    if account is None:
                        raise ValueError("Entre na sua conta para concluir o pedido.")
                    if destination not in account.addresses:
                        account.addresses.append(destination)
                        account.save(update_fields=["addresses"])
            break
        except IntegrityError:
            order = orders(session).filter(token=token).first()
            if order is None:
                raise
            break
        except OperationalError as error:
            if connection.vendor != "sqlite" or "locked" not in str(error).lower():
                raise
            if attempt == 3:
                raise ValueError("Banco ocupado. Tente novamente.") from error
            sleep(0.025 * (attempt + 1))
    change_cart(session, [])
    return order
