import importlib
import json
import os
import sys
import time
import uuid
from io import BytesIO
from unittest.mock import MagicMock, patch
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .models import Customer, MenuProduct, Order, OrderEvent, OrderOutbox
from .services import DELIVERY_FEE
from . import sms as sms_module
from .sms import BotoCoreError, ClientError, ConsoleProvider, SnsSmsProvider

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

    @override_settings(BYTEBISTRO_OUTBOX_ENABLED=True)
    def test_checkout_retries_keep_one_outbox_event(self):
        self.add()
        data = {"table": "4", "token": self.client.session["token"]}
        first = self.client.post("/restaurante/", data)
        retry = self.client.post("/restaurante/", data)
        self.assertEqual(first.url, retry.url)
        self.assertEqual(OrderOutbox.objects.get().order_id, Order.objects.get().pk)

    @override_settings(BYTEBISTRO_GRAPHQL_URL="http://api:4000/graphql")
    def test_status_queries_internal_graphql_with_session_identity(self):
        self.add()
        response = self.client.post("/restaurante/", {"table": "4", "token": self.client.session["token"]})
        payload = {"stage": 0, "status": "Pedido recebido", "finished": False, "reason": ""}
        with patch("shop.views.order_status", return_value=payload) as lookup:
            status = self.client.get(response.url + "status/")
        self.assertEqual(status.json(), payload)
        self.assertEqual(status.headers["Cache-Control"], "no-store")
        lookup.assert_called_once_with(Order.objects.get().pk, self.client.session["owner"], None)

    @override_settings(BYTEBISTRO_GRAPHQL_URL="http://api:4000/graphql", GRAPHQL_SERVICE_TOKEN="test-token")
    def test_graphql_tracking_distinguishes_missing_orders_from_upstream_failures(self):
        self.add()
        self.client.post("/restaurante/", {"table": "4", "token": self.client.session["token"]})
        url = reverse("status", args=[Order.objects.get().pk])
        payload = {"stage": 0, "status": "Pedido recebido", "finished": False, "reason": ""}

        with patch("shop.graphql.urlopen", return_value=BytesIO(json.dumps({"data": {"orderStatus": payload}}).encode())):
            response = self.client.get(url)
        self.assertEqual(response.json(), payload)

        with patch("shop.graphql.urlopen", return_value=BytesIO(b'{"data":{"orderStatus":null}}')):
            missing = Client().get(url)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.headers["Cache-Control"], "no-store")

        for response_body in (
            b'{broken JSON',
            b'{"errors":[{"message":"Upstream failure"}],"data":{"orderStatus":null}}',
            json.dumps({"data": {"orderStatus": {**payload, "stage": True}}}).encode(),
        ):
            with self.subTest(response_body=response_body):
                with patch("shop.graphql.urlopen", return_value=BytesIO(response_body)):
                    failure = self.client.get(url)
                self.assertEqual(failure.status_code, 503)
                self.assertEqual(failure.headers["Cache-Control"], "no-store")
                self.assertEqual(failure.json(), {"error": "Acompanhamento temporariamente indisponível."})

        with patch("shop.graphql.urlopen", side_effect=TimeoutError):
            self.assertEqual(self.client.get(url).status_code, 503)

    def test_local_tracking_status_is_private_to_the_order_owner(self):
        self.add()
        self.client.post("/restaurante/", {"table": "4", "token": self.client.session["token"]})
        url = reverse("status", args=[Order.objects.get().pk])

        self.assertEqual(self.client.get(url).headers["Cache-Control"], "no-store")
        missing = Client().get(url)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.headers["Cache-Control"], "no-store")
        self.assertEqual(missing.json(), {"error": "Pedido não encontrado."})

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


class ProductionSmsAndOrderEventTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_sns_sms_provider_e164_normalization_and_validation(self):
        cases = [
            ("75999999999", "+5575999999999"),
            ("(75) 99999-9999", "+5575999999999"),
            ("+5575999999999", "+5575999999999"),
            ("+55 75 99999-9999", "+5575999999999"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                mock_client = MagicMock()
                provider = SnsSmsProvider(client=mock_client)
                with patch("shop.sms.secrets.randbelow", return_value=123456), self.assertLogs("bytebistro.sms", level="INFO") as logs:
                    challenge = provider.issue(raw)
                self.assertTrue(provider.verify(challenge, "123456"))
                self.assertFalse(provider.verify(challenge, "000000"))
                mock_client.publish.assert_called_once()
                kwargs = mock_client.publish.call_args.kwargs
                self.assertEqual(kwargs["PhoneNumber"], expected)
                self.assertIn("123456", kwargs["Message"])
                self.assertEqual(
                    kwargs["MessageAttributes"],
                    {"AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}},
                )
                self.assertFalse(any("123456" in msg for msg in logs.output))

        with override_settings(SMS_COUNTRY_CODE="+1"):
            mock_client = MagicMock()
            with self.assertLogs("bytebistro.sms", level="INFO"):
                SnsSmsProvider(client=mock_client).issue("4155552671")
            self.assertEqual(mock_client.publish.call_args.kwargs["PhoneNumber"], "+14155552671")

        with override_settings(SMS_COUNTRY_CODE="1"):
            mock_client = MagicMock()
            with self.assertLogs("bytebistro.sms", level="INFO"):
                SnsSmsProvider(client=mock_client).issue("4155552671")
            self.assertEqual(mock_client.publish.call_args.kwargs["PhoneNumber"], "+14155552671")

        for invalid in ("", "123", "abc", "+05575999999999", "+123", None):
            with self.subTest(invalid=invalid):
                mock_client = MagicMock()
                with self.assertRaises(ValueError):
                    SnsSmsProvider(client=mock_client).issue(invalid)
                mock_client.publish.assert_not_called()

        for bad_cc in ("", "   ", "+", "+0", "0", "+abc", None):
            with self.subTest(settings_country_code=bad_cc):
                mock_client = MagicMock()
                with override_settings(SMS_COUNTRY_CODE=bad_cc):
                    with self.assertRaises(ValueError):
                        SnsSmsProvider(client=mock_client).issue("75999999999")
                mock_client.publish.assert_not_called()

        for bad_cc in ("", "   ", "+", "+0", "0", "+abc", 55):
            with self.subTest(explicit_country_code=bad_cc):
                mock_client = MagicMock()
                with self.assertRaises(ValueError):
                    SnsSmsProvider(client=mock_client, country_code=bad_cc).issue("75999999999")
                mock_client.publish.assert_not_called()

    def test_otp_verify_malformed_challenges_return_false_without_crashing(self):
        mock_client = MagicMock()
        sns_provider = SnsSmsProvider(client=mock_client)
        console_provider = ConsoleProvider()
        with self.assertLogs("bytebistro.sms", level="INFO"):
            valid_challenge = sns_provider.issue("75999999999")
        mock_client.publish.reset_mock()

        malformed_challenges = ("", "nodot", "a.b.c", None, ".", "abc.", ".abc", 123)
        for provider in (sns_provider, console_provider):
            for challenge in malformed_challenges:
                with self.subTest(provider=type(provider).__name__, challenge=challenge):
                    self.assertIs(provider.verify(challenge, "123456"), False)
            for bad_code in (None, 123456):
                with self.subTest(provider=type(provider).__name__, code=bad_code):
                    self.assertIs(provider.verify(valid_challenge, bad_code), False)
        mock_client.publish.assert_not_called()

        session = self.client.session
        session["otp"] = {"phone": "75999999999", "challenge": "tampered_no_dot", "issued": int(time.time())}
        session.save()
        cache.set("current:" + sms_module.digest("75999999999"), "tampered_no_dot", 300)
        with self.assertRaises(ValueError) as raised:
            sms_module.verify(session, "123456")
        self.assertEqual(str(raised.exception), "Código incorreto. Confira os seis dígitos.")

    @override_settings(DEBUG=False, SMS_PROVIDER="shop.sms.SnsSmsProvider")
    def test_sns_sms_provider_full_http_roundtrip_without_logging_otp(self):
        mock_client = MagicMock()
        with patch("shop.sms._sns_client", return_value=mock_client), \
                patch("shop.sms.secrets.randbelow", return_value=123456), \
                self.assertLogs("bytebistro.sms", level="INFO") as logs:
            response = self.client.post("/telefone/", {"phone": "(75) 99999-9999"})
        self.assertRedirects(response, "/verificar/")
        mock_client.publish.assert_called_once()
        kwargs = mock_client.publish.call_args.kwargs
        self.assertEqual(kwargs["PhoneNumber"], "+5575999999999")
        self.assertEqual(
            kwargs["MessageAttributes"]["AWS.SNS.SMS.SMSType"],
            {"DataType": "String", "StringValue": "Transactional"},
        )
        self.assertTrue(any("final 9999" in msg for msg in logs.output))
        self.assertFalse(any("123456" in msg for msg in logs.output))

        self.assertContains(self.client.post("/verificar/", {"code": "000000"}), "Código incorreto")
        self.assertRedirects(self.client.post("/verificar/", {"code": "123456"}), "/cadastro/")

    def test_sns_sms_provider_lazy_boto3_import_wiring(self):
        mock_client = MagicMock()
        fake_boto3 = MagicMock()
        fake_boto3.client.return_value = mock_client
        with patch.dict(sys.modules, {"boto3": fake_boto3}), self.assertLogs("bytebistro.sms", level="INFO"):
            challenge = SnsSmsProvider().issue("75999999999")
        fake_boto3.client.assert_called_once_with("sns")
        mock_client.publish.assert_called_once()
        self.assertIn(".", challenge)

    @override_settings(DEBUG=False, SMS_PROVIDER="shop.sms.SnsSmsProvider")
    def test_sns_sms_provider_errors_raise_value_error_and_render_alert(self):
        errors = [
            ("ClientError", ClientError({"Error": {"Code": "InternalError", "Message": "SNS error"}}, "Publish")),
            ("BotoCoreError", BotoCoreError()),
        ]
        for index, (name, error) in enumerate(errors):
            with self.subTest(error=name):
                mock_client = MagicMock()
                mock_client.publish.side_effect = error
                with patch("shop.sms.secrets.randbelow", return_value=123456), self.assertLogs("bytebistro.sms", level="WARNING") as logs:
                    with self.assertRaises(ValueError) as raised:
                        SnsSmsProvider(client=mock_client).issue("75999999999")
                self.assertEqual(str(raised.exception), "Não foi possível enviar o SMS. Tente novamente.")
                self.assertTrue(any("final 9999" in msg and name in msg for msg in logs.output))
                self.assertFalse(any("123456" in msg for msg in logs.output))

                client = Client()
                phone_number = f"7599999999{index}"
                with patch("shop.sms._sns_client", return_value=mock_client), \
                        patch("shop.sms.secrets.randbelow", return_value=123456), \
                        self.assertLogs("bytebistro.sms", level="WARNING") as http_logs:
                    response = client.post("/telefone/", {"phone": phone_number})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Não foi possível enviar o SMS")
                self.assertContains(response, '<p class="alert" role="alert">')
                self.assertNotIn("otp", client.session)
                self.assertFalse(any("123456" in msg for msg in http_logs.output))

    def test_aws_settings_sms_provider_defaults_and_override(self):
        base_env = {
            "DJANGO_SECRET_KEY": "aws-test-secret",
            "BYTEBISTRO_PUBLIC_HOST": "bistro.example.com",
            "BYTEBISTRO_ORIGIN_HOST": "origin.example.com",
            "PGHOST": "db.internal",
            "PGDATABASE": "bytebistro",
            "PGUSER": "bytebistro_web",
            "PGPASSWORD": "secret",
        }
        previous_module = sys.modules.pop("config.aws_settings", None)
        try:
            with patch.dict(os.environ, base_env, clear=True):
                aws = importlib.import_module("config.aws_settings")
                self.assertFalse(aws.DEBUG)
                self.assertEqual(aws.SMS_PROVIDER, "shop.sms.SnsSmsProvider")
                self.assertEqual(aws.SMS_COUNTRY_CODE, "+55")

            sys.modules.pop("config.aws_settings", None)
            empty_env = {
                **base_env,
                "SMS_PROVIDER": "",
                "SMS_COUNTRY_CODE": "",
            }
            with patch.dict(os.environ, empty_env, clear=True):
                aws = importlib.import_module("config.aws_settings")
                self.assertEqual(aws.SMS_PROVIDER, "shop.sms.SnsSmsProvider")
                self.assertEqual(aws.SMS_COUNTRY_CODE, "+55")

            sys.modules.pop("config.aws_settings", None)
            override_env = {
                **base_env,
                "SMS_PROVIDER": "custom.sms.Provider",
                "SMS_COUNTRY_CODE": "+1",
            }
            with patch.dict(os.environ, override_env, clear=True):
                aws = importlib.import_module("config.aws_settings")
                self.assertEqual(aws.SMS_PROVIDER, "custom.sms.Provider")
                self.assertEqual(aws.SMS_COUNTRY_CODE, "+1")
        finally:
            sys.modules.pop("config.aws_settings", None)
            if previous_module is not None:
                sys.modules["config.aws_settings"] = previous_module

    def test_order_event_label_and_staff_detail_rendering(self):
        self.assertEqual(OrderEvent(action="notified").label, "Notificação enviada")
        self.assertEqual(OrderEvent(action="custom_action").label, "custom_action")

        manager = User.objects.create_user("notif_manager", password="example-test-pass-862", is_staff=True)
        manager.groups.add(Group.objects.get_or_create(name="gerente")[0])
        order = Order.objects.create(
            token=uuid.uuid4(),
            owner="test-owner",
            mode="restaurante",
            destination={"table": "1"},
            payment="No restaurante",
            items=[],
            subtotal=1000,
            discount=0,
            fee=0,
            total=1000,
        )
        OrderEvent.objects.create(order=order, action="notified", actor=None, reason="")

        staff = Client()
        staff.force_login(manager)
        url = reverse("staff_detail", args=[order.pk])
        for target_url in (url, f"{url}?fragment=1"):
            with self.subTest(url=target_url):
                response = staff.get(target_url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Notificação enviada")
                self.assertNotContains(response, "· None")
