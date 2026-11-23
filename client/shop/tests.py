import time
from unittest.mock import patch
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .models import Customer, Order
from .services import DELIVERY_FEE
from .models import MenuProduct

@override_settings(DEBUG=True)
class Flows(TestCase):
    def setUp(self):
        cache.clear()

    def add(self):
        return self.client.post("/produto/smash/", {"qty":2, "option":"Ao ponto", "extras":["Bacon"], "price":1})

    def enter(self, existing=False):
        if existing:
            Customer.objects.create(phone="75999999999", name="Cliente existente", addresses=[self.address()])
        self.assertRedirects(self.client.get("/delivery/"), "/telefone/?next=delivery")
        with patch("shop.sms.secrets.randbelow", return_value=123456), self.assertLogs("bytebistro.sms"):
            self.assertRedirects(self.client.post("/telefone/", {"phone":"(75) 99999-9999"}), "/verificar/")
        self.assertContains(self.client.post("/verificar/", {"code":"000000"}), "Código incorreto")
        result = self.client.post("/verificar/", {"code":"123456"})
        self.assertRedirects(result, "/delivery/" if existing else "/cadastro/")
        if not existing:
            self.assertRedirects(self.client.post("/cadastro/", {"name":"Cliente Novo"}), "/delivery/")
        self.assertEqual(self.client.session["cart"][0]["qty"], 2)

    def address(self):
        return {"street":"Rua das Flores", "number":"42", "district":"Centro", "city":"Salvador", "state":"BA", "cep":"40000000", "extra":"", "reference":""}

    def test_menu_and_cart(self):
        for url in ["/", "/cardapio/", "/produto/smash/", "/conta/", "/pedidos/"]:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get("/cardapio/?q=laranja&cat=Bebidas"), "Suco de laranja")
        self.assertNotContains(self.client.get("/cardapio/?q=laranja&cat=Pizzas"), "Suco de laranja")
        self.assertRedirects(self.client.get("/modalidade/"), "/carrinho/")
        self.assertContains(self.client.post("/produto/smash/", {"qty":0}), "entre 1 e 20")
        self.assertContains(self.client.post("/produto/smash/", {"qty":1}), "personalização")
        self.assertContains(self.client.post("/produto/smash/", {"qty":1,"option":"Ao ponto","extras":["Inválido"]}), "Adicional indisponível")
        self.assertRedirects(self.add(), "/carrinho/")
        key = self.client.session["cart"][0]["key"]
        self.client.post("/carrinho/", {"key":key, "qty":3})
        self.assertContains(self.client.get("/carrinho/"), "101,70")
        MenuProduct.objects.filter(slug="smash").update(available=False)
        self.assertContains(self.client.get("/carrinho/"), "indisponível")
        self.client.post("/carrinho/", {"key":key, "remove":1})
        self.assertContains(self.client.get("/carrinho/"), "está vazio")

    def test_restaurant_and_duplicate(self):
        self.add()
        self.assertContains(self.client.get("/modalidade/"), "Consumir no restaurante")
        token = self.client.session["token"]
        self.assertContains(self.client.post("/restaurante/", {"token":token}), "Selecione a mesa")
        data = {"table":"4", "token":token}
        response = self.client.post("/restaurante/", data)
        order = Order.objects.get()
        url = reverse("track", args=[order.pk])
        self.assertRedirects(response, url)
        self.assertRedirects(self.client.post("/restaurante/", data), url)
        self.assertEqual(order.total, 6780)
        self.assertEqual(Client().get(url).status_code, 404)
        self.assertContains(self.client.get("/pedidos/"), order.number)
        for _ in range(2):
            call_command("avancar_pedido", order.number)
        self.assertTrue(self.client.get(url+"status/").json()["finished"])
        self.assertRedirects(self.client.get(url), url+"conclusao/")
        self.assertContains(self.client.get(url+"conclusao/"), "Seu pedido está pronto!")
        self.assertContains(self.client.get(url+"?detalhes=1"), "Detalhes do pedido")

    def test_new_delivery(self):
        self.add()
        self.enter()
        data = {"payment":"Pix", "token":self.client.session["token"]}
        self.assertContains(self.client.post("/delivery/", data), "Confira os campos")
        self.client.post("/delivery/", {**self.address(), **data})
        order = Order.objects.get()
        self.assertEqual(order.total, 6780+DELIVERY_FEE)
        self.assertEqual(len(Customer.objects.get().addresses), 1)
        for _ in range(4):
            call_command("avancar_pedido", order.number)
        self.assertContains(self.client.get(reverse("done", args=[order.pk])), "Pedido entregue!")
        self.client.post("/sair/")
        self.assertNotContains(self.client.get("/pedidos/"), order.number)

    def test_returning_delivery(self):
        self.add()
        self.enter(existing=True)
        self.assertContains(self.client.get("/delivery/"), "Rua das Flores")
        self.client.post("/delivery/", {"address":"0", "payment":"Dinheiro", "token":self.client.session["token"]})
        self.assertEqual(Order.objects.get().destination["number"], "42")
        self.assertEqual(Customer.objects.count(), 1)
        self.assertContains(self.client.get("/conta/"), "Cliente existente")

    def test_sms_limits_and_expiry(self):
        phone = {"phone":"75999999999"}
        with self.assertLogs("bytebistro.sms"):
            self.client.post("/telefone/", phone)
        self.assertContains(self.client.post("/verificar/", {"resend":"1"}), "Aguarde um minuto")
        for _ in range(5):
            self.client.post("/verificar/", {"code":"x"})
        self.assertContains(self.client.post("/verificar/", {"code":"x"}), "Limite atingido")
        with patch("shop.sms.time.time", return_value=time.time()+310):
            self.assertContains(self.client.post("/verificar/", {"code":"x"}), "Código expirado")

    def test_stale_checkout_preserves_cart(self):
        self.add()
        old_token = self.client.session["token"]
        self.add()
        self.assertContains(
            self.client.post("/restaurante/", {"table": "1", "token": old_token}),
            "O carrinho mudou",
        )
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(len(self.client.session["cart"]), 2)

    def test_resends_across_sessions_and_production_provider(self):
        phone = {"phone": "75999999999"}
        start = time.time()
        for attempt in range(4):
            with patch("time.time", return_value=start + attempt * 65), self.assertLogs("bytebistro.sms"):
                self.assertEqual(Client().post("/telefone/", phone).status_code, 302)
        with patch("time.time", return_value=start + 270):
            self.assertContains(Client().post("/telefone/", phone), "Limite atingido")
        with override_settings(DEBUG=False):
            self.assertContains(Client().post("/telefone/", {"phone":"75999999998"}), "provedor de SMS")
