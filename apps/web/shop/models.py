import uuid
from django.conf import settings
from django.db import models

class Customer(models.Model):
    phone = models.CharField(max_length=11, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    addresses = models.JSONField(default=list)


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.UUIDField(unique=True)
    owner = models.CharField(max_length=64)
    customer = models.ForeignKey(Customer, null=True, on_delete=models.SET_NULL)
    mode = models.CharField(max_length=12)
    destination = models.JSONField()
    payment = models.CharField(max_length=40)
    notes = models.CharField(max_length=300, blank=True)
    items = models.JSONField()
    subtotal = models.PositiveIntegerField()
    discount = models.PositiveIntegerField()
    fee = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    stage = models.PositiveSmallIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True)
    ready_at = models.DateTimeField(null=True)
    paid_at = models.DateTimeField(null=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=300, blank=True)

    @property
    def number(self):
        return self.id.hex[:8].upper()

    @property
    def stages(self):
        delivery = ["Pronto para entrega", "Saiu para entrega"] if self.mode == "delivery" else ["Pronto"]
        return ["Pedido recebido", "Em preparo", *delivery, "Entregue"]

    @property
    def finished(self):
        return self.stage == len(self.stages) - 1 or (self.mode == "restaurante" and self.stage == 2)

    @property
    def status(self):
        if self.stage in (90, 91):
            return "Recusado" if self.stage == 90 else "Cancelado"
        return self.stages[self.stage]

    @property
    def progress(self):
        return 0 if self.stage >= 90 else self.stage


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, related_name="events", on_delete=models.CASCADE)
    action = models.CharField(max_length=24)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    @property
    def label(self):
        return {
            "received": "Pedido recebido",
            "accept": "Aceito · preparo iniciado",
            "ready": "Preparo concluído",
            "dispatch": "Saiu para entrega",
            "complete": "Entregue",
            "reject": "Recusado",
            "cancel": "Cancelado",
            "paid": "Recebimento registrado",
            "notified": "Notificação enviada",
        }.get(self.action, self.action)


class OrderOutbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True)
    notified_at = models.DateTimeField(null=True)
    lease_until = models.DateTimeField(null=True)
    lease_token = models.UUIDField(null=True)
    notify_lease_until = models.DateTimeField(null=True)
    notify_lease_token = models.UUIDField(null=True)

    class Meta:
        indexes = [models.Index(fields=["sent_at", "created_at"])]


class Category(models.Model):
    name = models.CharField("Nome", max_length=80, unique=True)
    position = models.PositiveIntegerField("Ordem", default=0)
    active = models.BooleanField("Ativa", default=True)

    def __str__(self):
        return self.name


class MenuProduct(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField("Nome", max_length=100)
    category = models.ForeignKey(Category, verbose_name="Categoria", on_delete=models.PROTECT)
    description = models.TextField("Descrição")
    price = models.PositiveIntegerField("Preço em centavos")
    discount = models.PositiveIntegerField("Desconto em centavos", default=0)
    image = models.CharField("Imagem local ou URL HTTPS", max_length=500, blank=True)
    available = models.BooleanField("Disponível", default=True)
    archived = models.BooleanField("Arquivado", default=False)
    prep_minutes = models.PositiveIntegerField("Preparo estimado em minutos", default=20)
    options = models.JSONField(default=list, blank=True)
    extras = models.JSONField(default=list, blank=True)

    @property
    def final(self):
        return self.price - self.discount

    @property
    def image_url(self):
        if self.image.startswith("https://"):
            return self.image
        return "/static/images/" + (self.image or "logo.webp")


class Table(models.Model):
    number = models.PositiveIntegerField("Número", unique=True)
    label = models.CharField("Identificação", max_length=60, blank=True)
    active = models.BooleanField("Disponível", default=True)
    qr_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    def __str__(self):
        return self.label or f"Mesa {self.number:02d}"


class Ingredient(models.Model):
    name = models.CharField("Insumo", max_length=100, unique=True)
    unit = models.CharField("Unidade", max_length=20)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    minimum = models.DecimalField("Estoque mínimo", max_digits=12, decimal_places=3, default=0)
    updated = models.DateTimeField(auto_now=True)

    @property
    def low(self):
        return self.quantity <= self.minimum


class StockMovement(models.Model):
    ingredient = models.ForeignKey(Ingredient, related_name="movements", on_delete=models.PROTECT)
    delta = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=300)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)


class Restaurant(models.Model):
    name = models.CharField("Estabelecimento", max_length=100, default="ByteBistro")
    logo = models.URLField("URL do logo", blank=True)
    address = models.CharField("Endereço", max_length=240, blank=True)
    phone = models.CharField("Telefone", max_length=25, blank=True)
    hours = models.CharField("Horários de funcionamento", max_length=240, blank=True)
    accepting = models.BooleanField("Aceitar pedidos", default=True)
    delivery = models.BooleanField("Delivery disponível", default=True)
    fee = models.PositiveIntegerField("Taxa de entrega em centavos", default=690)
    prep = models.PositiveIntegerField("Preparo estimado em minutos", default=20)
    payments = models.JSONField(default=list)
    alert_minutes = models.PositiveIntegerField("Alertar após minutos de espera", default=5)
    sound = models.BooleanField("Permitir alerta sonoro", default=False)
