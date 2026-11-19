from django.urls import path

from orders import views

urlpatterns = [
    path("orders/photos/<int:pk>/", views.item_photo, name="item_photo"),
    path(
        "orders/photos/<int:pk>/thumb/",
        views.item_photo,
        {"size": "thumb"},
        name="item_photo_thumb",
    ),
]
