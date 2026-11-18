from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.phones import is_valid_phone, normalize_phone
from accounts.roles import OWNER, add_to_role


class Command(BaseCommand):
    help = "Create the owner account (first setup)."

    def add_arguments(self, parser):
        parser.add_argument("--phone", required=True)
        parser.add_argument("--name", required=True)

    def handle(self, *args, phone, name, **options):
        User = get_user_model()
        phone = normalize_phone(phone)
        if not is_valid_phone(phone):
            raise CommandError("Enter a 10-digit phone number.")
        if User.objects.filter(username=phone).exists():
            raise CommandError("An account with that phone number already exists.")
        password = getpass("Password: ")
        if password != getpass("Password (again): "):
            raise CommandError("Passwords don't match.")
        try:
            validate_password(password, User(username=phone, first_name=name))
        except ValidationError as e:
            raise CommandError(" ".join(e.messages)) from e
        with transaction.atomic():
            user = User.objects.create_user(
                username=phone, password=password, first_name=name
            )
            add_to_role(user, OWNER)
        self.stdout.write(f"Owner account created for {phone}.")
