import os
os.environ["DATABASE_URL"]="sqlite+aiosqlite:///./test.db"
os.environ["HELPDESK_ALLOWED_HOSTS"]="mock-helpdesk,localhost,127.0.0.1"
os.environ["OPENAI_API_KEY"]=""
os.environ["FALLBACK_DELAY_SECONDS"]="5"
import pytest
from app.config import get_settings
@pytest.fixture(autouse=True)
def test_config():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
