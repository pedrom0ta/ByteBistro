from time import sleep
from django.db import OperationalError, connection, transaction
from django.utils import timezone
from .models import Order, OrderEvent
from .stock import confirm_reservations, release_reservations

ROLES = {
    "gerente": {"dashboard", "orders", "kitchen", "tables", "products", "categories", "inventory", "customers", "reports", "settings"},
    "atendente": {"orders", "tables"},
    "cozinha": {"kitchen"},
}
SECTIONS = dict(dashboard="Dashboard", orders="Pedidos", kitchen="Cozinha", tables="Mesas",
                products="Cardápio", categories="Categorias", inventory="Estoque",
                customers="Clientes", reports="Relatórios", staff="Funcionários", settings="Configurações")

def access(user):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        return set()
    if user.is_superuser:
        return set(SECTIONS)
    return set().union(*(ROLES.get(name, set()) for name in user.groups.values_list("name", flat=True)))

def actions(order, scopes):
    current = order.stage
    if current == 0 and "orders" in scopes:
        return {"accept": "Aceitar pedido", "reject": "Recusar pedido"}
    if current == 1 and "kitchen" in scopes:
        return {"ready": "Marcar como pronto"}
    if current == 2 and "orders" in scopes:
        return {"dispatch": "Saiu para entrega"} if order.mode == "delivery" else {"complete": "Entregar na mesa"}
    if current == 3 and order.mode == "delivery" and "orders" in scopes:
        return {"complete": "Confirmar entrega"}
    return {}

def transition(order, action, user, reason="", expected=None):
    scopes = access(user) if user is not None else {"orders", "kitchen"}
    allowed = actions(order, scopes)
    if "settings" in scopes and order.stage in (0, 1, 2, 3) and order.stage < len(order.stages)-1:
        allowed["cancel"] = "Cancelar pedido"
    if action not in allowed or (expected is not None and expected != order.stage):
        raise ValueError("Ação indisponível para a etapa atual.")
    if action in ("reject", "cancel") and not 1 <= len(reason) <= 300:
        raise ValueError("Informe um motivo de até 300 caracteres.")
    target = {"accept": 1, "ready": 2, "dispatch": 3, "complete": len(order.stages)-1, "reject": 90, "cancel": 91}[action]
    now = timezone.now()
    changes = {"stage": target}
    if action == "accept":
        changes.update(accepted_at=now, accepted_by=user)
    if action == "ready":
        changes["ready_at"] = now
    if action in ("reject", "cancel"):
        changes["reason"] = reason
    for attempt in range(4):
        try:
            with transaction.atomic():
                if not Order.objects.filter(pk=order.pk, stage=order.stage).update(**changes):
                    raise ValueError("Outro funcionário já atualizou este pedido.")
                OrderEvent.objects.create(order=order, action=action, actor=user, reason=reason)
                if action in ("reject", "cancel"):
                    release_reservations(order)
                elif action == "complete":
                    confirm_reservations(order)
            return
        except OperationalError as error:
            if connection.vendor != "sqlite" or "locked" not in str(error).lower():
                raise
            if attempt == 3:
                raise ValueError("Banco ocupado. Confira a etapa e tente novamente.") from error
            sleep(0.025 * (attempt + 1))

