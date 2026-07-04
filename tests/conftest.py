"""
pytest-playwright configuration.
Sets browser options for all generated tests.

base_url is provided automatically by pytest-base-url (included with pytest-playwright).
Use: pytest --base-url https://the-internet.herokuapp.com
"""

import pytest


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "ignore_https_errors": True,
        "viewport": {"width": 1280, "height": 720},
    }
