from decimal import Decimal
import re
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Category, Ingredient, MenuProduct, ProductIngredient, Restaurant, Table

PAYMENTS = ["Pix", "Cartão de crédito", "Cartão de débito", "Dinheiro"]

class ProductForm(forms.ModelForm):
    options_text = forms.CharField(label="Personalizações, uma por linha", required=False, widget=forms.Textarea)
    extras_text = forms.CharField(label="Adicionais, um por linha (nome | centavos)", required=False, widget=forms.Textarea)

    class Meta:
        model = MenuProduct
        exclude = ["options", "extras"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["options_text"].initial = "\n".join(self.instance.options)
        self.fields["extras_text"].initial = "\n".join(f"{name} | {price}" for name, price in self.instance.extras)

    def clean(self):
        data = super().clean()
        if data.get("discount", 0) > data.get("price", 0):
            self.add_error("discount", "O desconto deve caber no preço.")
        image = data.get("image", "")
        if image and not (re.fullmatch(r"[\w.-]+\.(?:jpg|jpeg|png|webp)", image, re.I) or re.fullmatch(r"https://[^\s]+", image)):
            self.add_error("image", "Informe um nome de imagem local ou uma URL HTTPS.")
        self.instance.options = list(dict.fromkeys(line.strip() for line in data.get("options_text", "").splitlines() if line.strip()))
        extras = {}
        for line in data.get("extras_text", "").splitlines():
            if not line.strip():
                continue
            name, sep, price = line.partition("|")
            if not name.strip() or not sep or not re.fullmatch(r"[0-9]{1,8}", price.strip()):
                self.add_error("extras_text", "Use nome | preço em centavos.")
                break
            extras[name.strip()] = int(price)
        self.instance.extras = list(extras.items())
        return data

class ProductIngredientForm(forms.ModelForm):
    class Meta:
        model = ProductIngredient
        fields = ["ingredient", "quantity_per_unit"]

    def clean_quantity_per_unit(self):
        value = self.cleaned_data["quantity_per_unit"]
        if value <= Decimal("0"):
            raise forms.ValidationError("Informe uma quantidade positiva.")
        return value


ProductIngredientFormSet = forms.inlineformset_factory(
    MenuProduct,
    ProductIngredient,
    form=ProductIngredientForm,
    extra=2,
    can_delete=True,
)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = "__all__"

class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        fields = ["number", "label", "active"]

class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ["name", "unit", "minimum"]

    def clean_minimum(self):
        value = self.cleaned_data["minimum"]
        if value < 0:
            raise forms.ValidationError("Informe um mínimo não negativo.")
        return value

class MovementForm(forms.Form):
    kind = forms.ChoiceField(label="Operação", choices=[("in", "Entrada"), ("out", "Saída"), ("set", "Ajustar saldo")])
    amount = forms.DecimalField(label="Quantidade", min_value=0, max_digits=12, decimal_places=3)
    reason = forms.CharField(label="Justificativa", max_length=300)

class RestaurantForm(forms.ModelForm):
    payments = forms.MultipleChoiceField(label="Métodos na entrega", choices=[(v, v) for v in PAYMENTS], widget=forms.CheckboxSelectMultiple, required=False)

    class Meta:
        model = Restaurant
        fields = "__all__"

    def clean(self):
        data = super().clean()
        if data.get("delivery") and not data.get("payments"):
            self.add_error("payments", "Selecione ao menos um método para delivery.")
        return data

class StaffForm(UserCreationForm):
    role = forms.ChoiceField(label="Perfil", choices=[("gerente", "Gerente"), ("atendente", "Atendente"), ("cozinha", "Cozinha"), ("admin", "Administrador")])

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name"]
