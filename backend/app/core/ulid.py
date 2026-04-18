from ulid import ULID


def new_ulid() -> str:
    """Generate a new Crockford-Base32 encoded ULID (26 chars)."""
    return str(ULID())
