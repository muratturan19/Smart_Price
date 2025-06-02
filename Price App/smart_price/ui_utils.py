"""UI helper functions shared across Streamlit apps."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:  # pragma: no cover - hint for type checkers
    import streamlit as st

from . import config


def img_to_base64(path: Union[Path, str]) -> str:
    """Return base64 string for the image at ``path`` or URL."""
    if isinstance(path, (str, Path)) and str(path).startswith("http"):
        import requests

        resp = requests.get(str(path))
        resp.raise_for_status()
        data = resp.content
    else:
        with open(Path(path), "rb") as img_file:
            data = img_file.read()

    return base64.b64encode(data).decode("utf-8")


def logo_overlay(
    path: Union[Path, str],
    *,
    top: str | None = None,
    right: str | None = None,
    width: str = "clamp(80px,12vw,150px)",
    opacity: float | None = None,
    tooltip: str | None = None,
) -> None:
    """Render a floating logo overlay in the Streamlit app."""

    import streamlit as st

    encoded = img_to_base64(path)
    css_top = top or config.LOGO_TOP
    css_right = right or config.LOGO_RIGHT
    css_opacity = opacity if opacity is not None else config.LOGO_OPACITY
    title_attr = f' title="{tooltip}"' if tooltip else ""
    st.markdown(
        f"""
        <style>
            .top-right-logo {{
                position: fixed;
                top: {css_top};
                right: {css_right};
                width: {width};
                opacity: {css_opacity};
                z-index: 1000;
                pointer-events: none;
            }}
        </style>
        <img class="top-right-logo" src="data:image/png;base64,{encoded}"{title_attr} />
        """,
        unsafe_allow_html=True,
    )
