import pandas as pd
import streamlit as st


@st.cache_data
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
