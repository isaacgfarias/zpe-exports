import pandas as pd
from core.vcr_calculators import calcular_vcr_ceara_brasil
from core.metric_fetchers import obter_vcr_brasil_mundo, obter_pci_e_distancia
from core.normalization import normalizar_vcr
from core.priority_index import (
    calcular_vcr_ajustado,
    calcular_indice_prioridade_ajustado,
)


def process_comparison_data(comexstat_df, harvard_df, pesos_dict):
    """
    Processa todos os DataFrames para consolidar métricas, normalizá-las
    e calcular o Índice de Prioridade Ajustado.
    Responsabilidade Única: Pipeline de Processamento de Dados.
    """

    # 1. Obter Tabela de Referência
    df_referencia = comexstat_df[["headingCode", "heading"]].drop_duplicates()
    df_referencia = df_referencia.rename(columns={"heading": "Descrição"})
    # Filtro de códigos HS válidos (manter a lógica original)
    df_referencia = df_referencia[
        df_referencia["headingCode"].notna()
        & (df_referencia["headingCode"] != "0")
        & (df_referencia["headingCode"].str.len() > 1)
    ]

    # 2. Cálculo e obtenção das métricas
    df_vcr_ce_br = calcular_vcr_ceara_brasil(comexstat_df)
    df_vcr_br_md = obter_vcr_brasil_mundo(harvard_df)
    df_pci_dist = obter_pci_e_distancia(harvard_df)

    # 3. Consolidação dos DataFrames
    df_final = df_referencia.merge(df_vcr_ce_br, on="headingCode", how="left")
    df_final = df_final.merge(df_vcr_br_md, on="headingCode", how="left")
    df_final = df_final.merge(df_pci_dist, on="headingCode", how="left")

    # 4. Normalização e VCR Ajustado
    df_final = normalizar_vcr(df_final, "VCR_Ceara_Brasil")
    df_final = normalizar_vcr(df_final, "VCR_Brasil_Mundo")
    df_final = normalizar_vcr(df_final, "PCI")
    df_final = normalizar_vcr(df_final, "Distancia_Parceiros")
    df_final = calcular_vcr_ajustado(df_final)

    # 5. Cálculo do Índice de Prioridade Ajustado
    df_final = calcular_indice_prioridade_ajustado(df_final, pesos_dict)

    # 6. Renomear e Arredondar para a etapa de exibição (preparação do output)
    df_final = df_final.rename(
        columns={
            "headingCode": "Código HS",
            "VCR_Ceara_Brasil": "VCR estadual (Bruto)",
            "VCR_Ceara_Brasil_NORM": "VCR estadual normalizada",
            "VCR_Brasil_Mundo": "VCR país (Bruto)",
            "VCR_Brasil_Mundo_NORM": "VCR país normalizada",
            "Distancia_Parceiros": "distância entre parceiros (Bruto)",
            "Distancia_Parceiros_NORM": "distância entre parceiros normalizada",
            "PCI": "PCI (Bruto)",
            "PCI_NORM": "PCI normalizado",
            "VCR_AJUSTADO": "VCR Ajustado (Bruto)",
            "VCR_AJUSTADO_NORM": "VCR Ajustado normalizado",
            "INDICE_PRIORIDADE_AJUSTADO": "Índice de Prioridade Ajustado",
        }
    )

    cols_to_process = [
        "VCR estadual (Bruto)",
        "VCR país (Bruto)",
        "VCR estadual normalizada",
        "VCR país normalizada",
        "distância entre parceiros (Bruto)",
        "PCI (Bruto)",
        "VCR Ajustado (Bruto)",
        "VCR Ajustado normalizado",
        "PCI normalizado",
        "distância entre parceiros normalizada",
        "Índice de Prioridade Ajustado",
    ]

    for col in cols_to_process:
        # Apenas arredonda (não trata NaN para string aqui, o que mantém a coluna como float)
        df_final[col] = pd.to_numeric(df_final[col], errors="coerce").round(3)

    return df_final
