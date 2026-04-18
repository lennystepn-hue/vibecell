from app.core.ulid import new_ulid


def test_new_ulid_is_26_char_crockford() -> None:
    result = new_ulid()

    assert isinstance(result, str)
    assert len(result) == 26
    # Crockford-Base32 alphabet (no I, L, O, U)
    allowed = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert set(result).issubset(allowed)


def test_ulids_are_monotonic_in_time() -> None:
    first = new_ulid()
    second = new_ulid()

    # ULIDs are lexicographically sortable by time component
    assert first < second or first[:10] == second[:10]


def test_ulids_are_unique() -> None:
    values = {new_ulid() for _ in range(1000)}
    assert len(values) == 1000
