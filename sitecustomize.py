import builtins

builtins.APP_TITLE = "Prenotazioni Pilates Reformer"


def status_icon(status):
    return {"Confermata": "✅", "Lista attesa": "⏳", "Annullata": "❌"}.get(status, "")


builtins.status_icon = status_icon
