# Arquivo: analytics.py
import pandas as pd
import numpy as np
import streamlit as st


def format_fob_metric(value):
    if value >= 1e12:
        display = f"${value / 1e12:,.2f} Tri"
    elif value >= 1e9:
        display = f"${value / 1e9:,.2f} Bi"
    elif value >= 1e6:
        display = f"${value / 1e6:,.2f} Mi"
    else:
        display = f"${value:,.2f}"
    return display.replace(",", "_TEMP_").replace(".", ",").replace("_TEMP_", ".")


@st.cache_data
def calcular_vcr_ceara_brasil(df_comexstat):
    df_comexstat_valid = df_comexstat[df_comexstat["metricFOB"] > 0].copy()
    df_comexstat_valid["headingCode"] = df_comexstat_valid["headingCode"].astype(str)
    X_total_brasil = df_comexstat_valid["metricFOB"].sum()
    df_ceara = df_comexstat_valid[df_comexstat_valid["state"] == "Ceará"].copy()
    X_total_ceara = df_ceara["metricFOB"].sum()
    if X_total_brasil == 0 or X_total_ceara == 0 or df_comexstat_valid.empty:
        return pd.DataFrame(columns=["headingCode", "VCR_Ceara_Brasil"])
    df_xi_ceara = (
        df_ceara.groupby("headingCode")["metricFOB"]
        .sum()
        .reset_index()
        .rename(columns={"metricFOB": "Xi_Ceara"})
    )
    df_xi_brasil = (
        df_comexstat_valid.groupby("headingCode")["metricFOB"]
        .sum()
        .reset_index()
        .rename(columns={"metricFOB": "Xi_Brasil"})
    )
    df_vcr = df_xi_ceara.merge(df_xi_brasil, on="headingCode", how="outer").fillna(0)
    df_vcr["VCR_Ceara_Brasil"] = np.where(
        df_vcr["Xi_Brasil"] > 0,
        (df_vcr["Xi_Ceara"] / X_total_ceara) / (df_vcr["Xi_Brasil"] / X_total_brasil),
        0,
    )
    return df_vcr[["headingCode", "VCR_Ceara_Brasil"]]


@st.cache_data
def obter_vcr_brasil_mundo(df_harvard):
    df_vcr = df_harvard.rename(
        columns={"product_hs92_code": "headingCode", "export_rca": "VCR_Brasil_Mundo"}
    ).copy()
    df_vcr["headingCode"] = df_vcr["headingCode"].astype(str).str.zfill(4)
    return df_vcr.groupby("headingCode")["VCR_Brasil_Mundo"].mean().reset_index()


@st.cache_data
def obter_pci_e_distancia(df_harvard):
    df_metrics = df_harvard.rename(
        columns={
            "product_hs92_code": "headingCode",
            "pci": "PCI",
            "distance": "Distancia_Parceiros",
        }
    ).copy()
    df_metrics["headingCode"] = df_metrics["headingCode"].astype(str).str.zfill(4)
    return (
        df_metrics.groupby("headingCode")
        .agg({"PCI": "mean", "Distancia_Parceiros": "mean"})
        .reset_index()
    )


def normalizar_vcr(df: pd.DataFrame, coluna_vcr: str) -> pd.DataFrame:
    """
    Normaliza uma coluna específica e cria uma nova com o sufixo _NORM.
    """
    coluna_norm = coluna_vcr + "_NORM"

    # Garante que os dados sejam numéricos para o cálculo
    vcr_numeric = pd.to_numeric(df[coluna_vcr], errors="coerce")

    vcr_min = vcr_numeric.min()
    vcr_max = vcr_numeric.max()

    if vcr_max == vcr_min or pd.isna(vcr_min):
        df[coluna_norm] = 0.0
    else:
        df[coluna_norm] = (vcr_numeric - vcr_min) / (vcr_max - vcr_min)

    return df


