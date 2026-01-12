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
