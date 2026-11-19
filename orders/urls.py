from django.urls import path

from orders import views

urlpatterns = [
    path("orders/drafts/", views.draft_create, name="order_draft_create"),
    path("orders/drafts/<int:pk>/", views.draft, name="order_draft"),
    path("orders/drafts/<int:pk>/items/new/", views.item_add, name="order_item_add"),
    path(
        "orders/drafts/<int:pk>/items/<int:item_pk>/",
        views.item_edit,
        name="order_item_edit",
    ),
    path(
        "orders/drafts/<int:pk>/items/<int:item_pk>/remove/",
        views.item_remove,
        name="order_item_remove",
    ),
    path(
        "orders/drafts/<int:pk>/items/<int:item_pk>/measurements/",
        views.item_measurements,
        name="order_item_measurements",
    ),
    path(
        "orders/drafts/<int:pk>/photos/",
        views.item_photo_upload,
        name="order_photo_upload",
    ),
    path("orders/photos/<int:pk>/", views.item_photo, name="item_photo"),
    path(
        "orders/photos/<int:pk>/thumb/",
        views.item_photo,
        {"size": "thumb"},
        name="item_photo_thumb",
    ),
]
