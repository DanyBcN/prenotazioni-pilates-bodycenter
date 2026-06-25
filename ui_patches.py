import base64
from pathlib import Path

import streamlit as st

_PATCHED = False


def _logo_data_uri():
    path = Path("assets/logo.png")
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def apply_ui_patches():
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    original_columns = st.columns
    original_image = st.image
    original_markdown = st.markdown
    original_caption = st.caption
    original_radio = st.radio

    state = {"skip_logo": False, "skip_caption": False}

    class NoopColumn:
        def __enter__(self):
            return st
        def __exit__(self, exc_type, exc, tb):
            return False

    def inject_css():
        original_markdown(
            """
            <style>
            .block-container {
                padding-top: 1.0rem !important;
                padding-bottom: 2rem !important;
                max-width: 1240px !important;
            }
            .stApp { background: #f9fbf9 !important; }
            .bodycenter-hero {
                display: flex;
                align-items: center;
                gap: 28px;
                width: 100%;
                box-sizing: border-box;
                background: linear-gradient(135deg, #f8fbf8 0%, #eef6f1 100%);
                border: 1px solid #dfe8df;
                border-radius: 26px;
                padding: 22px 28px;
                margin: 4px 0 18px 0;
                box-shadow: 0 10px 30px rgba(36,49,66,0.07);
            }
            .bodycenter-hero-logo {
                width: 128px;
                height: 128px;
                object-fit: contain;
                filter: drop-shadow(0 6px 10px rgba(36,49,66,0.10));
                flex: 0 0 auto;
            }
            .bodycenter-hero-title {
                margin: 0;
                color: #243142;
                font-size: clamp(2.25rem, 4vw, 3.15rem);
                font-weight: 850;
                line-height: 1.02;
                letter-spacing: -0.035em;
            }
            .bodycenter-hero-subtitle {
                margin: 8px 0 0 0;
                color: #6f7780;
                font-size: 1.06rem;
            }
            div[data-testid="stRadio"] { margin-top: 0.1rem !important; margin-bottom: 0.55rem !important; }
            div[data-testid="stRadio"] > div { gap: 0.65rem !important; flex-wrap: wrap !important; }
            div[data-testid="stRadio"] label {
                min-height: 44px !important;
                padding: 0.58rem 1.02rem !important;
                border-radius: 999px !important;
                border: 1px solid #dce6dc !important;
                background: #ffffff !important;
                box-shadow: 0 3px 10px rgba(36,49,66,0.045) !important;
                transition: all 0.16s ease !important;
                display: inline-flex !important;
                align-items: center !important;
            }
            div[data-testid="stRadio"] label:hover {
                transform: translateY(-1px) !important;
                border-color: #496744 !important;
                background: #f2f8f3 !important;
                box-shadow: 0 6px 16px rgba(36,49,66,0.08) !important;
            }
            div[data-testid="stRadio"] label p {
                color: #243142 !important;
                font-size: 0.98rem !important;
                font-weight: 650 !important;
                margin: 0 !important;
            }
            div[data-testid="stRadio"] input[type="radio"] { display: none !important; }
            div[data-testid="stRadio"] label:has(input:checked) {
                background: #496744 !important;
                border-color: #496744 !important;
                box-shadow: 0 7px 18px rgba(73,103,68,0.22) !important;
            }
            div[data-testid="stRadio"] label:has(input:checked) p { color: #ffffff !important; }
            hr {
                margin-top: 0.85rem !important;
                margin-bottom: 1.35rem !important;
                border-top: 1px solid #e2eae2 !important;
            }
            @media (max-width: 760px) {
                .bodycenter-hero { flex-direction: column; align-items: flex-start; gap: 16px; padding: 18px; }
                .bodycenter-hero-logo { width: 96px; height: 96px; }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def columns_patched(spec, *args, **kwargs):
        if spec == [1, 6] or spec == (1, 6):
            state["skip_logo"] = True
            return [NoopColumn(), NoopColumn()]
        return original_columns(spec, *args, **kwargs)

    def image_patched(*args, **kwargs):
        if state["skip_logo"] and kwargs.get("width") == 130:
            return None
        return original_image(*args, **kwargs)

    def markdown_patched(body, *args, **kwargs):
        if isinstance(body, str) and "Prenotazioni Pilates Reformer" in body and "<h1" in body:
            inject_css()
            logo = _logo_data_uri()
            logo_html = f'<img class="bodycenter-hero-logo" src="{logo}" alt="Body Center logo" />' if logo else ""
            state["skip_logo"] = False
            state["skip_caption"] = True
            return original_markdown(
                f"""
                <div class="bodycenter-hero">
                    {logo_html}
                    <div>
                        <h1 class="bodycenter-hero-title">Prenotazioni Pilates Reformer</h1>
                        <p class="bodycenter-hero-subtitle">Gestionale interno Body Center · clienti, prenotazioni, pagamenti</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return original_markdown(body, *args, **kwargs)

    def caption_patched(body, *args, **kwargs):
        if state["skip_caption"] and isinstance(body, str) and "Gestionale interno Body Center" in body:
            state["skip_caption"] = False
            return None
        return original_caption(body, *args, **kwargs)

    def radio_patched(*args, **kwargs):
        inject_css()
        return original_radio(*args, **kwargs)

    st.columns = columns_patched
    st.image = image_patched
    st.markdown = markdown_patched
    st.caption = caption_patched
    st.radio = radio_patched
