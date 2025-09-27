# %%
import polars as pl
import streamlit as st
import plotly.express as px
import os

from comexstat import ComexStat
from comtrade import Comtrade
from dataverse import HarvardDataverse

# %%
# Configuração inicial do Streamlit
st.set_page_config(
    page_title="Dashboard Comércio Internacional",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Caminho para os arquivos de dados (assumindo que foram salvos por main.py)
COMEXSTAT_PATH = "Dashboard-Base/comexstat_data.csv"
HARVARD_PATH = "Dashboard-Base/harvard_data.csv"
COMTRADE_PATH = "Dashboard-Base/comtrade_data.csv"

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
    Carrega dados de um arquivo CSV usando Polars e os converte para um DataFrame de Pandas
    para compatibilidade com o Streamlit/Plotly, mantendo a performance da leitura.
    """
    return pl.read_csv(path).to_pandas()


# Carregar os três dataframes
comex = ComexStat()
comexstat_df = comex.query_comexstat_data(
    flow="export",
    period_from="2024-01",
    period_to="2024-12",
    filters=[{"filter": "state", "values": [23]}],
    metrics=["metricFOB"],
    details=["state", "heading"],
).to_pandas()

# # %% HARVARD's
TOKEN = os.getenv("HARVARD_API_KEY")
DOI: str = "doi:10.7910/DVN/T4CHWJ"

dataverse = HarvardDataverse(api_token=TOKEN)

schema_override = {"product_hs92_code": pl.Utf8}

harvard_df = dataverse.import_df(
    doi=DOI,
    target_filename="hs92_country_product_year_4.csv",
    polars_reader_options={"schema_overrides": schema_override},
)

harvard_df = harvard_df.select(harvard_df).to_pandas()

comtrade = Comtrade()
comtrade_df = pl.DataFrame(
    comtrade.query_data(
        # typeCode='C'
        # ,freqCode='A'
        # ,clCode='HS'
        # partnerCode='76'
    )
).to_pandas()

# %%
st.title("Dashboard de Análise de Comércio Internacional 📊")
st.markdown(
    "Este painel apresenta dados de comércio extraídos de fontes distintas: ComexStat, Harvard Dataverse e Comtrade da ONU."
)

# Criação das abas
tab_comex, tab_harvard, tab_comtrade, tab_compare = st.tabs(
    ["ComexStat", "Harvard Dataverse", "Comtrade", "Análise Comparativa"]
)


# Função auxiliar para criar filtros
def create_filters(df, tab_name):
    """Cria e retorna widgets de filtro na barra lateral."""
    st.sidebar.header(f"Filtros para {tab_name}")

    # Filtro de ano
    if "year" in df.columns:
        years = sorted(df["year"].unique())
        selected_years = st.sidebar.multiselect(
            f"Selecione o(s) Ano(s) - {tab_name}", years, default=years
        )
        df = df[df["year"].isin(selected_years)]

    # Filtro de produto (códigos HS)
    if "headingCode" in df.columns:
        products = sorted(df["headingCode"].unique())
        selected_products = st.sidebar.multiselect(
            f"Selecione o(s) Código(s) HS - {tab_name}", products
        )
        if selected_products:
            df = df[df["headingCode"].isin(selected_products)]
    elif "product_hs92_code" in df.columns:
        products = sorted(df["product_hs92_code"].unique())
        selected_products = st.sidebar.multiselect(
            f"Selecione o(s) Código(s) HS - {tab_name}", products
        )
        if selected_products:
            df = df[df["product_hs92_code"].isin(selected_products)]
    elif "cmdCode" in df.columns:
        products = sorted(df["cmdCode"].unique())
        selected_products = st.sidebar.multiselect(
            f"Selecione o(s) Código(s) HS - {tab_name}", products
        )
        if selected_products:
            df = df[df["cmdCode"].isin(selected_products)]

    return df


# %%
# Aba ComexStat
with tab_comex:
    st.header("Dados do ComexStat")

    # Filtros na sidebar
    comexstat_filtered = create_filters(comexstat_df, "ComexStat")

    st.dataframe(comexstat_filtered)

    if not comexstat_filtered.empty:
        # Gráfico de barras
        fig = px.bar(
            comexstat_filtered,
            x="heading",
            y="metricFOB",
            title="Valor FOB por Código de Título (Heading)",
            labels={"heading": "Título (Heading)", "metricFOB": "Valor FOB (US$)"},
        )
        st.plotly_chart(fig, use_container_width=True)

# %%
# Aba Harvard Dataverse
with tab_harvard:
    st.header("Dados do Harvard Dataverse")

    # Filtros na sidebar
    harvard_filtered = create_filters(harvard_df, "Harvard")

    st.dataframe(harvard_filtered)

    if not harvard_filtered.empty:
        # Gráfico de linha para tendência de exportação/importação
        fig = px.line(
            harvard_filtered.groupby("year")
            .agg({"export_value": "sum", "import_value": "sum"})
            .reset_index(),
            x="year",
            y=["export_value", "import_value"],
            title="Tendência de Exportação e Importação ao Longo do Tempo",
            labels={"year": "Ano", "value": "Valor (US$)", "variable": "Tipo de Fluxo"},
        )
        st.plotly_chart(fig, use_container_width=True)

# %%
# Aba Comtrade
with tab_comtrade:
    st.header("Dados do Comtrade")

    # Filtros na sidebar
    comtrade_filtered = create_filters(comtrade_df, "Comtrade")

    st.dataframe(comtrade_filtered)

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
    st.header("Análise Comparativa")
    st.markdown("Apenas dados sumarizados e visualizações lado a lado.")

    col1, col2, col3 = st.columns(3)

    # Coluna 1: Resumo ComexStat
    with col1:
        st.subheader("ComexStat")
        st.markdown("Sumário de valores FOB por estado.")
        if not comexstat_df.empty:
            summary = comexstat_df.groupby("state")["metricFOB"].sum().reset_index()
            st.dataframe(summary)

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
            st.dataframe(summary)

    # Coluna 3: Resumo Comtrade
    with col3:
        st.subheader("Comtrade")
        st.markdown("Valor primário total por ano.")
        if not comtrade_df.empty:
            summary = comtrade_df.groupby("refYear")["primaryValue"].sum().reset_index()
            st.dataframe(summary)
