import pytest
from django.http import QueryDict

from customers.listing import add_initial, parse_query, search_filter
from customers.models import Customer


def test_parse_query():
    assert parse_query(QueryDict("q=%20mee%20")) == "mee"
    assert parse_query(QueryDict("")) == ""
    assert len(parse_query(QueryDict("q=" + "a" * 200))) == 80


@pytest.mark.django_db
def test_search_filter_name_and_phone():
    Customer.objects.create(name="Meera Iyer", phone="9845022110")
    Customer.objects.create(name="Arjun Pillai", phone="9900177345")

    def found(q):
        return [c.name for c in Customer.objects.filter(search_filter(q))]

    assert found("mee") == ["Meera Iyer"]
    assert found("22110") == ["Meera Iyer"]
    assert found("+91 98450 22110") == ["Meera Iyer"]
    assert found("+91 98450") == ["Meera Iyer"]
    assert found("+9198450") == ["Meera Iyer"]
    assert found("91") == []
    assert found("990") == ["Arjun Pillai"]
    assert found("zzz") == []


def test_add_initial():
    assert add_initial("98450 22110") == {"phone": "9845022110"}
    assert add_initial(" Zed ") == {"name": "Zed"}
    assert add_initial("") == {}
