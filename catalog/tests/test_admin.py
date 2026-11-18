from django.contrib.auth.models import User
from django.urls import reverse

from catalog.models import Product
from catalog.tests.conftest import garment


def test_admin_cannot_delete_products(client, db):
    admin_user = User.objects.create_superuser("root", password="x")
    client.force_login(admin_user)
    product = garment("Blouse", "custom", 1800)

    page = client.get(reverse("admin:catalog_product_change", args=[product.pk]))
    assert page.status_code == 200
    assert reverse("admin:catalog_product_delete", args=[product.pk]) not in (
        page.content.decode()
    )

    url = reverse("admin:catalog_product_delete", args=[product.pk])
    assert client.post(url, {"post": "yes"}).status_code == 403

    response = client.post(
        reverse("admin:catalog_product_changelist"),
        {
            "action": "delete_selected",
            "_selected_action": [product.pk],
            "post": "yes",
        },
    )
    assert response.status_code in (200, 302)
    assert Product.objects.filter(pk=product.pk).exists()
