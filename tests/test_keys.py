from contribution_art.keys import read_key, arrows_available


def test_no_tty_returns_none():
    # Under pytest stdin is not a TTY, so no blocking read may happen.
    assert read_key() is None
    assert arrows_available() is False
