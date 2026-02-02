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


def normalizar_vcr(df, coluna):
    """
    Implementa a lógica das colunas M, N, O e P do .ods:
    Formula: ((Valor - Min) / (Max - Min))
    """
    min_val = df[coluna].min()
    max_val = df[coluna].max()

    # Evita divisão por zero caso todos os valores sejam iguais
    if max_val == min_val:
        df[f"{coluna}_norm"] = 0.0
    else:
        df[f"{coluna}_norm"] = (df[coluna] - min_val) / (max_val - min_val)

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


@st.cache_data
def carregar_mapeamento_ncm_cnae(file_path: str):
    """
    Carrega e limpa a tabela de correspondência NCM x CNAE.
    Lida com o formato específico do CSV (pula cabeçalho, limpa strings).
    """
    try:
        # Pula a primeira linha de título e lê os cabeçalhos reais
        df_map = pd.read_csv(file_path, skiprows=1)

        # Renomeia colunas para facilitar o acesso
        df_map.columns = ["ncm8_raw", "ncm_descricao", "cnae_raw"]

        # 1. Limpeza do NCM: remove .0, preenche com zeros à esquerda (8 dígitos)
        df_map["ncm8"] = (
            df_map["ncm8_raw"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.zfill(8)
        )

        # 2. Extração do SH4 (Prefixos)
        df_map["sh4"] = df_map["ncm8"].str[:4]

        # 3. Limpeza da CNAE: Remove pontos e lida com múltiplos códigos (explode)
        # Ex: "0151.2; 0152.1" vira duas linhas
        df_map["cnae_list"] = df_map["cnae_raw"].astype(str).str.split(";")
        df_map = df_map.explode("cnae_list")
        df_map["cnae7"] = (
            df_map["cnae_list"].str.replace(r"[\. -]", "", regex=True).str.strip()
        )

        # Remove códigos inválidos (como XXXX ou SEM TEC)
        df_map = df_map[df_map["cnae7"].str.isnumeric()]

        return df_map[["ncm8", "sh4", "ncm_descricao", "cnae7"]]
    except Exception as e:
        st.error(f"Erro ao carregar mapeamento NCM/CNAE: {e}")
        return pd.DataFrame()


def filtrar_mapeamento_por_cliente(
    df_map, ncm_exportados_cliente: list, cnaes_cliente: list = None
):
    """
    Refina o mapeamento para os NCMs que o cliente de fato opera
    e opcionalmente filtra pelas CNAEs registradas no CNPJ dele.
    """
    # Filtra pelos NCMs reais da operação
    df_filtered = df_map[df_map["ncm8"].isin(ncm_exportados_cliente)]

    # Se fornecido, filtra pelas CNAEs do cliente (estratégia de Direct Mapping)
    if cnaes_cliente:
        df_filtered = df_filtered[df_filtered["cnae7"].isin(cnaes_cliente)]

    return df_filtered


def classificar_cenarios_vcr(df):
    """
    Classifica os produtos em IDs de Cenário (1 a 7).
    Mantém as descrições oficiais disponíveis para referência.
    """
    # Dicionário mapeando os IDs para as descrições Ipsis Verbis
    descricoes_oficiais = {
        "Cenário 1": "Setores com Vantagem Comparativa no Ceará e no Brasil",
        "Cenário 2": "Setores com Vantagem Comparativa apenas no Ceará",
        "Cenário 3": "Setores com Vantagem Comparativa apenas no Brasil",
        "Cenário 4": "Setores com Potencial de Vantagem Comparativa no Ceará e no Brasil",
        "Cenário 5": "Setores com Potencial de Vantagem Comparativa apenas no Ceará",
        "Cenário 6": "Setores com Potencial de Vantagem Comparativa apenas no Brasil",
        "Cenário 7": "Setores sem Vantagem Comparativa ou Potencial de Vantagem",
    }

    def definir_id(row):
        vce = row.get("VCR_Ceara_Brasil", 0)
        vbr = row.get("VCR_Brasil_Mundo", 0)

        # Lógica de Quadrantes VCR >= 1.0
        if vce >= 1 and vbr >= 1:
            return "Cenário 1"
        if vce >= 1 and vbr < 1:
            return "Cenário 2"
        if vce < 1 and vbr >= 1:
            return "Cenário 3"

        # Lógica de Potencial 0.5 <= VCR < 1.0
        if 0.5 <= vce < 1 and 0.5 <= vbr < 1:
            return "Cenário 4"
        if 0.5 <= vce < 1 and vbr < 0.5:
            return "Cenário 5"
        if vce < 0.5 and 0 < vbr:
            return "Cenário 6"

        return "Cenário 7"

    df["Cenário ID"] = df.apply(definir_id, axis=1)
    # Criamos esta coluna apenas para consulta se necessário,
    # a visualização usará o 'Cenário ID'
    df["Cenário Descrição"] = df["Cenário ID"].map(descricoes_oficiais)

    return df


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
