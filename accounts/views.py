from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView, LogoutView

from accounts.forms import SIGN_IN_ERROR, SignInForm
from accounts.roles import home_url, role_for
from core.pages import render_page


class SignInView(LoginView):
    template_name = "accounts/sign_in.html"
    authentication_form = SignInForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or home_url(role_for(self.request.user))

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form), status=422)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        extra = {"class": "field__input"}
        if form.errors:
            extra |= {"aria-invalid": "true", "aria-describedby": "signin-error"}
        context["username_input"] = form["username"].as_widget(attrs=extra)
        context["password_input"] = form["password"].as_widget(attrs=extra)
        context["sign_in_error"] = SIGN_IN_ERROR
        return context


class SignOutView(LogoutView):
    next_page = "sign_in"


@login_required
def change_password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    form.fields["old_password"].label = "Current password"
    form.fields["new_password1"].label = "New password"
    form.fields["new_password2"].label = "New password again"
    saved, status = False, 200
    if request.method == "POST":
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            form = PasswordChangeForm(request.user)
            saved = True
        else:
            status = 422
    context = {
        "title": "Change password",
        "form": form,
        "saved": saved,
        "back_url": home_url(role_for(request.user)),
    }
    return render_page(request, "accounts/change_password.html", context, status=status)


change_password.required_role = "any"
