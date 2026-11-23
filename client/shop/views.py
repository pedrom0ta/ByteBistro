import re
import time
from uuid import UUID
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.conf import settings
from django.views.decorators.http import require_POST
from .graphql import GraphQLUnavailable, order_status
from . import services, sms
from .catalog import normalize
from . import storefront
from .forms import Address, Registration
from .models import Customer

def page(request, template, **context):
    return render(request, template + ".html", context)

def home(request):
    products = list(storefront.products().filter(available=True).order_by("-discount", "id"))
    return page(request, "home", featured=products[0] if products else None, popular=products[1:4], categories=storefront.categories(), restaurant=storefront.restaurant())

def menu(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("cat", "")
    products = storefront.products().order_by("category__position", "id")
    if category:
        products = products.filter(category__name=category)
    matches = [p for p in products if normalize(query) in normalize(f"{p.name} {p.category} {p.description}")]
    return page(request, "menu", products=matches, categories=storefront.categories(), category=category, query=query)

def product(request, slug):
    p = get_object_or_404(storefront.products(), slug=slug)
    if request.method == "POST":
        try:
            services.add(request.session, p, request.POST)
            return redirect("cart")
        except ValueError as error:
            messages.error(request, str(error))
    return page(request, "product", p=p, focus=True, back=reverse("menu"))

def cart(request):
    lines = list(request.session.get("cart", []))
    if request.method == "POST":
        key = request.POST.get("key")
        try:
            if request.POST.get("remove"):
                lines = [line for line in lines if line["key"] != key]
            else:
                for line in lines:
                    if line["key"] == key:
                        line["qty"] = services.quantity(request.POST.get("qty"))
            services.change_cart(request.session, lines)
        except ValueError as error:
            messages.error(request, str(error))
        return redirect("cart")
    try:
        totals = services.summary(request.session)
    except ValueError as error:
        messages.error(request, str(error))
        return page(request, "cart", unavailable=lines)
    return page(request, "cart", **totals)

def mode(request):
    if not request.session.get("cart"):
        return redirect("cart")
    return page(request, "mode", focus=True, back=reverse("cart"), restaurant=storefront.restaurant())

def phone(request):
    if request.GET.get("next") in ("account", "delivery"):
        request.session["after_login"] = request.GET["next"]
    if services.customer(request.session):
        return redirect(request.session.get("after_login", "account"))
    if request.method == "POST":
        value = re.sub(r"[()\s-]", "", request.POST.get("phone", ""))
        try:
            if not re.fullmatch(r"[1-9][0-9]9[0-9]{8}", value):
                raise ValueError("Informe um celular com DDD e nove dígitos.")
            sms.issue(request, value)
            return redirect("verify")
        except ValueError as error:
            messages.error(request, str(error))
    return page(request, "auth", step="phone", focus=True, back=reverse("mode" if request.session.get("after_login") == "delivery" else "account"))

def verify(request):
    otp = request.session.get("otp")
    if not otp:
        return redirect("phone")
    if request.method == "POST":
        try:
            if "resend" in request.POST:
                sms.issue(request, otp["phone"])
                return redirect("verify")
            number = sms.verify(request.session, request.POST.get("code", ""))
            account = Customer.objects.filter(phone=number).first()
            if account:
                request.session["customer"] = account.pk
                return redirect(request.session.get("after_login", "account"))
            request.session["verified"] = [number, int(time.time())]
            return redirect("register")
        except ValueError as error:
            messages.error(request, str(error))
    return page(request, "auth", step="verify", otp=otp, wait=max(0, int(60-time.time()+otp["issued"])), focus=True, back=reverse("phone"))

def register(request):
    verified = request.session.get("verified")
    if not verified or time.time()-verified[1] > 900:
        return redirect("phone")
    form = Registration(request.POST if request.method == "POST" else None)
    if form.is_valid():
        account, _ = Customer.objects.get_or_create(phone=verified[0], defaults=form.cleaned_data)
        request.session["customer"] = account.pk
        request.session.pop("verified")
        return redirect(request.session.get("after_login", "account"))
    return page(request, "auth", step="register", phone=verified[0], form=form, focus=True, back=reverse("phone"))

def checkout(request, kind):
    session = request.session
    account = services.customer(session)
    if request.method == "POST":
        try:
            token = UUID(request.POST.get("token", ""))
        except ValueError:
            token = None
        existing = services.orders(session).filter(token=token).first()
        if existing:
            if session.get("token") == str(token):
                services.change_cart(session, [])
            return redirect("track", existing.id)
    if not session.get("cart"):
        return redirect("cart")
    delivery = kind == "delivery"
    config = storefront.restaurant()
    if not config.accepting or (delivery and not config.delivery):
        messages.error(request, "Esta modalidade está temporariamente indisponível.")
        return redirect("mode")
    if delivery and not account:
        return redirect(reverse("phone")+"?next=delivery")
    try:
        totals = services.summary(session)
    except ValueError:
        return redirect("cart")
    form = Address()
    saved = account.addresses if delivery else []
    selected = request.POST.get("address", "0" if saved else "new")
    if request.method == "POST":
        try:
            payment = "No restaurante"
            destination = {}
            notes = request.POST.get("notes", "").strip()
            if len(notes) > 300:
                raise ValueError("Use até 300 caracteres nas observações.")
            if delivery:
                payment = request.POST.get("payment")
                if selected == "new":
                    form = Address(request.POST)
                    if not form.is_valid():
                        raise ValueError("Confira os campos do endereço.")
                    destination = form.cleaned_data
                elif selected.isascii() and selected.isdigit() and len(selected)<8 and int(selected)<len(saved):
                    destination = saved[int(selected)]
                else:
                    raise ValueError("Selecione um endereço válido.")
                if payment not in config.payments:
                    raise ValueError("Selecione a forma de pagamento.")
            else:
                table = request.POST.get("table")
                if table not in {str(t.number) for t in storefront.tables()}:
                    raise ValueError("Selecione a mesa do pedido.")
                destination = {"table": table}
            order = services.confirm(session, request.POST.get("token"), kind, destination, payment, notes)
            return redirect("track", order.id)
        except ValueError as error:
            messages.error(request, str(error))
    fee = config.fee if delivery else 0
    return page(request, "checkout", delivery=delivery, form=form, saved=saved, selected=selected, payments=config.payments, tables=storefront.tables(), token=session.get("token"), fee=fee, final=totals["partial"]+fee, focus=True, back=reverse("mode"), **totals)

def history(request):
    return page(request, "history", orders=services.orders(request.session))

def tracking(request, pk, view="track"):
    if view == "status" and getattr(settings, "BYTEBISTRO_GRAPHQL_URL", None):
        try:
            status = order_status(pk, services.owner(request.session), request.session.get("customer"))
        except GraphQLUnavailable:
            response = JsonResponse({"error": "Acompanhamento temporariamente indisponível."}, status=503)
        else:
            if status is None:
                raise Http404
            response = JsonResponse(status)
        response["Cache-Control"] = "no-store"
        return response

    order = get_object_or_404(services.orders(request.session), pk=pk)
    if view == "status":
        response = JsonResponse(dict(stage=order.progress, status=order.status, finished=order.finished, reason=order.reason))
        response["Cache-Control"] = "no-store"
        return response
    if view == "done" and not order.finished:
        return redirect("track", pk)
    if view == "track" and order.finished and "detalhes" not in request.GET:
        return redirect("done", pk)
    return page(request, "done" if view == "done" else "track", order=order, focus=True, back=reverse("history"))

def account(request):
    return page(request, "account", user_data=services.customer(request.session), payments=storefront.restaurant().payments)

@require_POST
def logout(request):
    cart = request.session.get("cart", [])
    staff = {key: value for key, value in request.session.items() if key.startswith("_auth_")}
    request.session.flush()
    request.session.update(staff)
    services.change_cart(request.session, cart)
    return redirect("account")
