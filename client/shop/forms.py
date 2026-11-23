from django import forms
from .services import PAYMENTS

class Registration(forms.Form):
    name = forms.CharField(label="Nome completo", max_length=100, min_length=3)
    email = forms.EmailField(label="E-mail (opcional)", required=False)

class Address(forms.Form):
    cep = forms.RegexField(r"^\d{5}-?\d{3}$", label="CEP", max_length=9,
                           widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "postal-code"}))
    street = forms.CharField(label="Rua", max_length=120)
    number = forms.CharField(label="Número", max_length=12)
    district = forms.CharField(label="Bairro", max_length=80)
    city = forms.CharField(label="Cidade", max_length=80)
    state = forms.ChoiceField(label="Estado", choices=[("", "Selecione")] + [(s,s) for s in "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()])
    extra = forms.CharField(label="Complemento (opcional)", required=False, max_length=100)
    reference = forms.CharField(label="Referência (opcional)", required=False, max_length=100)
