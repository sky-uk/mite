from acurl import CaseInsensitiveDict


def test_case_insensitive_constructor():
    # Expect it to lower keys on return
    my_dict = CaseInsensitiveDict({"Foo": "Bar", "baz": "Qux"})
    assert list(my_dict.keys()) == ["foo", "baz"]


def test_case_insensitive_get():
    my_dict = CaseInsensitiveDict({"Foo": "Bar"})
    assert my_dict.get("Foo") == "Bar"
    assert my_dict.get("foo") == "Bar"


def test_case_insensitive_get_item():
    my_dict = CaseInsensitiveDict({"Foo": "Bar"})
    assert my_dict["Foo"] == "Bar"
    assert my_dict["foo"] == "Bar"


def test_case_insensitive_set_item():
    my_dict = CaseInsensitiveDict()
    my_dict["Foo"] = "Bar"
    assert my_dict["Foo"] == "Bar"
    assert my_dict["foo"] == "Bar"
    my_dict["foo"] = "Bar"
    assert my_dict["Foo"] == "Bar"
    assert my_dict["foo"] == "Bar"


def test_case_insensitive_del_item():
    my_dict = CaseInsensitiveDict({"Foo": "Bar", "baz": "Qux"})
    del my_dict["Foo"]
    assert list(my_dict.keys()) == ["baz"]
    del my_dict["Baz"]
    assert not list(my_dict.keys())


def test_case_insensitive_contains():
    my_dict = CaseInsensitiveDict({"Foo": "Bar"})
    assert "Foo" in my_dict
    assert "foo" in my_dict


def test_case_insensitive_pop():
    my_dict = CaseInsensitiveDict({"Foo": "Bar", "baz": "Qux"})
    assert my_dict.pop("Foo") == "Bar"
    assert my_dict.pop("Baz") == "Qux"
    assert not list(my_dict.keys())


def test_case_insensitive_popitem():
    my_dict = CaseInsensitiveDict({"Foo": "Bar", "Baz": "Qux"})
    assert my_dict.popitem() == ("baz", "Qux")
    assert list(my_dict.keys()) == ["foo"]


def test_case_insensitive_setdefault():
    my_dict = CaseInsensitiveDict({"Foo": "Bar"})
    assert my_dict.setdefault("Foo") == "Bar"
    assert my_dict.setdefault("foo") == "Bar"
    assert my_dict.setdefault("Baz", "Qux") == "Qux"
    assert my_dict.setdefault("baz") == "Qux"
