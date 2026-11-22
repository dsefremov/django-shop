from django import forms


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(label="Имя и фамилия", max_length=150)
    customer_email = forms.EmailField(label="Эл. почта")
    customer_phone = forms.RegexField(
        label="Телефон",
        regex=r"^\+?[\d\s()\-]{10,20}$",
        max_length=32,
        error_messages={"invalid": "Укажите телефон, например +7 900 123-45-67."},
        widget=forms.TextInput(
            attrs={"type": "tel", "autocomplete": "tel", "placeholder": "+7 900 123-45-67"}
        ),
    )
    address = forms.CharField(
        label="Адрес доставки",
        max_length=255,
        widget=forms.TextInput(attrs={"autocomplete": "street-address"}),
    )
    comment = forms.CharField(
        label="Комментарий к заказу",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class PaymentForm(forms.Form):
    decision = forms.ChoiceField(choices=(("pay", "Оплатить"), ("decline", "Отказ")))
