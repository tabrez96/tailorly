from django.urls import path

from accounts.views import SignInView, SignOutView, change_password

urlpatterns = [
    path("sign-in/", SignInView.as_view(), name="sign_in"),
    path("sign-out/", SignOutView.as_view(), name="sign_out"),
    path("account/password/", change_password, name="change_password"),
]
