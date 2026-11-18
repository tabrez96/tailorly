import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

STRONG = "correct-horse-staple-9"


def run(monkeypatch, phone="98450 12345", *passwords):
    answers = iter(passwords or (STRONG, STRONG))
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
    monkeypatch.setattr(
        "accounts.management.commands.create_owner.getpass",
        lambda prompt="": next(answers),
    )
    call_command("create_owner", phone=phone, name="Shop owner")


def test_creates_owner(monkeypatch, db):
    run(monkeypatch)
    user = User.objects.get(username="9845012345")
    assert user.first_name == "Shop owner"
    assert user.groups.filter(name="owner").exists()
    assert not user.is_staff and not user.is_superuser
    assert authenticate(username="9845012345", password=STRONG) == user


def test_duplicate_phone(monkeypatch, db):
    run(monkeypatch)
    with pytest.raises(CommandError, match="already exists"):
        run(monkeypatch)


def test_invalid_phone(monkeypatch, db):
    with pytest.raises(CommandError, match="10-digit"):
        run(monkeypatch, "12345")


def test_password_mismatch(monkeypatch, db):
    with pytest.raises(CommandError, match="match"):
        run(monkeypatch, "98450 12345", STRONG, "other")
    assert not User.objects.exists()


def test_weak_password(monkeypatch, db):
    with pytest.raises(CommandError):
        run(monkeypatch, "98450 12345", "123", "123")
    assert not User.objects.exists()


def test_password_similar_to_phone(monkeypatch, db):
    with pytest.raises(CommandError, match="too similar"):
        run(monkeypatch, "98450 12345", "9845012345ab", "9845012345ab")
    assert not User.objects.exists()


def test_role_failure_leaves_no_user(monkeypatch, db):
    def boom(user, role):
        raise RuntimeError("boom")

    monkeypatch.setattr("accounts.management.commands.create_owner.add_to_role", boom)
    with pytest.raises(RuntimeError):
        run(monkeypatch)
    assert not User.objects.exists()
