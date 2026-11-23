from collections import Counter
from datetime import timedelta
from decimal import Decimal
from functools import wraps
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from . import staff_forms as forms
from .models import Category, Customer, Ingredient, MenuProduct, Order, OrderEvent, StockMovement, Table
from .operations import SECTIONS, access, actions, transition
from .storefront import restaurant

def restricted(section):
    def decorate(view):
        @wraps(view)
        @never_cache
        def checked(request, *args, **kwargs):
            request.scopes = access(request.user)
            if not request.user.is_authenticated:
                return redirect("staff_login")
            if section not in request.scopes:
                return HttpResponseForbidden("Seu perfil não tem acesso a esta operação.")
            return view(request, *args, **kwargs)
        return checked
    return decorate

@never_cache
def sign_in(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        key = "staff-login:" + request.META.get("REMOTE_ADDR", "")
        cache.add(key, 0, 300)
        if cache.incr(key) > 15:
            return render(request, "staff/login.html", {"form": form, "problem": "Aguarde alguns minutos para tentar novamente."}, status=429)
        if form.is_valid():
            user = form.get_user()
            scopes = access(user)
            if scopes:
                public = {key: value for key, value in request.session.items() if not key.startswith("_auth_")}
                login(request, user)
                request.session.update(public)
                landing = next(section for section in ("dashboard", "orders", "kitchen") if section in scopes)
                return redirect("staff_section", landing)
            form.add_error(None, "Credenciais inválidas para a equipe.")
    return render(request, "staff/login.html", {"form": form})

@require_POST
def sign_out(request):
    # Django logout clears its session. Keep the public cart and customer identity.
    public = {key: value for key, value in request.session.items() if not key.startswith("_auth_")}
    logout(request)
    request.session.update(public)
    return redirect("staff_login")

def layout(request, section, template="section", **data):
    return render(request, "staff/" + template + ".html", dict(
        section=section, title=SECTIONS[section], config=restaurant(),
        nav=[(key, value) for key, value in SECTIONS.items() if key in request.scopes],
        **data,
    ))

def completed(order):
    return order.stage == len(order.stages)-1

def metrics(records):
    stages = Counter(order.stage for order in records)
    durations = [(o.ready_at-o.accepted_at).total_seconds()/60 for o in records if o.ready_at and o.accepted_at]
    return dict(count=len(records), pending=stages[0], preparing=stages[1], ready=stages[2],
                completed=sum(completed(o) for o in records), rejected=stages[90], cancelled=stages[91],
                average=round(sum(durations)/len(durations),1) if durations else None)

def period(request):
    try:
        value = int(request.GET.get("days", "1"))
    except ValueError:
        value = 1
    return value if value in (1, 7, 30) else 1

def records():
    return Order.objects.select_related("customer", "accepted_by").order_by("-created")

def populate_board(request, kitchen=False):
    config = restaurant()
    since = timezone.localdate() - timedelta(days=period(request)-1)
    query = records()
    buckets = [("Novos pedidos", []), ("Em preparo", []), ("Prontos", []), ("Em entrega", []), ("Concluídos", []), ("Recusados e cancelados", [])]
    for order in query:
        stage = order.stage
        if kitchen and stage != 1:
            continue
        if stage >= 90 or completed(order):
            if timezone.localtime(order.created).date() < since:
                continue
            column = 5 if stage >= 90 else 4
        else:
            column = stage
        order.buttons = actions(order, request.scopes)
        order.waiting = stage == 0 and timezone.now()-order.created >= timedelta(minutes=config.alert_minutes)
        buckets[column][1].append(order)
    return [buckets[1]] if kitchen else buckets

def section(request, section):
    if section not in SECTIONS:
        return HttpResponseForbidden()
    scopes = access(request.user)
    if request.resolver_match.url_name == "staff_home" and scopes and section not in scopes:
        return redirect("staff_section", "orders" if "orders" in scopes else "kitchen")
    return restricted(section)(show)(request, section)

def show(request, section):
    if section in ("orders", "kitchen"):
        board = populate_board(request, section == "kitchen")
        return layout(request, section, "board", board=board, days=period(request))
    if section in ("dashboard", "reports"):
        days = period(request) if section == "reports" else 1
        since = timezone.localdate()-timedelta(days=days-1)
        entries = list(records().filter(created__date__gte=since))
        values = metrics(entries)
        receipts = list(records().filter(paid_at__date__gte=since))
        sales = Counter()
        modes = Counter(o.mode for o in entries)
        for order in entries:
            if completed(order):
                for item in order.items:
                    sales[item["name"]] += item["qty"]
        gross = sum(o.total for o in receipts)
        daily_receipts = Counter()
        for order in receipts:
            daily_receipts[timezone.localtime(order.paid_at).date()] += order.total
        revenue = [(date, daily_receipts[date]) for date in sorted(daily_receipts)]
        values.update(received=gross, ticket=gross//len(receipts) if receipts else None,
                      unpaid=sum(o.total for o in entries if not o.paid_at and o.stage < 90))
        return layout(request, section, "dashboard", entries=entries[:10], values=values,
                      days=days, sales=sales.most_common(8), modes=list(modes.items()),
                      revenue=revenue, revenue_max=max(daily_receipts.values(), default=1))
    if section == "customers":
        customers = Customer.objects.all().order_by("name")
        for person in customers:
            person.purchases = list(records().filter(customer=person))
        return layout(request, section, customers=customers)
    if section == "staff":
        form = forms.StaffForm(request.POST or None)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.is_staff = True
                user.is_superuser = form.cleaned_data["role"] == "admin"
                user.save()
                if not user.is_superuser:
                    group, _ = Group.objects.get_or_create(name=form.cleaned_data["role"])
                    user.groups.add(group)
            return redirect("staff_section", "staff")
        return layout(request, section, form=form, employees=User.objects.filter(is_staff=True).prefetch_related("groups"))
    if section == "settings":
        form = forms.RestaurantForm(request.POST or None, instance=restaurant())
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações salvas.")
            return redirect("staff_section", "settings")
        return layout(request, section, form=form)
    return manage(request, section)

MANAGEMENT = {
    "products": (MenuProduct, forms.ProductForm, "name"),
    "categories": (Category, forms.CategoryForm, "position"),
    "tables": (Table, forms.TableForm, "number"),
    "inventory": (Ingredient, forms.IngredientForm, "name"),
}

def manage(request, section):
    model, form_class, sort = MANAGEMENT[section]
    if section == "tables" and request.method == "POST" and "settings" not in request.scopes:
        return HttpResponseForbidden()
    if section == "products" and request.method == "POST" and "availability" in request.POST:
        value = request.POST["availability"]
        product_id = request.POST.get("product_id", "")
        if value not in {"on", "off"} or not product_id.isascii() or not product_id.isdigit() or len(product_id) > 15:
            raise Http404
        product = get_object_or_404(MenuProduct, pk=product_id, archived=False)
        MenuProduct.objects.filter(pk=product.pk, archived=False).update(available=value == "on")
        return redirect("staff_section", section)
    identifier = request.GET.get("edit")
    if identifier and (not identifier.isascii() or not identifier.isdigit() or len(identifier) > 15):
        raise Http404
    instance = get_object_or_404(model, pk=identifier) if identifier else None
    if request.method == "POST" and section == "inventory" and "movement" in request.POST and instance:
        movement = forms.MovementForm(request.POST)
        if movement.is_valid():
            data = movement.cleaned_data
            amount = data["amount"]
            delta = {"in": amount, "out": -amount, "set": amount-instance.quantity}[data["kind"]]
            new_balance = instance.quantity + delta
            if not 0 <= new_balance <= Decimal("999999999.999"):
                movement.add_error("amount", "O saldo resultante está fora do limite.")
            else:
                with transaction.atomic():
                    written = Ingredient.objects.filter(pk=instance.pk, quantity=instance.quantity).update(
                        quantity=F("quantity")+delta, updated=timezone.now())
                    if written:
                        StockMovement.objects.create(ingredient=instance, delta=delta, actor=request.user, reason=data["reason"])
                if written:
                    return redirect(request.path+"?edit="+str(instance.pk))
                movement.add_error(None, "O saldo mudou. Revise e tente novamente.")
        form = form_class(instance=instance)
    else:
        movement = forms.MovementForm()
        form = form_class(request.POST or None, instance=instance)
        if form.is_valid():
            form.save()
            return redirect("staff_section", section)
    entries = list(model.objects.order_by(sort))
    if section == "tables":
        by_number = {str(t.number): t for t in entries}
        by_id = {t.pk: t for t in entries}
        for table in entries:
            table.active_orders = []
        for order in records().filter(mode="restaurante", stage__lt=3):
            table = (by_id.get(order.destination["table_id"]) if "table_id" in order.destination
                     else by_number.get(str(order.destination.get("table"))))
            if table:
                table.active_orders.append(order)
        for table in entries:
            table.balance = sum(o.total for o in table.active_orders)
    return layout(request, section, form=form, entries=entries, selected=instance,
                  movement=movement, can_edit=section != "tables" or "settings" in request.scopes)

@never_cache
def board_fragment(request, section):
    if section not in ("orders", "kitchen"):
        return HttpResponseForbidden()
    return restricted(section)(fragment)(request, section)

def fragment(request, section):
    return render(request, "staff/columns.html", {"board": populate_board(request, section == "kitchen"), "section": section})

@restricted("orders")
def detail(request, pk):
    order = get_object_or_404(records().prefetch_related("events__actor"), pk=pk)
    if request.GET.get("fragment") == "1":
        return render(request, "staff/order_details.html", {
            "order": order, "show_private": "customers" in request.scopes,
            "buttons": actions(order, request.scopes),
        })
    return layout(request, "orders", "detail", order=order,
                  show_private="customers" in request.scopes, buttons=actions(order, request.scopes))

@require_POST
@never_cache
def change(request, pk):
    scopes = access(request.user)
    if not scopes.intersection({"orders", "kitchen"}):
        return HttpResponseForbidden()
    order = get_object_or_404(Order, pk=pk)
    action = request.POST.get("action")
    if action not in {"ready"} and "orders" not in scopes:
        return HttpResponseForbidden()
    if action == "ready" and "kitchen" not in scopes:
        return HttpResponseForbidden()
    try:
        expected = int(request.POST.get("stage", ""))
        if action == "paid":
            if "settings" not in scopes or not completed(order) or expected != order.stage:
                return HttpResponseForbidden()
            with transaction.atomic():
                if not Order.objects.filter(pk=pk, stage=expected, paid_at__isnull=True).update(paid_at=timezone.now()):
                    raise ValueError("Recebimento já registrado.")
                OrderEvent.objects.create(order=order, action="paid", actor=request.user)
        else:
            transition(order, action, request.user, request.POST.get("reason", "").strip(), expected)
        messages.success(request, "Pedido atualizado.")
    except ValueError as error:
        messages.error(request, str(error) or "Etapa inválida.")
    section = "kitchen" if "kitchen" in scopes and ("orders" not in scopes or request.POST.get("return") == "kitchen") else "orders"
    return redirect("staff_section", section)

@require_POST
@restricted("staff")
def toggle_staff(request, pk):
    user = get_object_or_404(User, pk=pk, is_staff=True)
    if user.pk == request.user.pk:
        return HttpResponseForbidden()
    User.objects.filter(pk=pk, is_active=user.is_active).update(is_active=not user.is_active)
    return redirect("staff_section", "staff")
