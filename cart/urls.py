from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.CartView.as_view(), name="index"),
    path("add/<int:product_id>/", views.AddToCartView.as_view(), name="add"),
    path("update/<int:product_id>/", views.UpdateCartView.as_view(), name="update"),
    path("remove/<int:product_id>/", views.RemoveFromCartView.as_view(), name="remove"),
]
