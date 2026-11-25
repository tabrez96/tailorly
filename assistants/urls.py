from django.urls import path

from assistants import views

urlpatterns = [
    path("settings/assistants/", views.assistants, name="assistants"),
    path("settings/assistants/set/", views.assistants_set, name="assistants_set"),
    path(
        "settings/assistants/keys/new/",
        views.assistant_key_new,
        name="assistant_key_new",
    ),
    path(
        "settings/assistants/keys/<int:pk>/revoke/",
        views.assistant_key_revoke,
        name="assistant_key_revoke",
    ),
]
