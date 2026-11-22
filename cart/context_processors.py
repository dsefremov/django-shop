from django.http import HttpRequest

from .cart import Cart


def cart(request: HttpRequest) -> dict[str, int]:
    return {"cart_count": Cart(request).count()}
