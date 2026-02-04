#!/usr/bin/env python3
import gettext
import logging
import os

# Constants
DOMAIN = "big-digi-cam"
LOCALEDIR = "/usr/share/locale"

# Development localedir check
# utils/i18n.py -> utils -> root -> locale
dev_localedir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "locale",
)

if os.path.isdir(dev_localedir):
    LOCALEDIR = dev_localedir

def setup_i18n():
    """Setup internationalization."""
    try:
        gettext.bindtextdomain(DOMAIN, LOCALEDIR)
        gettext.textdomain(DOMAIN)
        return gettext.gettext
    except Exception as e:
        print(f"Failed to setup i18n: {e}")
        return lambda s: s

_ = setup_i18n()
