try:
    import streamlit as st

    _OriginalSetPageConfig = st.set_page_config

    HEADER_NAV_CSS = """
    <style>
    .block-container {
        padding-top: 1.15rem !important;
        padding-bottom: 2rem !important;
        max-width: 1240px !important;
    }

    div[data-testid="stHorizontalBlock"]:has(h1) {
        background: linear-gradient(135deg, #f8fbf8 0%, #eef6f1 100%) !important;
        border: 1px solid #dfe8df !important;
        border-radius: 26px !important;
        padding: 22px 28px !important;
        margin: 6px 0 18px 0 !important;
        box-shadow: 0 10px 30px rgba(36, 49, 66, 0.07) !important;
        align-items: center !important;
    }

    div[data-testid="stHorizontalBlock"]:has(h1) img {
        max-height: 150px !important;
        width: auto !important;
        object-fit: contain !important;
        filter: drop-shadow(0 6px 10px rgba(36, 49, 66, 0.10));
    }

    div[data-testid="stHorizontalBlock"]:has(h1) h1 {
        font-size: clamp(2.35rem, 4vw, 3.25rem) !important;
        font-weight: 850 !important;
        line-height: 1.02 !important;
        letter-spacing: -0.035em !important;
        margin-bottom: 0.35rem !important;
        color: #243142 !important;
    }

    div[data-testid="stHorizontalBlock"]:has(h1) [data-testid="stCaptionContainer"] {
        font-size: 1.05rem !important;
        color: #6f7780 !important;
    }

    div[data-testid="stRadio"] {
        margin-top: 0.15rem !important;
        margin-bottom: 0.55rem !important;
    }

    div[data-testid="stRadio"] > div {
        gap: 0.65rem !important;
        flex-wrap: wrap !important;
    }

    div[data-testid="stRadio"] label {
        min-height: 44px !important;
        padding: 0.58rem 1.02rem !important;
        border-radius: 999px !important;
        border: 1px solid #dce6dc !important;
        background: #ffffff !important;
        box-shadow: 0 3px 10px rgba(36, 49, 66, 0.045) !important;
        transition: all 0.16s ease !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 0.45rem !important;
    }

    div[data-testid="stRadio"] label:hover {
        transform: translateY(-1px) !important;
        border-color: #496744 !important;
        background: #f2f8f3 !important;
        box-shadow: 0 6px 16px rgba(36, 49, 66, 0.08) !important;
    }

    div[data-testid="stRadio"] label p {
        color: #243142 !important;
        font-size: 0.98rem !important;
        font-weight: 650 !important;
        margin: 0 !important;
    }

    div[data-testid="stRadio"] input[type="radio"] {
        display: none !important;
    }

    div[data-testid="stRadio"] label:has(input:checked) {
        background: #496744 !important;
        border-color: #496744 !important;
        color: #ffffff !important;
        box-shadow: 0 7px 18px rgba(73, 103, 68, 0.22) !important;
    }

    div[data-testid="stRadio"] label:has(input:checked) p {
        color: #ffffff !important;
    }

    hr {
        margin-top: 0.85rem !important;
        margin-bottom: 1.35rem !important;
        border-top: 1px solid #e2eae2 !important;
    }
    </style>
    """

    def set_page_config_with_header_style(*args, **kwargs):
        result = _OriginalSetPageConfig(*args, **kwargs)
        try:
            st.markdown(HEADER_NAV_CSS, unsafe_allow_html=True)
        except Exception:
            pass
        return result

    st.set_page_config = set_page_config_with_header_style
except Exception:
    pass
