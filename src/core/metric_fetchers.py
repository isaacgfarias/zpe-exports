import pandas as pd
import streamlit as st


@st.cache_data
def obter_vcr_brasil_mundo(df_harvard):
    """Processa o DataFrame de Harvard para obter o VCR Brasil vs. Mundo por HS4."""
    df_vcr = df_harvard.rename(
        columns={"product_hs92_code": "headingCode", "export_rca": "VCR_Brasil_Mundo"}
    ).copy()

    df_vcr["headingCode"] = df_vcr["headingCode"].astype(str).str[:4]

    df_vcr = df_vcr.groupby("headingCode")["VCR_Brasil_Mundo"].mean().reset_index()

    return df_vcr


@st.cache_data
def obter_pci_e_distancia(df_harvard):
    """Processa o DataFrame de Harvard para obter PCI e Distância por HS4."""
    df_metrics = df_harvard.rename(
        columns={
            "product_hs92_code": "headingCode",
            "pci": "PCI",
            "distance": "Distancia_Parceiros",
        }
    ).copy()

    df_metrics["headingCode"] = df_metrics["headingCode"].astype(str).str[:4]

    df_metrics = (
        df_metrics.groupby("headingCode")
        .agg({"PCI": "mean", "Distancia_Parceiros": "mean"})
        .reset_index()
    )

    return df_metrics
