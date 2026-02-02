import pandas as pd
import numpy as np

# Importação relativa para usar 'normalizar_vcr' de outro módulo 'core'
from .normalization import normalizar_vcr


def calcular_vcr_ajustado(df_metrics: pd.DataFrame) -> pd.DataFrame:
    """Calcula o VCR Ajustado, ponderando VCR Ceará/Brasil com PCI para produtos complexos."""
    df = df_metrics.copy()
    vcr_ce_br = pd.to_numeric(df["VCR_Ceara_Brasil"], errors="coerce").fillna(0)
    pci = pd.to_numeric(df["PCI"], errors="coerce").fillna(0)

    # Lógica de ajuste: se VCR > 1 e PCI existe, faz a média simples (placeholder original)
    df["VCR_AJUSTADO"] = np.where(
        (vcr_ce_br > 1) & (pci.notna()),
        (vcr_ce_br + pci) / 2,
        vcr_ce_br,
    )
    df = normalizar_vcr(df, "VCR_AJUSTADO")
    return df


def calcular_indice_prioridade_ajustado(df, pesos):
    """
    Calcula o índice final seguindo a lógica das colunas X, Y, Z, AA do .ods.
    Multiplica os valores normalizados (Min-Max) pelos pesos definidos.
    """
    # Criamos uma cópia para não gerar avisos de SettingWithCopy
    df_calc = df.copy()

    # Mapeamento das colunas normalizadas (garantindo que existam)
    # Se a coluna não existir, cria-se uma série de zeros com o mesmo index do DF
    vcr_ce_norm = (
        df_calc["VCR_Ceara_Brasil_norm"]
        if "VCR_Ceara_Brasil_norm" in df_calc.columns
        else 0
    )
    vcr_br_norm = (
        df_calc["VCR_Brasil_Mundo_norm"]
        if "VCR_Brasil_Mundo_norm" in df_calc.columns
        else 0
    )
    pci_norm = df_calc["PCI_norm"] if "PCI_norm" in df_calc.columns else 0
    dist_norm = (
        df_calc["Distancia_Parceiros_norm"]
        if "Distancia_Parceiros_norm" in df_calc.columns
        else 0
    )

    # Lógica das colunas X, Y, Z, AA do .ods
    df_calc["X"] = vcr_ce_norm * pesos.get("vcr_ceara", 0)
    df_calc["Y"] = vcr_br_norm * pesos.get("vcr_brasil", 0)
    df_calc["Z"] = pci_norm * pesos.get("pci", 0)
    df_calc["AA"] = dist_norm * pesos.get("distancia", 0)

    # Soma final (Coluna AC do .ods / Ranking da Planilha8)
    df_calc["INDICE_PRIORIDADE_AJUSTADO"] = (
        df_calc["X"] + df_calc["Y"] + df_calc["Z"] + df_calc["AA"]
    )

    return df_calc
