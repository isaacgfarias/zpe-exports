import pandas as pd
import numpy as np
import streamlit as st


@st.cache_data
def calcular_vcr_ceara_brasil(df_comexstat):
    """Calcula o VCR (Vantagem Comparativa Revelada) do Ceará vs. Brasil."""
    df_comexstat_valid = df_comexstat[df_comexstat["metricFOB"] > 0].copy()
    df_comexstat_valid["headingCode"] = df_comexstat_valid["headingCode"].astype(str)

    X_total_brasil = df_comexstat_valid["metricFOB"].sum()
    df_ceara = df_comexstat_valid[df_comexstat_valid["state"] == "Ceará"].copy()
    X_total_ceara = df_ceara["metricFOB"].sum()

    if X_total_brasil == 0 or X_total_ceara == 0 or df_comexstat_valid.empty:
        return pd.DataFrame(columns=["headingCode", "VCR_Ceara_Brasil"])

    df_xi_ceara = df_ceara.groupby("headingCode")["metricFOB"].sum().reset_index()
    df_xi_ceara = df_xi_ceara.rename(columns={"metricFOB": "Xi_Ceara"})

    df_xi_brasil = (
        df_comexstat_valid.groupby("headingCode")["metricFOB"].sum().reset_index()
    )
    df_xi_brasil = df_xi_brasil.rename(columns={"metricFOB": "Xi_Brasil"})

    df_vcr = df_xi_ceara.merge(df_xi_brasil, on="headingCode", how="outer").fillna(0)

    parcela_ceara = df_vcr["Xi_Ceara"] / X_total_ceara
    parcela_brasil = df_vcr["Xi_Brasil"] / X_total_brasil

    df_vcr["VCR_Ceara_Brasil"] = np.where(
        parcela_brasil > 0, parcela_ceara / parcela_brasil, 0
    )

    return df_vcr[["headingCode", "VCR_Ceara_Brasil"]]


@st.cache_data
def calcular_vcr_dentro_selecao(df_comex_filtrado, df_comex_nacional):
    """
    Calcula o VCR local para o conjunto de estados selecionados,
    usando o contexto nacional ou o contexto do conjunto selecionado como base.
    """
    if df_comex_filtrado.empty:
        return pd.DataFrame(columns=["state", "headingCode", "heading", "VCR"])

    df_comex_filtrado = df_comex_filtrado.copy()
    df_comex_filtrado["headingCode"] = df_comex_filtrado["headingCode"].astype(str)

    selected_states = df_comex_filtrado["state"].unique()

    # 1. DEFINIÇÃO DA BASE DE COMPARAÇÃO
    if len(selected_states) == 1:
        df_base_comparacao = df_comex_nacional.copy()
    else:
        df_base_comparacao = df_comex_filtrado.copy()

    X_total_comparacao = df_base_comparacao["metricFOB"].sum()

    df_xi_comparacao = (
        df_base_comparacao.groupby("headingCode")["metricFOB"].sum().reset_index()
    )
    df_xi_comparacao = df_xi_comparacao.rename(columns={"metricFOB": "Xi_comparacao"})

    if X_total_comparacao == 0:
        df_comex_filtrado["VCR"] = 0.0
        return df_comex_filtrado[["state", "headingCode", "metricFOB", "VCR"]].copy()

    df_xi_comparacao["Tx_Global_Contexto"] = (
        df_xi_comparacao["Xi_comparacao"] / X_total_comparacao
    )

    # 2. CÁLCULO DO NUMERADOR DA VCR (Taxa Local)
    df_export_estado = (
        df_comex_filtrado.groupby(["state", "headingCode"])["metricFOB"]
        .sum()
        .reset_index()
    )

    df_export_total_estado = (
        df_comex_filtrado.groupby("state")["metricFOB"].sum().reset_index()
    )
    df_export_total_estado = df_export_total_estado.rename(
        columns={"metricFOB": "X_total_estado"}
    )

    df_vcr_calc = df_export_estado.merge(df_export_total_estado, on="state", how="left")
    df_vcr_calc = df_vcr_calc.merge(
        df_xi_comparacao[["headingCode", "Tx_Global_Contexto"]],
        on="headingCode",
        how="left",
    ).fillna(0)

    df_vcr_calc["Tx_Local"] = df_vcr_calc["metricFOB"] / df_vcr_calc["X_total_estado"]

    # 3. CÁLCULO FINAL
    df_vcr_calc["VCR"] = np.where(
        df_vcr_calc["Tx_Global_Contexto"] > 0,
        df_vcr_calc["Tx_Local"] / df_vcr_calc["Tx_Global_Contexto"],
        0.0,
    )

    df_result = df_vcr_calc[["state", "headingCode", "metricFOB", "VCR"]].copy()

    df_headings = df_comex_nacional[["headingCode", "heading"]].drop_duplicates()
    df_result = df_result.merge(df_headings, on="headingCode", how="left")

    return df_result[df_result["VCR"] > 0].sort_values(by="VCR", ascending=False)
