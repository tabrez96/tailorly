from django.contrib.auth.forms import AuthenticationForm

from accounts.phones import normalize_phone

SIGN_IN_ERROR = "That phone number and password don't match. Check both and try again."


class SignInForm(AuthenticationForm):
    error_messages = {"invalid_login": SIGN_IN_ERROR, "inactive": SIGN_IN_ERROR}

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Phone number"
        self.fields["username"].max_length = 20
        self.fields["username"].widget.attrs.update(
            {"inputmode": "tel", "autocomplete": "username", "autocapitalize": "none"}
        )
        self.fields["password"].widget.attrs.update(
            {"autocomplete": "current-password"}
        )

    def clean_username(self):
        return normalize_phone(self.cleaned_data["username"])
