import pytest
import os
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("bleach", MagicMock())

from app.modes.library.book_cover import BookCoverService, _normalize_server_address


pytestmark = pytest.mark.unit

TEST_COMFYUI_ADDRESS = os.environ.get(
    "COMFYUI_SERVER_ADDRESS", "http://example.com:8188/"
)


@pytest.mark.parametrize(
    ("raw_address", "expected"),
    [
        ("example.com:8188", "example.com:8188"),
        ("http://example.com:8188/", "example.com:8188"),
        ("https://example.com:9000", "example.com:9000"),
        ("localhost:8188/", "localhost:8188"),
        ("", "localhost:8188"),
    ],
)
def test_normalize_server_address(raw_address, expected):
    assert _normalize_server_address(raw_address) == expected


def test_book_cover_service_normalizes_server_address():
    service = BookCoverService(TEST_COMFYUI_ADDRESS, "scripts/example_workflow.json")

    assert service.server_address == _normalize_server_address(TEST_COMFYUI_ADDRESS)
