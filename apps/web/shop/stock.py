from decimal import Decimal
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from .models import Ingredient, MenuProduct, ProductIngredient, StockReservation


def refresh_product_availability(ingredient_ids=None, product_ids=None):
    """Sincroniza `available` dos produtos com receita conforme o estoque dos insumos."""
    qs = ProductIngredient.objects.all()
    if ingredient_ids is not None:
        qs = qs.filter(ingredient_id__in=ingredient_ids)
    if product_ids is not None:
        qs = qs.filter(product_id__in=product_ids)
    affected_ids = list(qs.values_list("product_id", flat=True).distinct())
    if not affected_ids:
        return

    insufficient_ids = set(
        ProductIngredient.objects.filter(
            product_id__in=affected_ids,
            ingredient__quantity__lt=F("quantity_per_unit"),
        ).values_list("product_id", flat=True)
    )
    to_disable = [pid for pid in affected_ids if pid in insufficient_ids]
    to_enable = [pid for pid in affected_ids if pid not in insufficient_ids]
    if to_disable:
        MenuProduct.objects.filter(pk__in=to_disable, archived=False, available=True).update(available=False)
    if to_enable:
        MenuProduct.objects.filter(pk__in=to_enable, archived=False, available=False).update(available=True)


def reserve_stock(order, lines):
    """Valida saldo dos insumos necessários, debita e cria reservas ativas na mesma transação."""
    slugs_qty = {}
    for line in lines:
        slugs_qty[line["slug"]] = slugs_qty.get(line["slug"], 0) + line["qty"]
    if not slugs_qty:
        return

    recipes = (
        ProductIngredient.objects
        .filter(product__slug__in=slugs_qty.keys())
        .select_related("product", "ingredient")
    )

    demand = {}
    for recipe in recipes:
        needed = recipe.quantity_per_unit * slugs_qty[recipe.product.slug]
        demand[recipe.ingredient_id] = demand.get(recipe.ingredient_id, Decimal("0")) + needed

    if not demand:
        return

    ingredient_ids = sorted(demand.keys())
    ingredients_qs = Ingredient.objects.filter(pk__in=ingredient_ids).order_by("pk")
    if connection.vendor != "sqlite":
        ingredients_qs = ingredients_qs.select_for_update()

    locked = {ing.pk: ing for ing in ingredients_qs}
    insufficient = [
        locked[ing_id].name
        for ing_id in ingredient_ids
        if locked[ing_id].quantity < demand[ing_id]
    ]
    if insufficient:
        raise ValueError(
            f"Estoque insuficiente para: {', '.join(insufficient)}. "
            "Ajuste ou remova os itens para continuar."
        )

    now = timezone.now()
    for ing_id in ingredient_ids:
        needed = demand[ing_id]
        Ingredient.objects.filter(pk=ing_id).update(
            quantity=F("quantity") - needed,
            updated=now,
        )
        StockReservation.objects.create(
            order=order,
            ingredient_id=ing_id,
            quantity=needed,
            status=StockReservation.ACTIVE,
        )

    refresh_product_availability(ingredient_ids=ingredient_ids)


def release_reservations(order):
    """Libera reservas ativas do pedido de forma idempotente e devolve o estoque."""
    now = timezone.now()
    ingredient_ids = []
    with transaction.atomic():
        reservations_qs = StockReservation.objects.filter(
            order=order,
            status=StockReservation.ACTIVE,
        ).order_by("pk")
        if connection.vendor != "sqlite":
            reservations_qs = reservations_qs.select_for_update()

        for reservation in reservations_qs:
            claimed = StockReservation.objects.filter(
                pk=reservation.pk,
                status=StockReservation.ACTIVE,
            ).update(status=StockReservation.RELEASED, released_at=now)
            if claimed:
                Ingredient.objects.filter(pk=reservation.ingredient_id).update(
                    quantity=F("quantity") + reservation.quantity,
                    updated=now,
                )
                ingredient_ids.append(reservation.ingredient_id)

        if ingredient_ids:
            refresh_product_availability(ingredient_ids=ingredient_ids)


def confirm_reservations(order):
    """Marca reservas ativas do pedido como confirmadas após a conclusão."""
    StockReservation.objects.filter(
        order=order,
        status=StockReservation.ACTIVE,
    ).update(status=StockReservation.CONFIRMED)
