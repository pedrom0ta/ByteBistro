import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from django.contrib.auth.models import Group, User
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from . import services
from .models import (
    Category,
    Ingredient,
    MenuProduct,
    Order,
    OrderOutbox,
    ProductIngredient,
    Restaurant,
    StockReservation,
    Table,
)
from .operations import transition
from .stock import release_reservations


def create_manager(username="stock_manager"):
    user = User.objects.create_user(username, password="example-test-pass-862", is_staff=True)
    user.groups.add(Group.objects.get_or_create(name="gerente")[0])
    return user


class StockReservationTests(TestCase):
    def setUp(self):
        self.manager = create_manager()
        self.staff = Client()
        self.staff.force_login(self.manager)
        self.smash = MenuProduct.objects.get(slug="smash")
        self.meat = Ingredient.objects.create(
            name="Carne bovina",
            unit="kg",
            quantity=Decimal("1.000"),
            minimum=Decimal("0.300"),
        )
        ProductIngredient.objects.create(
            product=self.smash,
            ingredient=self.meat,
            quantity_per_unit=Decimal("0.200"),
        )

    def add_smash(self, qty=2, client=None):
        target = client or self.client
        return target.post(
            "/produto/smash/",
            {"qty": qty, "option": "Ao ponto", "extras": ["Bacon"]},
        )

    @override_settings(BYTEBISTRO_OUTBOX_ENABLED=True)
    def test_checkout_reserves_stock_and_retry_keeps_single_reservation(self):
        self.add_smash(qty=2)
        payload = {"table": "1", "token": self.client.session["token"]}
        first = self.client.post("/restaurante/", payload)
        retry = self.client.post("/restaurante/", payload)
        self.assertEqual(first.url, retry.url)

        order = Order.objects.get()
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal("0.600"))
        reservation = StockReservation.objects.get(order=order)
        self.assertEqual(reservation.ingredient, self.meat)
        self.assertEqual(reservation.quantity, Decimal("0.400"))
        self.assertEqual(reservation.status, StockReservation.ACTIVE)
        self.assertEqual(OrderOutbox.objects.filter(order=order).count(), 1)

    def test_checkout_blocked_when_stock_insufficient(self):
        self.meat.quantity = Decimal("0.300")
        self.meat.save()
        self.add_smash(qty=2)
        response = self.client.post(
            "/restaurante/",
            {"table": "1", "token": self.client.session["token"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estoque insuficiente para: Carne bovina")
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(StockReservation.objects.count(), 0)
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal("0.300"))
        self.assertEqual(len(self.client.session["cart"]), 1)

    def test_product_unavailable_on_menu_when_depleted_and_restored_on_cancel_or_restock(self):
        self.meat.quantity = Decimal("0.200")
        self.meat.save()
        self.add_smash(qty=1)
        self.client.post("/restaurante/", {"table": "1", "token": self.client.session["token"]})
        order = Order.objects.get()

        self.smash.refresh_from_db()
        self.assertFalse(self.smash.available)
        menu_response = self.client.get("/cardapio/")
        self.assertContains(menu_response, "Esgotado")
        self.assertContains(menu_response, "sold-out")

        transition(order, "cancel", self.manager, reason="Cliente desistiu", expected=0)
        self.meat.refresh_from_db()
        self.smash.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal("0.200"))
        self.assertTrue(self.smash.available)
        reservation = StockReservation.objects.get(order=order)
        self.assertEqual(reservation.status, StockReservation.RELEASED)
        self.assertIsNotNone(reservation.released_at)

        # Deplete again, then restock via inventory movement
        self.add_smash(qty=1)
        self.client.post("/restaurante/", {"table": "1", "token": self.client.session["token"]})
        self.smash.refresh_from_db()
        self.assertFalse(self.smash.available)

        self.staff.post(
            f"/painel/inventory/?edit={self.meat.pk}",
            {"movement": 1, "kind": "in", "amount": "1.000", "reason": "Reposição"},
        )
        self.smash.refresh_from_db()
        self.assertTrue(self.smash.available)

    def test_repeated_release_is_idempotent(self):
        self.add_smash(qty=2)
        self.client.post("/restaurante/", {"table": "1", "token": self.client.session["token"]})
        order = Order.objects.get()

        transition(order, "cancel", self.manager, reason="Cancelamento 1", expected=0)
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal("1.000"))

        # Repeated release call must not restore stock a second time
        release_reservations(order)
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal("1.000"))

        with self.assertRaises(ValueError):
            order.refresh_from_db()
            transition(order, "cancel", self.manager, reason="Cancelamento 2")
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal("1.000"))

    def test_reject_releases_and_complete_confirms_reservation(self):
        self.add_smash(qty=1)
        self.client.post("/restaurante/", {"table": "1", "token": self.client.session["token"]})
        rejected = Order.objects.latest("created")
        transition(rejected, "reject", self.manager, reason="Sem chapa", expected=0)
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal("1.000"))
        self.assertEqual(StockReservation.objects.get(order=rejected).status, StockReservation.RELEASED)

        self.add_smash(qty=1)
        self.client.post("/restaurante/", {"table": "1", "token": self.client.session["token"]})
        delivered = Order.objects.latest("created")
        transition(delivered, "accept", self.manager, expected=0)
        delivered.refresh_from_db()
        transition(delivered, "ready", self.manager, expected=1)
        delivered.refresh_from_db()
        transition(delivered, "complete", self.manager, expected=2)
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal("0.800"))
        self.assertEqual(StockReservation.objects.get(order=delivered).status, StockReservation.CONFIRMED)

    def test_product_without_recipe_keeps_manual_availability(self):
        brownie = MenuProduct.objects.get(slug="brownie")
        self.client.post("/produto/brownie/", {"qty": 1})
        self.client.post("/restaurante/", {"table": "1", "token": self.client.session["token"]})
        order = Order.objects.get()
        self.assertEqual(StockReservation.objects.filter(order=order).count(), 0)
        brownie.refresh_from_db()
        self.assertTrue(brownie.available)

    def test_dashboard_low_stock_alert_is_configurable(self):
        self.meat.quantity = Decimal("0.200")
        self.meat.save()
        response = self.staff.get(reverse("staff_section", args=["dashboard"]))
        self.assertContains(response, "Estoque baixo")
        self.assertContains(response, "Carne bovina")

        Restaurant.objects.filter(pk=1).update(low_stock_alert=False)
        response = self.staff.get(reverse("staff_section", args=["dashboard"]))
        self.assertNotContains(response, "Carne bovina")

    def test_staff_can_manage_product_recipe_formset(self):
        pizza = MenuProduct.objects.get(slug="pizza")
        cheese = Ingredient.objects.create(
            name="Muçarela",
            unit="kg",
            quantity=Decimal("0.100"),
            minimum=Decimal("0.500"),
        )
        response = self.staff.post(
            f"/painel/products/?edit={pizza.pk}",
            {
                "slug": pizza.slug,
                "name": pizza.name,
                "category": pizza.category_id,
                "description": pizza.description,
                "price": pizza.price,
                "discount": pizza.discount,
                "image": pizza.image,
                "available": "on",
                "prep_minutes": pizza.prep_minutes,
                "recipe-TOTAL_FORMS": "1",
                "recipe-INITIAL_FORMS": "0",
                "recipe-MIN_NUM_FORMS": "0",
                "recipe-MAX_NUM_FORMS": "1000",
                "recipe-0-ingredient": str(cheese.pk),
                "recipe-0-quantity_per_unit": "0.250",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductIngredient.objects.filter(product=pizza, ingredient=cheese).count(), 1)
        pizza.refresh_from_db()
        self.assertFalse(pizza.available)


class ConcurrentStockReservation(TransactionTestCase):
    def setUp(self):
        category, _ = Category.objects.get_or_create(name="Hambúrgueres", defaults={"position": 0})
        self.smash, _ = MenuProduct.objects.get_or_create(
            slug="smash",
            defaults={
                "name": "Smash da Casa",
                "category": category,
                "description": "Burger",
                "price": 3490,
                "image": "burger.jpg",
                "available": True,
            },
        )
        MenuProduct.objects.filter(pk=self.smash.pk).update(available=True, archived=False)
        Table.objects.get_or_create(number=1)
        Restaurant.objects.get_or_create(pk=1, defaults={"payments": ["Pix"], "accepting": True})
        self.meat = Ingredient.objects.create(
            name="Carne concorrente",
            unit="kg",
            quantity=Decimal("0.200"),
            minimum=Decimal("0.100"),
        )
        ProductIngredient.objects.create(
            product=self.smash,
            ingredient=self.meat,
            quantity_per_unit=Decimal("0.200"),
        )

    def test_only_one_concurrent_checkout_gets_last_unit(self):
        gate = Barrier(2)
        option = self.smash.options[0] if self.smash.options else ""

        def attempt_checkout(_index):
            close_old_connections()
            try:
                token = str(uuid.uuid4())
                session = {
                    "owner": uuid.uuid4().hex,
                    "token": token,
                    "cart": [{"slug": "smash", "option": option, "extras": [], "notes": "", "qty": 1, "key": uuid.uuid4().hex}],
                }
                gate.wait(timeout=5)
                services.confirm(session, token, "restaurante", {"table": "1"}, "No restaurante", "")
                return True
            except ValueError:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt_checkout, [0, 1]))

        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 1)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(StockReservation.objects.count(), 1)
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal("0.000"))
        self.smash.refresh_from_db()
        self.assertFalse(self.smash.available)