def calcular_indice_prioridade_ajustado(df: pd.DataFrame, pesos: dict) -> pd.DataFrame:
    """
    Calcula o Índice de Prioridade SEM a métrica de VCR Ajustado.
    Utiliza VCR Estadual, Nacional, PCI e Distância.
    """
    df_calc = df.copy()

    # Recupera as colunas normalizadas (geradas individualmente no dashboard_tabs.py)
    vcr_ce_norm = df_calc.get("VCR_Ceara_Brasil_NORM", 0).fillna(0)
    vcr_br_norm = df_calc.get("VCR_Brasil_Mundo_NORM", 0).fillna(0)
    pci_norm = df_calc.get("PCI_NORM", 0).fillna(0)

    dist_norm = df_calc.get("Distancia_Parceiros_NORM", 0).fillna(0)
    proximidade_norm = 1 - dist_norm  # Inverte distância para proximidade

    # 1. Cálculo do sub-índice de VCR (Estadual + Nacional)
    peso_vcr_total = pesos["vcr_ceara"] + pesos["vcr_brasil"]

    if peso_vcr_total > 0:
        # Redistribui os pesos proporcionalmente apenas entre os dois VCRs existentes
        peso_vcr_ceara = pesos["vcr_ceara"] / peso_vcr_total
        peso_vcr_brasil = pesos["vcr_brasil"] / peso_vcr_total
        indice_vcr = (vcr_ce_norm * peso_vcr_ceara) + (vcr_br_norm * peso_vcr_brasil)
    else:
        indice_vcr = (vcr_ce_norm + vcr_br_norm) / 2

    # 2. Cálculo do Índice Final
    # O VCR Composto tem peso fixo de 1 na proporção com PCI e Distância
    peso_total_geral = 1 + pesos["pci"] + pesos["distancia"]

    peso_vcr_composto = 1 / peso_total_geral
    peso_pci = pesos["pci"] / peso_total_geral
    peso_distancia = pesos["distancia"] / peso_total_geral

    df_calc["INDICE_PRIORIDADE_AJUSTADO"] = (
        (indice_vcr * peso_vcr_composto)
        + (pci_norm * peso_pci)
        + (proximidade_norm * peso_distancia)
    )

    return df_calc


# def calcular_indice_prioridade_ajustado(df: pd.DataFrame, pesos: dict) -> pd.DataFrame:
#     """
#     Calcula o Índice de Prioridade Ajustado removendo a métrica de VCR Ajustado
#     conforme solicitado, focando em VCR Estadual, Nacional, PCI e Distância.
#     """
#     df_calc = df.copy()

#     # 1. Normalização das entradas para o cálculo
#     df_calc["VCR_CE_NORM"] = pd.to_numeric(
#         df_calc["VCR_Ceara_Brasil_NORM"], errors="coerce"
#     ).fillna(0)
#     df_calc["VCR_BR_NORM"] = pd.to_numeric(
#         df_calc["VCR_Brasil_Mundo_NORM"], errors="coerce"
#     ).fillna(0)

#     dist_norm = pd.to_numeric(
#         df_calc["Distancia_Parceiros_NORM"], errors="coerce"
#     ).fillna(0)
#     proximidade_norm = 1 - dist_norm  # Inverte distância para proximidade

#     # 2. Cálculo do sub-índice de VCR (Estadual + Nacional)
#     # Removemos o vcr_ajustado da soma e do cálculo
#     peso_vcr_total = pesos["vcr_ceara"] + pesos["vcr_brasil"]

#     if peso_vcr_total > 0:
#         peso_vcr_ceara = pesos["vcr_ceara"] / peso_vcr_total
#         peso_vcr_brasil = pesos["vcr_brasil"] / peso_vcr_total
#     else:
#         # Fallback caso os pesos de VCR sejam zero
#         peso_vcr_ceara = peso_vcr_brasil = 0.5

#     indice_vcr = (df_calc["VCR_CE_NORM"] * peso_vcr_ceara) + (
#         df_calc["VCR_BR_NORM"] * peso_vcr_brasil
#     )

#     # 3. Cálculo do Índice Final (VCR Composto + PCI + Proximidade)
#     # O VCR Composto tem peso fixo de 1 no denominador relativo
#     peso_total_geral = 1 + pesos["pci"] + pesos["distancia"]

#     peso_vcr_composto = 1 / peso_total_geral
#     peso_pci = pesos["pci"] / peso_total_geral
#     peso_distancia = pesos["distancia"] / peso_total_geral

#     df_calc["INDICE_PRIORIDADE_AJUSTADO"] = (
#         (indice_vcr * peso_vcr_composto)
#         + (df_calc["PCI_NORM"] * peso_pci)
#         + (proximidade_norm * peso_distancia)
#     )

#     return df_calc
