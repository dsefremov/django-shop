from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.CatalogView.as_view(), name="index"),
    path("catalog/<slug:slug>/", views.CatalogView.as_view(), name="category"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="product"),
]
