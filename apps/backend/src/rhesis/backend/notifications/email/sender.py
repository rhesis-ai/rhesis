"""The From header for outgoing mail.

The address always comes from configuration (``FROM_EMAIL``, ``WELCOME_FROM_EMAIL``). The
name is the recipient organization's branded product name when it has one
(``crud.organization.get_product_name``), so a white-labelled organization's mail arrives
under its own name. Without one the configured value is used as written, so an operator's
``"Name" <address>`` keeps its name and a bare address goes out bare.
"""

from email.utils import formataddr, parseaddr
from typing import Optional


def sender_with_name(configured: str, display_name: Optional[str]) -> str:
    """``configured`` under ``display_name``, or ``configured`` as written without one."""
    if not display_name:
        return configured
    _, address = parseaddr(configured)
    # Quotes and escapes the name as needed, and encodes a non-ASCII one.
    return formataddr((display_name, address))
