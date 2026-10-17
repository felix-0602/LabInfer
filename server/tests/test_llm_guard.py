import pytest

from app.llm import OutboundError, validate_outbound_url


@pytest.mark.parametrize("url", [
    "http://api.example.com/v1/chat/completions",
    "https://localhost/v1/chat/completions",
    "https://127.0.0.1/v1/chat/completions",
    "https://192.168.1.1/v1/chat/completions",
    "https://10.0.0.5/v1/chat/completions",
    "https://[::1]/v1/chat/completions",
])
def test_rejects_non_public_or_plain_http(url):
    with pytest.raises(OutboundError):
        validate_outbound_url(url)
