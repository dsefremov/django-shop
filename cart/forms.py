from typing import Any

from django import forms
from django.core.validators import MaxValueValidator

from catalog.models import Product


class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(label="Количество", min_value=1, initial=1)

    def __init__(self, *args: Any, product: Product | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if product is not None and product.stock > 0:
            field = self.fields["quantity"]
            field.validators.append(MaxValueValidator(product.stock))
            field.widget.attrs["max"] = product.stock


class UpdateCartForm(forms.Form):
    quantity = forms.IntegerField(label="Количество", min_value=0)
