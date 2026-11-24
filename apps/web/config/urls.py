from django.urls import path
from shop import views as v
from shop import staff_views as staff

urlpatterns = [
    path("painel/", staff.section, {"section": "dashboard"}, name="staff_home"),
    path("painel/entrar/", staff.sign_in, name="staff_login"),
    path("painel/sair/", staff.sign_out, name="staff_logout"),
    path("painel/pedido/<uuid:pk>/", staff.detail, name="staff_detail"),
    path("painel/pedido/<uuid:pk>/alterar/", staff.change, name="staff_change"),
    path("painel/funcionario/<int:pk>/alternar/", staff.toggle_staff, name="staff_toggle"),
    path("painel/<slug:section>/atualizar/", staff.board_fragment, name="staff_fragment"),
    path("painel/<slug:section>/", staff.section, name="staff_section"),
    path("", v.home, name="home"),
    path("cardapio/", v.menu, name="menu"),
    path("produto/<slug:slug>/", v.product, name="product"),
    path("carrinho/", v.cart, name="cart"),
    path("modalidade/", v.mode, name="mode"),
    path("restaurante/", v.checkout, {"kind": "restaurante"}, name="restaurant"),
    path("delivery/", v.checkout, {"kind": "delivery"}, name="delivery"),
    path("telefone/", v.phone, name="phone"),
    path("verificar/", v.verify, name="verify"),
    path("cadastro/", v.register, name="register"),
    path("pedidos/", v.history, name="history"),
    path("pedidos/<uuid:pk>/", v.tracking, name="track"),
    path("pedidos/<uuid:pk>/status/", v.tracking_status, name="status"),
    path("pedidos/<uuid:pk>/conclusao/", v.tracking, {"view":"done"}, name="done"),
    path("conta/", v.account, name="account"),
    path("sair/", v.logout, name="logout"),
]
