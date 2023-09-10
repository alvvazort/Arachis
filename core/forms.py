from typing import Any, Mapping, Optional, Type, Union
from django import forms
from django.forms.utils import ErrorList
from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget

PAYMENT_CHOICES = (
    ('S', 'Stripe'),
    ('P', 'PayPal')
)


class CheckoutForm(forms.Form):
    street_address = forms.CharField(required=True ,widget=forms.TextInput(attrs={
        'placeholder': 'C/ Amor de Dios 123',
        'class': 'form-control'
    }))
    apartment_address = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Apartamento 123',
        'class': 'form-control'
    }))
    country = CountryField(blank_label='(Selecciona un pais)').formfield(widget=CountrySelectWidget(attrs={
        'class': 'custom-select d-block w-100'
    }))
    country.initial = 'ES'
    country.disabled = True
    city = forms.CharField(required=True, widget=forms.TextInput(attrs={
        'class': 'form-control'
    }))
    zip = forms.CharField(required=True, widget=forms.TextInput(attrs={
        'class': 'form-control'
    }))
    same_shipping_address = forms.BooleanField(widget=forms.CheckboxInput(attrs={
        'class': 'custom-checkbox'
    }), required=False, label="La dirección de facturación es la misma que la de entrega")
    same_shipping_address.initial = True
    #save_info = forms.BooleanField(required=False)
    '''
    payment_option = forms.ChoiceField(
        widget=forms.RadioSelect, choices=PAYMENT_CHOICES)
    '''

    street_address_billing = forms.CharField(required=False,widget=forms.TextInput(attrs={
        'placeholder': 'C/ Amor de Dios 123',
        'class': 'form-control'
    }))
    apartment_address_billing = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Apartamento 123',
        'class': 'form-control'
    }))
    country_billing = CountryField(blank_label='(Selecciona un pais)').formfield(widget=CountrySelectWidget(attrs={
        'class': 'custom-select d-block w-100'
    }))
    country_billing.initial = 'ES'
    country_billing.disabled = True
    city_billing = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control'
    }))
    zip_billing = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control'
    }))


class CouponForm(forms.Form):
    code = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Promo code'
    }))


class RefundForm(forms.Form):
    ref_code = forms.CharField()
    message = forms.CharField(widget=forms.Textarea(attrs={
        'rows': 4
    }))
    email = forms.EmailField()
