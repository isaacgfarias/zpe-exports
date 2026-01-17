# %%
import streamlit as st
# import pandas as pd  # Importação mantida para tipagem e operações básicas

# Importação dos módulos refatorados
from core.data_loader import get_all_data
from components.dashboard_tabs import (
    render_tab_compare,
    render_tab_comex,
    render_tab_harvard,
    render_tab_comtrade,
)

# Configuração inicial do Streamlit
st.set_page_config(
    page_title="Dashboard Comércio Internacional",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- 1. CARREGAMENTO CENTRALIZADO DE DADOS ---
# A função get_all_data já trata a checagem de arquivos e os decoradores @st.cache_data
comexstat_df, harvard_df, comtrade_df = get_all_data()

# %%
st.title("Dashboard de Análise de Comércio Internacional 📊")
st.markdown(
    "Este painel apresenta dados de comércio extraídos de fontes distintas: ComexStat, Harvard Dataverse e Comtrade da ONU."
)

# Criação e Renderização das Abas (Chama os componentes refatorados)
tab_compare, tab_comex, tab_harvard, tab_comtrade = st.tabs(
    [
        "Análise Comparativa",
        "ComexStat",
        "Harvard Dataverse",
        "Comtrade",
    ]
)

# Aba Análise Comparativa
with tab_compare:
    render_tab_compare(comexstat_df, harvard_df, comtrade_df)

# Aba ComexStat
with tab_comex:
    render_tab_comex(comexstat_df)

# Aba Harvard Dataverse
with tab_harvard:
    render_tab_harvard(harvard_df)

# Aba Comtrade
with tab_comtrade:
    render_tab_comtrade(comtrade_df)

# %%
