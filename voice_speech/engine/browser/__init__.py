"""
Riva Browser Engine Package
===========================
Target-isolated DOM inspection and browser automation.
"""
from .dom_inspector import inspect_browser_tab, DOMInspector, send_browser_draft

__all__ = ["inspect_browser_tab", "DOMInspector", "send_browser_draft"]
