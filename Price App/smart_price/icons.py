"""Base64 encoded icons for use in the Streamlit UI.

The constants defined here are tiny 1\u00d71 pixel PNG images encoded as
base64 strings.  They are used by :func:`smart_price.streamlit_app.big_alert`
as fallbacks when no custom icon path is supplied.
"""

__all__ = [
    "SUCCESS_ICON_B64",
    "ERROR_ICON_B64",
    "WARNING_ICON_B64",
    "INFO_ICON_B64",
    "ICONS",
]

SUCCESS_ICON_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNg+M8AAAICAQB7CYF4AAAAAElFTkSuQmCC"
ERROR_ICON_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
WARNING_ICON_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4/58BAAT/Af9dfQKHAAAAAElFTkSuQmCC"
INFO_ICON_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYPgPAAEDAQAIicLsAAAAAElFTkSuQmCC"

ICONS = {
    "success": SUCCESS_ICON_B64,
    "error": ERROR_ICON_B64,
    "warning": WARNING_ICON_B64,
    "info": INFO_ICON_B64,
}
