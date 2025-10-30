# %%
import polars as pl
import streamlit as st
import plotly.express as px
import os
import pandas as pd
import numpy as np  # Adicionado para operações numéricas robustas

# Nota: As classes ComexStat, Comtrade e HarvardDataverse foram mantidas na importação
from comexstat import Comexstat
from comtrade import Comtrade
from dataverse import HarvardDataverse

# --- Funções Auxiliares de Formatação e Cálculo ---


def format_fob_metric(value):
    """
    Formata um valor numérico para uma string no formato monetário (US$)
    com sufixos Mi (Milhões), Bi (Bilhões) ou Tri (Trilhões),
    utilizando vírgula como separador decimal.
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


@st.cache_data
def calcular_vcr_ceara_brasil(df_comexstat):
    """
    Calcula o VCR (Vantagem Comparativa Revelada) do Ceará em relação ao Brasil
    para cada 'headingCode' (setor i), utilizando o Valor FOB (metricFOB).
    """
    # Filtrar dados válidos e garantir coerência de tipos
    df_comexstat_valid = df_comexstat[df_comexstat["metricFOB"] > 0].copy()
    df_comexstat_valid["headingCode"] = df_comexstat_valid["headingCode"].astype(str)

    # 1. Total das exportações (FOB) para o Brasil e Ceará
    X_total_brasil = df_comexstat_valid["metricFOB"].sum()
    df_ceara = df_comexstat_valid[df_comexstat_valid["state"] == "Ceará"].copy()
    X_total_ceara = df_ceara["metricFOB"].sum()

    if X_total_brasil == 0 or X_total_ceara == 0 or df_comexstat_valid.empty:
        # Retorna estrutura vazia se não houver dados válidos para cálculo
        return pd.DataFrame(columns=["headingCode", "VCR_Ceara_Brasil"])

    # 2. Exportações por setor no Ceará (Xi_Ceara)
    df_xi_ceara = df_ceara.groupby("headingCode")["metricFOB"].sum().reset_index()
    df_xi_ceara = df_xi_ceara.rename(columns={"metricFOB": "Xi_Ceara"})

    # 3. Exportações por setor no Brasil (Xi_Brasil)
    df_xi_brasil = (
        df_comexstat_valid.groupby("headingCode")["metricFOB"].sum().reset_index()
    )
    df_xi_brasil = df_xi_brasil.rename(columns={"metricFOB": "Xi_Brasil"})

    # 4. Junção dos dados
    df_vcr = df_xi_ceara.merge(df_xi_brasil, on="headingCode", how="outer").fillna(0)

    # 5. Cálculo da VCR
    parcela_ceara = df_vcr["Xi_Ceara"] / X_total_ceara
    parcela_brasil = df_vcr["Xi_Brasil"] / X_total_brasil

    # Uso de np.where para evitar divisão por zero de forma robusta e vetorial
    df_vcr["VCR_Ceara_Brasil"] = np.where(
        parcela_brasil > 0, parcela_ceara / parcela_brasil, 0
    )

    return df_vcr[["headingCode", "VCR_Ceara_Brasil"]]


@st.cache_data
def obter_vcr_brasil_mundo(df_harvard):
    """
    Obtém o VCR do Brasil em relação ao Mundo a partir da coluna 'export_rca'
    do Harvard Dataverse, por 'product_hs92_code' (setor i).
    """
    df_vcr = df_harvard.rename(
        columns={"product_hs92_code": "headingCode", "export_rca": "VCR_Brasil_Mundo"}
    ).copy()

    # Normaliza o código HS de 6 dígitos para 4 para unificação com ComexStat
    df_vcr["headingCode"] = df_vcr["headingCode"].astype(str).str[:4]

    # Calcula a média do VCR ao longo dos anos para cada produto de 4 dígitos
    df_vcr = df_vcr.groupby("headingCode")["VCR_Brasil_Mundo"].mean().reset_index()

    return df_vcr


@st.cache_data
def obter_pci_e_distancia(df_harvard):
    """
    Obtém o PCI e a Distância para cada setor (product_hs92_code).
    """
    df_metrics = df_harvard.rename(
        columns={
            "product_hs92_code": "headingCode",
            "pci": "PCI",
            "distance": "Distancia_Parceiros",
        }
    ).copy()

    # Normaliza o código HS de 6 dígitos para 4 para unificação com ComexStat
    df_metrics["headingCode"] = df_metrics["headingCode"].astype(str).str[:4]

    # Calcula a média do PCI e da Distância ao longo dos anos para cada produto de 4 dígitos
    df_metrics = (
        df_metrics.groupby("headingCode")
        .agg({"PCI": "mean", "Distancia_Parceiros": "mean"})
        .reset_index()
    )

    return df_metrics


@st.cache_data
def calcular_vcr_dentro_selecao(df_comex_filtrado, df_comex_nacional):
    """
    Calcula a VCR (Vantagem Comparativa Revelada) dos produtos (headings)
    em cada estado.
    - Se apenas 1 estado for selecionado, compara-o contra o contexto NACIONAL.
    - Se múltiplos estados forem selecionados, compara-o contra o CONJUNTO FILTRADO.
    """
    import numpy as np
    import pandas as pd

    if df_comex_filtrado.empty:
        return pd.DataFrame(columns=["state", "headingCode", "heading", "VCR"])

    df_comex_filtrado = df_comex_filtrado.copy()
    df_comex_filtrado["headingCode"] = df_comex_filtrado["headingCode"].astype(str)

    selected_states = df_comex_filtrado["state"].unique()

    # ----------------------------------------------------------------------
    # 1. DEFINIÇÃO DA BASE DE COMPARAÇÃO (DENOMINADOR)
    # ----------------------------------------------------------------------
    if len(selected_states) == 1:
        # CORREÇÃO: Se apenas um estado, a base de comparação é o CONTEXTO NACIONAL
        df_base_comparacao = df_comex_nacional.copy()

    else:
        # Se múltiplos estados, a base de comparação é a SOMA DOS ESTADOS SELECIONADOS
        df_base_comparacao = df_comex_filtrado.copy()

    # Cálculo do Denominador da VCR

    # Total das exportações (FOB) para o CONTEXTO DE COMPARAÇÃO
    X_total_comparacao = df_base_comparacao["metricFOB"].sum()

    # Exportação do Produto no Contexto de Comparação (Xi_comparacao)
    df_xi_comparacao = (
        df_base_comparacao.groupby("headingCode")["metricFOB"].sum().reset_index()
    )
    df_xi_comparacao = df_xi_comparacao.rename(columns={"metricFOB": "Xi_comparacao"})

    if X_total_comparacao == 0:
        # Retorna VCR 0 se o total for 0
        df_comex_filtrado["VCR"] = 0.0
        return df_comex_filtrado[["state", "headingCode", "metricFOB", "VCR"]].copy()

    # Taxa de Exportação Global no Contexto de Comparação (Denominador da VCR)
    df_xi_comparacao["Tx_Global_Contexto"] = (
        df_xi_comparacao["Xi_comparacao"] / X_total_comparacao
    )

    # ----------------------------------------------------------------------
    # 2. CÁLCULO DO NUMERADOR DA VCR (Taxa Local)
    # ----------------------------------------------------------------------

    # Agregação por Estado e Produto (X_i, estado)
    df_export_estado = (
        df_comex_filtrado.groupby(["state", "headingCode"])["metricFOB"]
        .sum()
        .reset_index()
    )

    # Total das exportações por Estado (X_total_estado)
    df_export_total_estado = (
        df_comex_filtrado.groupby("state")["metricFOB"].sum().reset_index()
    )
    df_export_total_estado = df_export_total_estado.rename(
        columns={"metricFOB": "X_total_estado"}
    )

    # Junção dos dados
    df_vcr_calc = df_export_estado.merge(df_export_total_estado, on="state", how="left")
    df_vcr_calc = df_vcr_calc.merge(
        df_xi_comparacao[["headingCode", "Tx_Global_Contexto"]],
        on="headingCode",
        how="left",
    ).fillna(0)

    # Cálculo da Taxa de Exportação Local (Numerador da VCR)
    df_vcr_calc["Tx_Local"] = df_vcr_calc["metricFOB"] / df_vcr_calc["X_total_estado"]

    # ----------------------------------------------------------------------
    # 3. CÁLCULO FINAL
    # ----------------------------------------------------------------------
    df_vcr_calc["VCR"] = np.where(
        df_vcr_calc["Tx_Global_Contexto"] > 0,
        df_vcr_calc["Tx_Local"] / df_vcr_calc["Tx_Global_Contexto"],
        0.0,
    )

    # Reagrupar para ter uma linha por state/heading/headingCode e manter VCR
    df_result = df_vcr_calc[["state", "headingCode", "metricFOB", "VCR"]].copy()

    # Adicionar a descrição (heading) de volta, usando a base nacional para garantir todos os headings
    df_headings = df_comex_nacional[["headingCode", "heading"]].drop_duplicates()
    df_result = df_result.merge(df_headings, on="headingCode", how="left")

    return df_result[df_result["VCR"] > 0].sort_values(by="VCR", ascending=False)


# ==============================================================================
# NOVAS FUNÇÕES EXIGIDAS PELA LÓGICA DO DOCUMENTO ANEXO
# ==============================================================================


def normalizar_vcr(df: pd.DataFrame, coluna_vcr: str) -> pd.DataFrame:
    """
    Normaliza os valores de uma coluna de VCR para um intervalo de 0 a 1.
    Fórmula: VCRi^Norm = (VCRi - VCRmin) / (VCRmax - VCRmin)
    Aplica-se apenas a valores numéricos válidos.
    """
    coluna_norm = coluna_vcr + "_NORM"

    # Converte para numérico e remove NaNs para o cálculo min/max
    vcr_numeric = pd.to_numeric(df[coluna_vcr], errors="coerce").dropna()

    if vcr_numeric.empty:
        df[coluna_norm] = 0.0
        return df

    vcr_min = vcr_numeric.min()
    vcr_max = vcr_numeric.max()

    if vcr_max == vcr_min:
        df[coluna_norm] = 0.0
    else:
        # Aplica a normalização, tratando NaNs (que serão preenchidos depois)
        df[coluna_norm] = (df[coluna_vcr].astype(float) - vcr_min) / (vcr_max - vcr_min)

    return df


def calcular_vcr_ajustado(df_metrics: pd.DataFrame) -> pd.DataFrame:
    """
    IMPLEMENTAÇÃO PLACEHOLDER (VCR Ajustado).
    O cálculo real do VCR Ajustado (baseado em Empregos, Empresas, etc.) exige
    dados municipais/setoriais que não são carregados em 'app.py' (apenas Comex, Harvard, Comtrade).

    Esta função implementa um PLACEHOLDER simulando o VCR Ajustado (VCR_AJUSTADO)
    e o VCR Ajustado Normalizado (VCR_AJUSTADO_NORM) baseado no PCI e VCR Ceará/Brasil,
    para que a lógica de normalização possa ser demonstrada.
    """
    df = df_metrics.copy()

    # Placeholder: VCR_AJUSTADO é uma combinação do VCR tradicional e PCI
    # Isso simula um índice de complexidade local/setorial.
    vcr_ce_br = pd.to_numeric(df["VCR_Ceara_Brasil"], errors="coerce").fillna(0)
    pci = pd.to_numeric(df["PCI"], errors="coerce").fillna(0)

    # Simulação da fórmula: (VCR_CE/BR + PCI) / 2
    df["VCR_AJUSTADO"] = np.where(
        (vcr_ce_br > 1) & (pci.notna()),
        (vcr_ce_br + pci) / 2,  # Combinação quando há vantagem
        vcr_ce_br,  # Apenas VCR quando não há vantagem (ou PCI ausente)
    )

    # Normalização conforme documento
    df = normalizar_vcr(df, "VCR_AJUSTADO")

    return df


def calcular_indice_prioridade_ajustado(df: pd.DataFrame, pesos: dict) -> pd.DataFrame:
    """
    Calcula o Índice de Prioridade Ajustado utilizando as métricas normalizadas
    e os pesos definidos pelo usuário.
    """
    df_calc = df.copy()

    # Certifica-se de que as colunas normalizadas são float, tratando NaNs
    df_calc["VCR_CE_NORM"] = pd.to_numeric(
        df_calc["VCR_Ceara_Brasil_NORM"], errors="coerce"
    ).fillna(0)
    df_calc["VCR_BR_NORM"] = pd.to_numeric(
        df_calc["VCR_Brasil_Mundo_NORM"], errors="coerce"
    ).fillna(0)
    df_calc["VCR_AJ_NORM"] = pd.to_numeric(
        df_calc["VCR_AJUSTADO_NORM"], errors="coerce"
    ).fillna(0)
    df_calc["PCI_NORM"] = pd.to_numeric(df_calc["PCI_NORM"], errors="coerce").fillna(0)

    # Normalização da Distância: Inverter a lógica. Distâncias menores devem ter valor maior (proximidade).
    # Assumimos que a Distância (métrica bruta) já foi normalizada de 0 a 1 em "Distancia_Parceiros_NORM"
    # Se Distancia_Parceiros_NORM for a proximidade:
    dist_norm = pd.to_numeric(
        df_calc["Distancia_Parceiros_NORM"], errors="coerce"
    ).fillna(0)

    # Se Distancia_Parceiros_NORM for a distância (quanto maior, pior):
    # Vamos reverter (1 - Distância Normalizada) para obter a Proximidade Normalizada
    proximidade_norm = 1 - dist_norm

    # Cálculo do Índice de Prioridade Ajustado (Soma Ponderada)
    # VCR_estadual + VCR_país + VCR_Ajustado são métricas positivas (quanto maior, melhor)
    # PCI é métrica positiva (quanto maior, melhor)
    # Distância é métrica negativa (quanto maior, pior) -> usamos Proximidade

    # Peso total para garantir que a soma das VCRs seja ponderada corretamente
    peso_vcr_total = pesos["vcr_ceara"] + pesos["vcr_brasil"] + pesos["vcr_ajustado"]

    # Normalização dos pesos VCRs para soma 1 (para o subconjunto VCR)
    if peso_vcr_total > 0:
        peso_vcr_ceara = pesos["vcr_ceara"] / peso_vcr_total
        peso_vcr_brasil = pesos["vcr_brasil"] / peso_vcr_total
        peso_vcr_ajustado = pesos["vcr_ajustado"] / peso_vcr_total
    else:
        # Se os pesos VCRs forem zero, distribuímos igualmente para evitar NaN
        peso_vcr_ceara = peso_vcr_brasil = peso_vcr_ajustado = 1 / 3

    # Índice VCR Composto (normalizado)
    indice_vcr = (
        (df_calc["VCR_CE_NORM"] * peso_vcr_ceara)
        + (df_calc["VCR_BR_NORM"] * peso_vcr_brasil)
        + (df_calc["VCR_AJ_NORM"] * peso_vcr_ajustado)
    )

    # Índice Final: Combinação dos 3 componentes (VCR_Composto, PCI, Proximidade)
    # Assumimos que os pesos PCI, Distancia e o peso VCR_total (1) são os pesos finais

    # Normalizando os 3 grandes grupos de pesos (VCR Total, PCI, Distância) para somarem 1
    peso_total_geral = 1 + pesos["pci"] + pesos["distancia"]

    peso_vcr_composto = 1 / peso_total_geral  # Peso do subconjunto VCR
    peso_pci = pesos["pci"] / peso_total_geral
    peso_distancia = pesos["distancia"] / peso_total_geral

    df_calc["INDICE_PRIORIDADE_AJUSTADO"] = (
        (indice_vcr * peso_vcr_composto)
        + (df_calc["PCI_NORM"] * peso_pci)
        + (proximidade_norm * peso_distancia)
    )

    return df_calc


# ==============================================================================
# FIM DAS NOVAS FUNÇÕES
# ==============================================================================


# %%
# Configuração inicial do Streamlit
st.set_page_config(
    page_title="Dashboard Comércio Internacional",
    layout="wide",
    # Ocultando a sidebar para manter a estética original do seu código,
    # já que os filtros foram movidos para o expander
    initial_sidebar_state="collapsed",
)


COMEXSTAT_PATH = "resources/comexstat_data.csv"
HARVARD_PATH = "resources/harvard_data.csv"
COMTRADE_PATH = "resources/comtrade_data.csv"

# Verificação e carregamento dos dados
if not all(
    os.path.exists(path) for path in [COMEXSTAT_PATH, HARVARD_PATH, COMTRADE_PATH]
):
    st.error(
        "Arquivos de dados não encontrados. Por favor, execute o script 'main.py' primeiro para gerar os arquivos CSV."
    )
    st.stop()


@st.cache_data
def load_data(path):
    """
    Carrega dados de um arquivo CSV usando Polars, converte para Pandas e,
    para ComexStat, aplica a correção de desalinhamento de colunas.
    """
    # Schema de leitura forçada
    if "harvard_data.csv" in path:
        custom_schema = {
            "country_id": pl.Int8,
            "country_iso3_code": pl.Utf8,
            "product_id": pl.Int64,
            "product_hs92_code": pl.Utf8,
            "year": pl.Int64,
            "export_value": pl.Int64,
            "import_value": pl.Int64,
            "global_share": pl.Float64,
            "export_rca": pl.Float64,
            "distance": pl.Float64,
            "cog": pl.Float64,
            "pci": pl.Float64,
        }
    elif "comexstat_data.csv" in path:
        custom_schema = {
            "year": pl.Int64,
            "state": pl.Utf8,
            "headingCode": pl.Utf8,
            "heading": pl.Utf8,
            "metricFOB": pl.Int64,
        }
    elif "comtrade_data.csv" in path:
        custom_schema = {
            "typeCode": pl.Utf8,
            "freqCode": pl.Utf8,
            "refPeriodId": pl.Int64,
            "refYear": pl.Int64,
            "refMonth": pl.Int64,
            "period": pl.Int64,
            "reporterCode": pl.Int64,
            "reporterISO": pl.Utf8,  # Inferred as string/code
            "reporterDesc": pl.Utf8,  # Inferred as string/description
            "flowCode": pl.Utf8,
            "flowDesc": pl.Utf8,  # Inferred as string/description
            "partnerCode": pl.Int64,
            "partnerISO": pl.Utf8,  # Inferred as string/code
            "partnerDesc": pl.Utf8,  # Inferred as string/description
            "partner2Code": pl.Int64,
            "partner2ISO": pl.Utf8,  # Inferred as string/code
            "partner2Desc": pl.Utf8,  # Inferred as string/description
            "classificationCode": pl.Utf8,
            "classificationSearchCode": pl.Utf8,
            "isOriginalClassification": pl.Boolean,
            "cmdCode": pl.Utf8,
            "cmdDesc": pl.Utf8,  # Inferred as string/description
            "aggrLevel": pl.Int64,  # Inferred as integer level
            "isLeaf": pl.Boolean,  # Inferred as a boolean flag
            "customsCode": pl.Utf8,
            "customsDesc": pl.Utf8,  # Inferred as string/description
            "mosCode": pl.Int64,
            "motCode": pl.Int64,
            "motDesc": pl.Utf8,  # Inferred as string/description
            "qtyUnitCode": pl.Int64,
            "qtyUnitAbbr": pl.Utf8,  # Inferred as string/abbreviation
            "qty": pl.Float64,  # Inferred as a measurable quantity
            "isQtyEstimated": pl.Boolean,
            "altQtyUnitCode": pl.Int64,
            "altQtyUnitAbbr": pl.Utf8,  # Inferred as string/abbreviation
            "altQty": pl.Float64,  # Inferred as a measurable quantity
            "isAltQtyEstimated": pl.Boolean,
            "netWgt": pl.Float64,
            "isNetWgtEstimated": pl.Boolean,
            "grossWgt": pl.Float64,
            "isGrossWgtEstimated": pl.Boolean,
            "cifvalue": pl.Float64,  # Inferred as a monetary value
            "fobvalue": pl.Float64,
            "primaryValue": pl.Float64,
            "legacyEstimationFlag": pl.Int64,
            "isReported": pl.Boolean,
            "isAggregate": pl.Boolean,
        }
    else:
        custom_schema = None

    # 1. Leitura usando Polars
    df_pl = pl.read_csv(
        path, schema=custom_schema, ignore_errors=True, truncate_ragged_lines=True
    )

    # 2. Conversão para Pandas
    df_pd = df_pl.to_pandas()

    return df_pd


# Carregar os três dataframes, usando a função cacheada e tipagem correta
comexstat_df = load_data(COMEXSTAT_PATH)
harvard_df = load_data(HARVARD_PATH)
comtrade_df = load_data(COMTRADE_PATH)

# Garantir a coerência do tipo 'headingCode' para merge na Análise Comparativa
comexstat_df["headingCode"] = comexstat_df["headingCode"].astype(str)

# %%
st.title("Dashboard de Análise de Comércio Internacional 📊")
st.markdown(
    "Este painel apresenta dados de comércio extraídos de fontes distintas: ComexStat, Harvard Dataverse e Comtrade da ONU."
)

# Criação das abas
tab_comex, tab_harvard, tab_comtrade, tab_compare = st.tabs(
    ["ComexStat", "Harvard Dataverse", "Comtrade", "Análise Comparativa"]
)


# %%
# Aba ComexStat
with tab_comex:
    st.header("Dados do ComexStat")

    # --- FILTROS DENTRO DA ABA ---
    with st.expander("Opções de Filtragem", expanded=True):
        col_state, col_year, col_hs = st.columns(3)

        # 1. Filtro de Estado (UF) - Default: 'CE'
        states = sorted(comexstat_df["state"].dropna().unique().tolist())
        default_state = ["Ceará"] if "Ceará" in states else states[:1]

        selected_states = col_state.multiselect(
            "Selecione o(s) Estado(s)",
            options=states,
            default=default_state,
            key="comex_state_select",
            help="Selecione um ou mais estados para a análise.",
        )

        # 2. Filtro de Ano
        years = sorted(comexstat_df["year"].dropna().unique().astype(int).tolist())
        selected_years = col_year.multiselect(
            "Selecione o(s) Ano(s)",
            years,
            default=years,
            key="comex_year_select",
            help="Selecione um ou mais anos para a análise.",
        )

        # 3. Filtro de Código HS
        df_for_hs_options = comexstat_df.copy()
        if selected_states:
            df_for_hs_options = df_for_hs_options[
                df_for_hs_options["state"].isin(selected_states)
            ]
        if selected_years:
            df_for_hs_options = df_for_hs_options[
                df_for_hs_options["year"].isin(selected_years)
            ]

        df_for_hs_options["HS_Desc"] = (
            df_for_hs_options["headingCode"].astype(str)
            + " - "
            + df_for_hs_options["heading"].astype(str).str[:50]
            + "..."
        )
        products_options = sorted(
            df_for_hs_options["HS_Desc"].dropna().unique().tolist()
        )

        selected_hs_desc = col_hs.multiselect(
            "Selecione o(s) Código(s) HS",
            products_options,
            key="comex_hs_select",
            help="Filtra códigos HS com base na seleção de estado/ano.",
        )
        selected_products = [desc.split(" - ")[0] for desc in selected_hs_desc]

    # --- APLICAÇÃO DOS FILTROS ---
    comexstat_filtered = comexstat_df.copy()

    if selected_states:
        comexstat_filtered = comexstat_filtered[
            comexstat_filtered["state"].isin(selected_states)
        ]

    if selected_years:
        comexstat_filtered = comexstat_filtered[
            comexstat_filtered["year"].isin(selected_years)
        ]

    if selected_products:
        comexstat_filtered = comexstat_filtered[
            comexstat_filtered["headingCode"].isin(selected_products)
        ]

    # --- BLOCO DE MÉTRICAS ANALÍTICAS ---
    # (Mantido como antes, usando o total FOB da seleção)
    col_metric1, col_metric2, col_metric3 = st.columns(3)

    total_selected_fob = comexstat_filtered["metricFOB"].sum()
    total_brasil_fob = comexstat_df["metricFOB"].sum()
    total_mundo_display = "$49,71 Tri"

    with col_metric1:
        st.subheader("Total de Exportações (Seleção Atual)")
        st.metric("Total (US$)", format_fob_metric(total_selected_fob))

    with col_metric2:
        st.subheader("Total de Exportações do Brasil")
        st.metric("Total (US$)", format_fob_metric(total_brasil_fob))

    with col_metric3:
        st.subheader("Total de Exportações do Mundo")
        st.metric("Total (US$)", total_mundo_display)

    st.markdown("---")
    # --- FIM DO BLOCO DE MÉTRICAS ---

    # ----------------------------------------------------------------------
    # --- NOVO DATAFRAME: EXIBIÇÃO DA VCR ---
    # ----------------------------------------------------------------------
    if not comexstat_filtered.empty:
        # 1. Cálculo da VCR para a seleção atual
        # CHAVE: Passando o DataFrame nacional (comexstat_df) como segundo argumento para o contexto
        df_vcr_display = calcular_vcr_dentro_selecao(comexstat_filtered, comexstat_df)

        # Agregação para o DataFrame de exibição (mantendo uma linha por heading/state com VCR)
        df_display = df_vcr_display[
            ["state", "headingCode", "heading", "metricFOB", "VCR"]
        ].copy()

        # Renomear e formatar para exibição
        df_display = df_display.rename(
            columns={
                "state": "Estado",
                "headingCode": "Código HS",
                "heading": "Descrição do Produto",
                "metricFOB": "Valor FOB (US$)",
                "VCR": "VCR (Relevância Revelada)",
            }
        )

        df_display["Valor FOB (US$)"] = df_display["Valor FOB (US$)"].apply(
            format_fob_metric
        )
        df_display["VCR (Relevância Revelada)"] = df_display[
            "VCR (Relevância Revelada)"
        ].round(3)

        st.subheader(
            "Vantagem Comparativa Revelada (VCR) por Produto (Base Nacional/Conjunto)"
        )
        st.dataframe(
            df_display,
            width="stretch",
            column_order=(
                "Estado",
                "Código HS",
                "Descrição do Produto",
                "VCR (Relevância Revelada)",
                "Valor FOB (US$)",
            ),
        )

        # ----------------------------------------------------------------------
        # --- REFATORAÇÃO DO GRÁFICO DE BARRAS (AGRUPAMENTO) ---
        # ----------------------------------------------------------------------

        # Mantendo a lógica de agrupamento em 'Demais/Outros' para o gráfico
        # Nota: O gráfico ainda usa o valor FOB, mas pode ser mudado para VCR se necessário.
        # Por enquanto, mantemos FOB para representar o valor absoluto de exportação.

        # Agrega o valor FOB por Título (Heading) e Estado (State)
        df_agg = (
            comexstat_filtered.groupby(["heading", "state"])["metricFOB"]
            .sum()
            .reset_index()
        )

        total_fob_selection = df_agg["metricFOB"].sum()
        THRESHOLD_PERCENT = 0.02

        df_agg["percentage"] = df_agg["metricFOB"] / total_fob_selection
        df_small = df_agg[df_agg["percentage"] < THRESHOLD_PERCENT].copy()

        if not df_small.empty:
            outros_fob = df_small["metricFOB"].sum()
            outros_data = pd.DataFrame(
                [
                    {
                        "heading": f"Demais/Outros (< {THRESHOLD_PERCENT * 100:.0f}%)",
                        "state": "Agregado",
                        "metricFOB": outros_fob,
                        "percentage": outros_fob / total_fob_selection,
                    }
                ]
            )

            df_large = df_agg[df_agg["percentage"] >= THRESHOLD_PERCENT]
            df_plot = pd.concat([df_large, outros_data], ignore_index=True)
        else:
            df_plot = df_agg.copy()

        # Gráfico de barras FOB
        fig = px.bar(
            df_plot.sort_values(by="metricFOB", ascending=False),
            x="heading",
            y="metricFOB",
            color="state",
            title=f"Valor FOB por Título (Top Headings + Demais/Outros)",
            labels={
                "heading": "Título (Heading)",
                "metricFOB": "Valor FOB (US$)",
                "state": "Estado",
            },
            hover_data={"percentage": ":.2%"},
        )
        st.plotly_chart(fig, use_container_width=True)

# %%
# Aba Harvard Dataverse
with tab_harvard:
    st.header("Dados do Harvard Dataverse")

    # --- FILTROS DENTRO DA ABA ---
    with st.expander("Opções de Filtragem"):
        # Cópia do DataFrame para filtragem sequencial
        df_filtered = harvard_df.copy()

        # Coluna adicionada para País
        col_year, col_country, col_hs = st.columns(3)

        # 1. Filtro de Ano
        years = sorted(df_filtered["year"].dropna().unique().astype(int).tolist())
        selected_years = col_year.multiselect(
            "Selecione o(s) Ano(s)", years, default=years, key="harvard_year_select"
        )
        if selected_years:
            df_filtered = df_filtered[df_filtered["year"].isin(selected_years)]

        # 2. Filtro de País - IMPLEMENTAÇÃO: Default BRA
        # Obter opções de país (após o filtro de ano)
        countries_options = sorted(
            df_filtered["country_iso3_code"].dropna().unique().astype(str).tolist()
        )
        # Definir o default como "BRA" se estiver disponível
        default_country = (
            ["BRA"] if "BRA" in countries_options else countries_options[:1]
        )

        selected_countries = col_country.multiselect(
            "Selecione o(s) País(es) (ISO3)",
            options=countries_options,
            default=default_country,  # <--- Priorização do Brasil
            key="harvard_country_select",
        )
        if selected_countries:
            df_filtered = df_filtered[
                df_filtered["country_iso3_code"].isin(selected_countries)
            ]

        # 3. Filtro de Código HS
        products = sorted(
            df_filtered["product_hs92_code"].dropna().unique().astype(str).tolist()
        )
        selected_products = col_hs.multiselect(
            "Selecione o(s) Código(s) HS", products, key="harvard_hs_select"
        )
        if selected_products:
            df_filtered = df_filtered[
                df_filtered["product_hs92_code"].isin(selected_products)
            ]

    # Variável para o DataFrame filtrado, antes da agregação
    harvard_filtered = df_filtered

    # ----------------------------------------------------------------------
    # --- AGREGAÇÃO PARA EXIBIÇÃO SUMARIZADA E LIMPA ---
    # ----------------------------------------------------------------------
    if not harvard_filtered.empty:
        # Define as colunas para agregação
        group_cols = ["country_iso3_code", "year"]

        # Agregação: Soma para valores monetários, Média para índices
        df_aggregated = (
            harvard_filtered.groupby(group_cols)
            .agg(
                {
                    "export_value": "sum",
                    "import_value": "sum",
                    "global_share": "mean",  # Média da participação global
                    "export_rca": "mean",  # Média do VCR de exportação
                    "distance": "mean",  # Média da Distância
                    "cog": "mean",  # Média do COG
                    "pci": "mean",  # Média do PCI
                    "product_id": "count",  # Contagem de produtos (Count)
                }
            )
            .reset_index()
        )

        # Renomear colunas para clareza
        df_aggregated = df_aggregated.rename(
            columns={
                "country_iso3_code": "País (ISO3)",
                "year": "Ano",
                "export_value": "Exportação Total (US$)",
                "import_value": "Importação Total (US$)",
                "global_share": "Share Global Médio",
                "export_rca": "VCR Médio",
                "distance": "Distância Média",
                "cog": "COG Médio",
                "pci": "PCI Médio",
                "product_id": "Qtd. Produtos HS",
            }
        )

        # Formatação das colunas de valor e arredondamento
        for col in ["Exportação Total (US$)", "Importação Total (US$)"]:
            df_aggregated[col] = df_aggregated[col].apply(
                lambda x: format_fob_metric(x)
                .replace(" Tri", "T")
                .replace(" Bi", "B")
                .replace(" Mi", "M")
            )

        for col in [
            "Share Global Médio",
            "VCR Médio",
            "Distância Média",
            "COG Médio",
            "PCI Médio",
        ]:
            df_aggregated[col] = df_aggregated[col].round(3)

        # Exibição do DataFrame AGREGADO
        st.subheader("Tabela Agregada por País e Ano (Sumário)")
        st.dataframe(df_aggregated, width="stretch")

        # --- EXIBIÇÃO DETALHADA (OPCIONAL) ---
        with st.expander("Visualizar Detalhes por Produto (Granularidade Máxima)"):
            st.markdown(
                "Abaixo está a tabela na sua granularidade máxima, exibindo cada **`product_hs92_code`**."
            )
            st.dataframe(harvard_filtered, width="stretch")

        # ----------------------------------------------------------------------
        # --- NOVO GRÁFICO DE BARRA DE PROPORÇÃO DE PRODUTOS ---
        # ----------------------------------------------------------------------
        st.subheader("Distribuição de Exportação por Produto (Top 10)")

        # Agregação por Código HS para obter o valor total de exportação
        df_product_export = (
            harvard_filtered.groupby("product_hs92_code")
            .agg(
                total_export=("export_value", "sum"),
                average_pci=("pci", "mean"),  # Adiciona PCI médio para o hover
            )
            .reset_index()
        )

        # Cálculo da proporção
        total_global_export = df_product_export["total_export"].sum()
        df_product_export["proportion"] = (
            df_product_export["total_export"] / total_global_export
        )

        # Selecionar Top N produtos (ex: Top 10)
        df_plot_product = df_product_export.sort_values(
            by="total_export", ascending=False
        ).head(15)

        # Criação do gráfico de barras (proporção de exportação)
        fig = px.bar(
            df_plot_product,
            x="product_hs92_code",
            y="proportion",  # Usar a proporção no eixo Y
            color="proportion",  # Colorir pela proporção
            title="Proporção de Exportação (Export Value) por Código HS",
            labels={
                "product_hs92_code": "Código HS (Produto)",
                "proportion": "Proporção do Total (%)",
                "total_export": "Valor Exportado (US$)",
            },
            hover_data={
                "total_export": True,
                "average_pci": ":.3f",
                "proportion": ":.2%",
            },
            template="plotly_dark",  # Para manter a estética escura
        )

        fig.update_layout(yaxis_tickformat=".0%")  # Formatar eixo Y como porcentagem

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhum dado encontrado com os filtros aplicados.")

with tab_comtrade:
    st.header("Dados do Comtrade")

    # --- FILTROS DENTRO DA ABA ---
    with st.expander("Opções de Filtragem"):
        df_filtered = comtrade_df.copy()

        col_year, col_hs = st.columns(2)

        # Filtro de ano
        years = sorted(df_filtered["refYear"].dropna().unique().astype(int).tolist())
        selected_years = col_year.multiselect(
            "Selecione o(s) Ano(s)", years, default=years, key="comtrade_year_select"
        )
        if selected_years:
            df_filtered = df_filtered[df_filtered["refYear"].isin(selected_years)]

        # Filtro de produto (códigos HS)
        products = sorted(df_filtered["cmdCode"].dropna().unique().astype(str).tolist())
        selected_products = col_hs.multiselect(
            "Selecione o(s) Código(s) HS", products, key="comtrade_hs_select"
        )
        if selected_products:
            df_filtered = df_filtered[df_filtered["cmdCode"].isin(selected_products)]

    comtrade_filtered = df_filtered

    st.dataframe(comtrade_filtered, width="stretch")

    if not comtrade_filtered.empty:
        # Gráfico de pizza para a distribuição do valor primário por produto
        fig = px.pie(
            comtrade_filtered,
            names="cmdDesc",
            values="primaryValue",
            title="Distribuição do Valor Primário por Descrição do Produto",
        )
        st.plotly_chart(fig, use_container_width=True)

# %%
# Aba Análise Comparativa
with tab_compare:
    st.header("Análise Comparativa de Especialização e Complexidade")
    st.markdown(
        "Consolidação de métricas de VCR (Vantagem Comparativa Revelada), Distância e PCI (Índice de Complexidade de Produtos) por Código HS."
    )

    # --- 0. Controles de Pesos (Sidebar para tempo real) ---
    st.markdown("### 🎚️ Ajuste de Pesos para o Índice de Prioridade")
    st.markdown(
        "Utilize os sliders para definir a importância de cada métrica no **Índice de Prioridade Ajustado**."
    )

    col_vcr_ce, col_vcr_br, col_vcr_aj, col_pci, col_dist = st.columns(5)

    # Pesos para as 3 VCRs (sub-componentes do 'Índice VCR Composto')
    vcr_ceara_weight = col_vcr_ce.slider(
        "Peso VCR Estadual",
        0.0,
        1.0,
        0.4,
        0.05,
        key="w_vcr_ceara",
        help="Prioriza VCR do estado (Ceará/Brasil).",
    )
    vcr_brasil_weight = col_vcr_br.slider(
        "Peso VCR País",
        0.0,
        1.0,
        0.3,
        0.05,
        key="w_vcr_brasil",
        help="Prioriza VCR do país (Brasil/Mundo).",
    )
    vcr_ajustado_weight = col_vcr_aj.slider(
        "Peso VCR Ajustado",
        0.0,
        1.0,
        0.3,
        0.05,
        key="w_vcr_ajustado",
        help="Prioriza o VCR Ajustado (baseado na Complexidade Local).",
    )

    # Pesos para PCI e Distância (componentes de topo)
    pci_weight = col_pci.slider(
        "Peso PCI",
        0.0,
        1.0,
        0.3,
        0.05,
        key="w_pci",
        help="Prioriza a Complexidade do Produto (PCI).",
    )
    distancia_weight = col_dist.slider(
        "Peso Distância",
        0.0,
        1.0,
        0.4,
        0.05,
        key="w_distancia",
        help="Prioriza a Proximidade dos Parceiros (1 - Distância).",
    )

    # Dicionário de Pesos
    pesos_dict = {
        "vcr_ceara": vcr_ceara_weight,
        "vcr_brasil": vcr_brasil_weight,
        "vcr_ajustado": vcr_ajustado_weight,
        "pci": pci_weight,
        "distancia": distancia_weight,  # Métrica inversa (Proximidade)
    }

    st.markdown("---")

    # 1. Obter Tabela de Referência de Códigos HS e Descrições
    # Filtra códigos HS inválidos ou vazios
    df_referencia = comexstat_df[["headingCode", "heading"]].drop_duplicates()
    df_referencia = df_referencia.rename(columns={"heading": "Descrição"})
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

    # 4. IMPLEMENTAÇÃO: Normalização dos VCRs Tradicionais (Estadual/País) e Distância (para PCI)
    df_final = normalizar_vcr(df_final, "VCR_Ceara_Brasil")
    df_final = normalizar_vcr(df_final, "VCR_Brasil_Mundo")
    # Normalização do PCI
    df_final = normalizar_vcr(df_final, "PCI")
    # Normalização da Distância (Bruta)
    df_final = normalizar_vcr(df_final, "Distancia_Parceiros")

    # 5. IMPLEMENTAÇÃO: Cálculo do VCR Ajustado (Municipal/Setorial) e sua Normalização (Lógica do anexo)
    # Nota: Este é um PLACEHOLDER, pois os dados municipais/setoriais (Empregos, PIB, etc.) não estão carregados.
    df_final = calcular_vcr_ajustado(df_final)

    # 6. IMPLEMENTAÇÃO: Cálculo do Índice de Prioridade Ajustado
    df_final = calcular_indice_prioridade_ajustado(df_final, pesos_dict)

    # 7. Formatação da Tabela
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

    # Arredondamento e limpeza
    cols_to_round = [
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

    for col in cols_to_round:
        df_final[col] = pd.to_numeric(df_final[col], errors="coerce").round(3)

    # Substituir NaN por 'N/A'
    df_final = df_final.fillna("N/A")

    # Ordenação final pela nova métrica ajustada
    df_final_sorted = df_final.sort_values(
        by=["Índice de Prioridade Ajustado"],
        key=lambda x: pd.to_numeric(x, errors="coerce"),
        ascending=False,
    )

    # Exibição da Tabela Consolidada
    st.subheader("Tabela de Especialização e Complexidade Ponderada")
    st.info(
        "A tabela é ordenada pelo **Índice de Prioridade Ajustado**, que combina as métricas normalizadas com os pesos definidos nos sliders."
    )

    # Colunas finais a serem exibidas (foco nas métricas normalizadas e no Índice)
    column_order = [
        "Código HS",
        "Descrição",
        "VCR estadual normalizada",
        "VCR país normalizada",
        "VCR Ajustado normalizado",
        "PCI normalizado",
        "distância entre parceiros normalizada",
        "Índice de Prioridade Ajustado",
    ]

    # Exibir as métricas brutas também, em uma seção expansível
    with st.expander("Visualizar Métrica Brutas"):
        st.dataframe(
            df_final_sorted[
                [
                    "Código HS",
                    "Descrição",
                    "VCR estadual (Bruto)",
                    "VCR país (Bruto)",
                    "VCR Ajustado (Bruto)",
                    "PCI (Bruto)",
                    "distância entre parceiros (Bruto)",
                ]
            ],
            width="stretch",
        )

    st.dataframe(
        df_final_sorted[column_order],
        width="stretch",
    )

    # Espaço para os sumários originais
    st.markdown("---")
    st.subheader("Dados Sumarizados (Originais)")

    col1, col2, col3 = st.columns(3)

    # Coluna 1: Resumo ComexStat
    with col1:
        st.subheader("ComexStat")
        st.markdown("Sumário de valores FOB por estado.")
        if not comexstat_df.empty:
            summary = comexstat_df.groupby("state")["metricFOB"].sum().reset_index()
            st.dataframe(summary, width="stretch")

    # Coluna 2: Resumo Harvard
    with col2:
        st.subheader("Harvard Dataverse")
        st.markdown("Total de exportação e importação por ano.")
        if not harvard_df.empty:
            summary = (
                harvard_df.groupby("year")
                .agg({"export_value": "sum", "import_value": "sum"})
                .reset_index()
            )
            st.dataframe(summary, width="stretch")

    # Coluna 3: Resumo Comtrade
    with col3:
        st.subheader("Comtrade")
        st.markdown("Valor primário total por ano.")
        if not comtrade_df.empty:
            summary = comtrade_df.groupby("refYear")["primaryValue"].sum().reset_index()
            st.dataframe(summary, width="stretch")
