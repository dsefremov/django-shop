from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("orders/", views.OrderListView.as_view(), name="list"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="detail"),
    path("orders/<int:pk>/pay/", views.PayOrderView.as_view(), name="pay"),
    path("orders/<int:pk>/cancel/", views.CancelOrderView.as_view(), name="cancel"),
]
