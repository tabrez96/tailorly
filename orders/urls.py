from django.urls import path

from orders import views

urlpatterns = [
    path("orders/", views.orders, name="orders"),
    path("orders/new/", views.draft_new, name="order_new"),
    path("orders/drafts/", views.draft_create, name="order_draft_create"),
    path("orders/drafts/<int:pk>/", views.draft, name="order_draft"),
    path(
        "orders/drafts/<int:pk>/customer/",
        views.draft_customer,
        name="order_draft_customer",
    ),
    path(
        "orders/drafts/<int:pk>/customer/search/",
        views.draft_customer_search,
        name="order_draft_customer_search",
    ),
    path(
        "orders/drafts/<int:pk>/customer/new/",
        views.draft_customer_add,
        name="order_draft_customer_add",
    ),
    path(
        "orders/drafts/<int:pk>/paid-by/",
        views.draft_paid_by,
        name="order_draft_paid_by",
    ),
    path(
        "orders/drafts/<int:pk>/queue-hint/",
        views.draft_queue_hint,
        name="order_draft_queue_hint",
    ),
    path(
        "orders/drafts/<int:pk>/place/",
        views.draft_place,
        name="order_draft_place",
    ),
    path("orders/<int:pk>/", views.order_detail, name="order"),
    path(
        "orders/<int:pk>/items/<int:item_pk>/",
        views.item_detail,
        name="order_item",
    ),
    path("orders/<int:pk>/payments/new/", views.payment_sheet, name="order_payment"),
    path(
        "orders/<int:pk>/invoice/send/",
        views.invoice_send,
        name="order_invoice_send",
    ),
    path("orders/<int:pk>/ready/", views.order_ready, name="order_ready"),
    path("orders/<int:pk>/deliver/", views.order_deliver, name="order_deliver"),
    path("orders/<int:pk>/edit/", views.order_edit, name="order_edit"),
    path(
        "orders/<int:pk>/edit/items/new/",
        views.order_edit_item_add,
        name="order_edit_item_add",
    ),
    path(
        "orders/<int:pk>/edit/items/<int:item_pk>/",
        views.order_edit_item,
        name="order_edit_item",
    ),
    path(
        "orders/<int:pk>/edit/items/<int:item_pk>/remove/",
        views.order_edit_item_remove,
        name="order_edit_item_remove",
    ),
    path(
        "orders/<int:pk>/items/<int:item_pk>/materials/new/",
        views.material_add,
        name="order_item_material_add",
    ),
    path(
        "orders/<int:pk>/items/<int:item_pk>/materials/<int:line_pk>/",
        views.material_edit,
        name="order_item_material",
    ),
    path(
        "orders/<int:pk>/items/<int:item_pk>/materials/<int:line_pk>/remove/",
        views.material_remove,
        name="order_item_material_remove",
    ),
    path(
        "orders/<int:pk>/items/<int:item_pk>/measurements/",
        views.item_measurements_sheet,
        name="order_item_measurements_sheet",
    ),
    path(
        "orders/<int:pk>/items/<int:item_pk>/photos/",
        views.item_photo_add,
        name="order_item_photo_add",
    ),
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
