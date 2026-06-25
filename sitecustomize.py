from pathlib import Path


def _repair_app_source():
    path = Path(__file__).with_name("app.py")
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    original = text

    def indent_len(s):
        return len(s) - len(s.lstrip(" "))

    # Remove empty duplicated mobile guards left by previous runtime patches.
    for _ in range(20):
        lines = text.splitlines(True)
        out = []
        changed = False
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped == "if not is_mobile_client():":
                current_indent = indent_len(line)
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                if j >= len(lines):
                    changed = True
                    i += 1
                    continue
                next_line = lines[j]
                next_indent = indent_len(next_line)
                # Empty if: next real line is not indented under it, or is another identical if.
                if next_line.strip() == "if not is_mobile_client():" or next_indent <= current_indent:
                    changed = True
                    i += 1
                    continue
            out.append(line)
            i += 1
        text = "".join(out)
        if not changed:
            break

    # Repair the specific broken variants seen in Streamlit Cloud.
    text = text.replace(
        "    if not is_mobile_client():\n    if not is_mobile_client():\n        st.dataframe(per, use_container_width=True, hide_index=True)\n",
        "    if not is_mobile_client():\n        st.dataframe(per, use_container_width=True, hide_index=True)\n",
    )
    text = text.replace(
        "    if not is_mobile_client():\n    st.dataframe(per, use_container_width=True, hide_index=True)\n",
        "    if not is_mobile_client():\n        st.dataframe(per, use_container_width=True, hide_index=True)\n",
    )

    # Remove the riskiest mobile stop block if it was duplicated.
    while text.count("    archive_mobile_html(df)\n    if is_mobile_client():\n        return\n") > 1:
        text = text.replace("    archive_mobile_html(df)\n    if is_mobile_client():\n        return\n", "", 1)

    if text != original:
        path.write_text(text, encoding="utf-8")


try:
    _repair_app_source()
except Exception:
    pass
