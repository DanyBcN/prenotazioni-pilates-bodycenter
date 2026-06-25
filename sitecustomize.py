from pathlib import Path
import re


def _repair_app_source():
    path = Path(__file__).with_name("app.py")
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    original = text

    # 1) Remove all broken Python mobile-control fragments created by previous runtime patches.
    patterns = [
        r'(?m)^    sync_mobile_mode\(\)\n',
        r'(?m)^    archive_mobile_html\(df\)\n',
        r'(?m)^    if is_mobile_client\(\):\n        return\n',
        r'(?m)^    if not is_mobile_client\(\):\n(?=    if not is_mobile_client\(\):)',
        r'(?m)^    if not is_mobile_client\(\):\n(?!        )',
    ]
    for pat in patterns:
        text = re.sub(pat, '', text)

    # 2) Fix the specific duplicated/empty if variants seen in Streamlit Cloud.
    text = text.replace(
        "    if not is_mobile_client():\n    if not is_mobile_client():\n        st.dataframe(per, use_container_width=True, hide_index=True)\n",
        "    st.dataframe(per, use_container_width=True, hide_index=True)\n",
    )
    text = text.replace(
        "    if not is_mobile_client():\n    st.dataframe(per, use_container_width=True, hide_index=True)\n",
        "    st.dataframe(per, use_container_width=True, hide_index=True)\n",
    )

    # 3) Hide broken/duplicate helper functions if present by neutralizing only their use, not inserting new Python control flow.
    text = text.replace("import streamlit.components.v1 as components\n", "")

    # 4) Add one safe CSS rule only: mobile hides tables/components; desktop hides mobile cards.
    css_safe = '''
    .mobile-archive { display:none !important; }
    @media (max-width:760px) {
        .mobile-archive { display:block !important; }
        div[data-testid="stCustomComponentV1"],
        div[data-testid="stDataFrame"],
        div[data-testid="stDataEditor"],
        .ag-root-wrapper,
        .ag-theme-streamlit {
            display:none !important;
            height:0 !important;
            max-height:0 !important;
            overflow:hidden !important;
        }
    }
    @media (min-width:761px) {
        .mobile-archive { display:none !important; }
    }
'''
    if '.mobile-archive' not in text:
        text = text.replace('    .stApp { background: #fbfcfb; }\n', '    .stApp { background: #fbfcfb; }\n' + css_safe)

    # 5) Keep simple stable archive ordering by client if possible.
    text = text.replace(
        'return df.sort_values(["_sort", "Ora", "Cliente"]).drop(columns=["_sort"]).reset_index(drop=True)',
        'return df.sort_values(["Cliente", "_sort", "Ora"]).drop(columns=["_sort"]).reset_index(drop=True)',
    )

    # 6) Remove duplicate JsCode imports if previous patches created them.
    text = text.replace(', JsCode, JsCode', ', JsCode')

    if text != original:
        path.write_text(text, encoding="utf-8")


try:
    _repair_app_source()
except Exception:
    pass
