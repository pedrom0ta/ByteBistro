import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth.models import Group, User
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from .models import Customer, Ingredient, MenuProduct, Order, OrderEvent, Restaurant, Table
from .operations import transition

def employee(name, role=None):
    user = User.objects.create_user(name, password="example-test-pass-862", is_staff=True, is_superuser=role is None)
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    return user

def place(client):
    client.post("/produto/smash/", {"qty": 2, "option": "Ao ponto", "extras": ["Bacon"]})
    client.post("/restaurante/", {"token": client.session["token"], "table": "1", "notes": "Teste"})
    return Order.objects.latest("created")

class OperationsTests(TestCase):
    def setUp(self):
        self.manager = employee("manager", "gerente")
        self.waiter = employee("waiter", "atendente")
        self.cook = employee("cook", "cozinha")
        self.staff = Client()
        self.staff.force_login(self.manager)
        self.kitchen = Client()
        self.kitchen.force_login(self.cook)

    def change(self, order, action, stage, client=None, reason=""):
        return (client or self.staff).post(reverse("staff_change", args=[order.pk]),
                                           {"action": action, "stage": stage, "reason": reason})

    def status(self, order):
        return self.client.get(reverse("status", args=[order.pk])).json()

    def test_restaurant_operational_flow(self):
        board = "/painel/orders/atualizar/"
        self.assertNotContains(self.staff.get(board), "data-order=")
        order = place(self.client)
        self.assertContains(self.staff.get(board), f'data-order="{order.pk}"', count=1)
        self.assertNotContains(self.kitchen.get("/painel/kitchen/"), order.number)
        self.assertEqual(self.change(order, "accept", 0, client=self.kitchen).status_code, 403)
        self.change(order, "accept", 0)
        self.change(order, "accept", 0)
        self.assertEqual(self.status(order)["status"], "Em preparo")
        self.assertEqual(order.events.filter(action="accept").count(), 1)
        self.assertContains(self.kitchen.get("/painel/kitchen/atualizar/"), f'data-order="{order.pk}"', count=1)
        self.assertNotContains(self.kitchen.get("/painel/kitchen/"), "R$")
        waiter = Client()
        waiter.force_login(self.waiter)
        self.assertEqual(self.change(order, "ready", 1, client=waiter).status_code, 403)
        self.change(order, "ready", 1, client=self.kitchen)
        self.assertEqual(self.status(order)["status"], "Pronto")
        self.change(order, "complete", 2)
        self.change(order, "paid", 3)
        self.assertEqual(self.status(order)["status"], "Entregue")
        self.assertContains(self.staff.get("/painel/reports/"), "67,80")
        self.assertContains(self.staff.get(reverse("staff_detail", args=[order.pk])), "Recebimento registrado")

    def test_rejection_requires_reason_and_is_terminal(self):
        order = place(self.client)
        self.change(order, "reject", 0)
        self.assertEqual(self.status(order)["stage"], 0)
        self.change(order, "reject", 0, reason="Produto indisponível")
        self.change(order, "accept", 90)
        self.assertEqual(self.status(order)["status"], "Recusado")
        self.assertEqual(self.status(order)["reason"], "Produto indisponível")
        self.assertEqual(order.events.get(action="reject").actor, self.manager)

    def test_delivery_requires_dispatch(self):
        customer = Customer.objects.create(name="Cliente de teste", phone="75999999999")
        session = self.client.session
        session["customer"] = customer.pk
        session.save()
        self.client.post("/produto/smash/", {"qty": 1, "option": "Ao ponto"})
        response = self.client.post("/delivery/", {
            "token": self.client.session["token"], "address": "new", "payment": "Pix",
            "cep": "44000000", "street": "Rua de teste", "number": "10", "district": "Centro",
            "city": "Feira de Santana", "state": "BA",
        })
        order = Order.objects.get(customer=customer)
        self.assertRedirects(response, reverse("track", args=[order.pk]))
        self.change(order, "accept", 0)
        self.change(order, "ready", 1, client=self.kitchen)
        self.change(order, "complete", 2)
        self.assertEqual(self.status(order)["status"], "Pronto para entrega")
        self.change(order, "dispatch", 2)
        self.assertEqual(self.status(order)["status"], "Saiu para entrega")
        self.change(order, "complete", 3)
        self.assertEqual(self.status(order)["status"], "Entregue")

    def test_access_and_modules_render(self):
        self.assertRedirects(self.client.get("/painel/"), "/painel/entrar/")
        self.assertEqual(self.client.post("/painel/entrar/", {"username":"cook", "password":"example-test-pass-862"}).status_code, 302)
        self.assertEqual(self.kitchen.get("/painel/customers/").status_code, 403)
        self.staff.force_login(employee("administrator"))
        for section in ("dashboard", "orders", "kitchen", "tables", "products", "categories", "inventory", "customers", "reports", "staff", "settings"):
            with self.subTest(section=section):
                self.assertEqual(self.staff.get(f"/painel/{section}/").status_code, 200)

    def test_product_and_table_availability(self):
        self.client.post("/produto/smash/", {"qty": 1, "option": "Ao ponto"})
        data = {"token": self.client.session["token"], "table": "1"}
        table = Table.objects.get(number=1)
        self.staff.post(f"/painel/tables/?edit={table.pk}", {"number": 1, "label": "Janela"})
        self.assertContains(self.client.post("/restaurante/", data), "Selecione a mesa")
        Table.objects.filter(pk=table.pk).update(active=True)
        product = MenuProduct.objects.get(slug="smash")
        self.staff.post(f"/painel/products/?edit={product.pk}", {
            "slug": "smash", "name": product.name, "category": product.category_id,
            "description": product.description, "price": product.price, "discount": product.discount,
            "image": product.image, "prep_minutes": 20,
        })
        self.assertContains(self.client.get("/produto/smash/"), "indisponível")
        self.assertEqual(self.client.post("/restaurante/", data).url, "/carrinho/")
        self.assertFalse(Order.objects.exists())
        self.staff.post("/painel/products/", {"product_id": product.pk, "availability": "on"})
        self.assertContains(self.client.get("/produto/smash/"), "Adicionar ao carrinho")
        self.kitchen.post("/painel/products/", {"product_id": product.pk, "availability": "off"})
        self.assertTrue(MenuProduct.objects.get(pk=product.pk).available)

    def test_inventory_and_settings(self):
        self.staff.post("/painel/inventory/", {"name": "Batata", "unit": "kg", "minimum": "2"})
        ingredient = Ingredient.objects.get()
        path = f"/painel/inventory/?edit={ingredient.pk}"
        self.staff.post(path, {"movement": 1, "kind": "in", "amount": "4", "reason": "Compra"})
        self.assertContains(self.staff.post(path, {"movement": 1, "kind": "out", "amount": "5", "reason": "Teste"}), "fora do limite")
        ingredient.refresh_from_db()
        self.assertEqual(ingredient.quantity, 4)
        self.assertEqual(ingredient.movements.count(), 1)
        data = {"name": "ByteBistro", "fee": 900, "prep": 20, "alert_minutes": 5, "payments": ["Pix"]}
        self.staff.post("/painel/settings/", data)
        self.assertFalse(Restaurant.objects.get().accepting)
        self.assertContains(self.client.get("/"), "pausou")

class ConcurrentApproval(TransactionTestCase):
    def test_only_one_employee_can_accept(self):
        first = employee("first")
        second = employee("second")
        order = Order.objects.create(token=uuid.uuid4(), owner="test", mode="restaurante",
            destination={"table":"1"}, payment="No restaurante", items=[], subtotal=1000, discount=0, fee=0, total=1000)
        gate = Barrier(2)

        def accept(user):
            close_old_connections()
            try:
                snapshot = Order.objects.get(pk=order.pk)
                gate.wait(timeout=5)
                transition(snapshot, "accept", user, expected=0)
                return True
            except ValueError:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, [first, second]))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(OrderEvent.objects.filter(order=order, action="accept").count(), 1)

