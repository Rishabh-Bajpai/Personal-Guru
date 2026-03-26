import pytest
import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


BOOK_COVER_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "modes" / "library" / "book_cover.py"
)
_book_cover_spec = spec_from_file_location("test_book_cover_module", BOOK_COVER_PATH)
_book_cover_module = module_from_spec(_book_cover_spec)
_book_cover_spec.loader.exec_module(_book_cover_module)

BookCoverService = _book_cover_module.BookCoverService
_normalize_server_address = _book_cover_module._normalize_server_address


pytestmark = pytest.mark.unit

TEST_COMFYUI_ADDRESS = os.environ.get(
    "COMFYUI_SERVER_ADDRESS", "http://example.com:8188/"
)


@pytest.mark.parametrize(
    ("raw_address", "expected"),
    [
        ("example.com:8188", ("http", "example.com:8188")),
        ("http://example.com:8188/", ("http", "example.com:8188")),
        ("https://example.com:9000", ("https", "example.com:9000")),
        ("localhost:8188/", ("http", "localhost:8188")),
        ("", ("http", "localhost:8188")),
    ],
)
def test_normalize_server_address(raw_address, expected):
    assert _normalize_server_address(raw_address) == expected


def test_normalize_server_address_rejects_unsupported_scheme():
    with pytest.raises(ValueError, match="Unsupported ComfyUI URL scheme"):
        _normalize_server_address("ftp://example.com:8188")


def test_book_cover_service_normalizes_server_address():
    service = BookCoverService(TEST_COMFYUI_ADDRESS, "scripts/example_workflow.json")

    expected_scheme, expected_server_address = _normalize_server_address(
        TEST_COMFYUI_ADDRESS
    )
    assert service.http_scheme == expected_scheme
    assert service.server_address == expected_server_address
