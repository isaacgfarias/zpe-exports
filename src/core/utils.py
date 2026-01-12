import streamlit as st


def format_fob_metric(value):
    """
    Formata um valor numérico para uma string no formato monetário (US$)
    com sufixos Mi, Bi, ou Tri, utilizando vírgula como separador decimal.
    """
    if value >= 1e12:
        display = f"${value / 1e12:,.2f} Tri"
    elif value >= 1e9:
        display = f"${value / 1e9:,.2f} Bi"
    elif value >= 1e6:
        display = f"${value / 1e6:,.2f} Mi"
    else:
        display = f"${value:,.2f}"

    # Ajuste de formatação (troca . por , para decimal e , por . para milhar)
    return display.replace(",", "_TEMP_").replace(".", ",").replace("_TEMP_", ".")


def abbreviate_metric(value):
    if value >= 1e12:
        display = f"{value / 1e12:,.2f} Tri"
    elif value >= 1e9:
        display = f"{value / 1e9:,.2f} Bi"
    elif value >= 1e6:
        display = f"{value / 1e6:,.2f} Mi"
    else:
        display = f"{value:,.2f}"

    # Ajuste de formatação (troca . por , para decimal e , por . para milhar)
    return display.replace(",", "_TEMP_").replace(".", ",").replace("_TEMP_", ".")
