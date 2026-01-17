import streamlit as st
import pandas as pd
import plotly.express as px

from core.analytics import (
    calcular_vcr_ceara_brasil,
    obter_vcr_brasil_mundo,
    obter_pci_e_distancia,
    normalizar_vcr,
    format_fob_metric,
    carregar_mapeamento_ncm_cnae,
    classificar_cenarios_vcr,
    calcular_indice_prioridade_ajustado,
)
from core.priority_index import calcular_indice_prioridade_ajustado
from core.vcr_calculators import calcular_vcr_dentro_selecao


def render_tab_compare(comexstat_df, harvard_df, comtrade_df):
    """
    Renderiza a aba de Análise Comparativa consolidando métricas SH4,
    mapeamento NCM/CNAE e os 7 Cenários Estratégicos.
    """
    st.header("Análise Comparativa de Especialização e Complexidade")

    # --- 0. Controles de Pesos ---
    st.markdown("### 🎚️ Ajuste de Pesos para o Índice de Prioridade")
    col_vcr_ce, col_vcr_br, col_pci, col_dist = st.columns(4)

    pesos_dict = {
        "vcr_ceara": col_vcr_ce.slider("Peso VCR Estadual", 0.0, 1.0, 0.4, 0.05),
        "vcr_brasil": col_vcr_br.slider("Peso VCR País", 0.0, 1.0, 0.3, 0.05),
        "pci": col_pci.slider("Peso PCI", 0.0, 1.0, 0.3, 0.05),
        "distancia": col_dist.slider("Peso Distância", 0.0, 1.0, 0.4, 0.05),
    }

    # --- 1. Processamento de Dados ---
    with st.spinner("Consolidando métricas e classificando cenários..."):
        # Métricas base (SH4)
        df_ce = calcular_vcr_ceara_brasil(comexstat_df)
        df_br = obter_vcr_brasil_mundo(harvard_df)
        df_metrics = obter_pci_e_distancia(harvard_df)

        # Descrições dos códigos HS
        df_descricoes = comexstat_df[["headingCode", "heading"]].drop_duplicates()
        df_descricoes["headingCode"] = (
            df_descricoes["headingCode"].astype(str).str.zfill(4)
        )

        # Merge principal
        df_final = df_ce.merge(df_br, on="headingCode", how="left")
        df_final = df_final.merge(df_metrics, on="headingCode", how="left")
        df_final["headingCode"] = df_final["headingCode"].astype(str).str.zfill(4)
        df_final = df_final.merge(df_descricoes, on="headingCode", how="left").fillna(0)

        # --- CARREGAMENTO DO MAPEAMENTO NCM/CNAE ---
        PATH_MAP = "resources/NCM2012XCNAE20.xls"
        try:
            # Lê apenas as 3 primeiras colunas do Excel
            df_map_raw = pd.read_excel(PATH_MAP, skiprows=1, engine="xlrd").iloc[:, :3]
            df_map_raw.columns = ["ncm_raw", "desc_ncm", "cnae_raw"]

            # Limpeza e criação da chave HS4
            df_map_raw["ncm8"] = (
                df_map_raw["ncm_raw"]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.zfill(8)
            )
            df_map_raw["headingCode"] = df_map_raw["ncm8"].str[:4]

            # Agrupamento para exibição em linha única
            df_ponte = (
                df_map_raw.groupby("headingCode")
                .agg(
                    {
                        "ncm8": lambda x: ", ".join(sorted(set(x.astype(str)))),
                        "cnae_raw": lambda x: ", ".join(
                            sorted(
                                set(str(val) for val in x if str(val).lower() != "nan")
                            )
                        ),
                    }
                )
                .reset_index()
            )

            df_final = df_final.merge(df_ponte, on="headingCode", how="left")
        except Exception as e:
            st.warning(f"Aviso: Não foi possível carregar o Tradutor NCM/CNAE: {e}")
            df_final["ncm8"] = "Não disp."
            df_final["cnae_raw"] = "Não disp."

        # Aplica a lógica dos 7 cenários (Classificação Baseada na Imagem)
        df_final = classificar_cenarios_vcr(df_final)

        # Normalização e Cálculo do Índice de Prioridade
        for col in [
            "VCR_Ceara_Brasil",
            "VCR_Brasil_Mundo",
            "PCI",
            "Distancia_Parceiros",
        ]:
            df_final = normalizar_vcr(df_final, col)

        df_final = calcular_indice_prioridade_ajustado(df_final, pesos_dict)
        df_final = df_final.sort_values(
            by="INDICE_PRIORIDADE_AJUSTADO", ascending=False
        )

    # --- 2. Filtros de Interface ---
    st.markdown("---")
    col_f1, col_f2 = st.columns(2)

    all_codes = sorted(df_final["headingCode"].unique().tolist())
    start_hs = col_f1.selectbox("Filtrar HS (Início)", ["Início"] + all_codes)

    cenarios = ["Todos"] + sorted(df_final["Cenário Estratégico"].unique().tolist())
    filtro_cenario = col_f2.selectbox("Filtrar por Cenário Estratégico", cenarios)

    # Aplicação dos filtros
    df_view = df_final.copy()
    if start_hs != "Início":
        df_view = df_view[df_view["headingCode"] >= start_hs]
    if filtro_cenario != "Todos":
        df_view = df_view[df_view["Cenário Estratégico"] == filtro_cenario]

    # --- 3. Exibição da Tabela Principal ---
    if not df_view.empty:
        mapping = {
            "headingCode": "HS4",
            "heading": "Produto (SH4)",
            "Cenário Estratégico": "Posicionamento Estratégico",
            "ncm8": "NCMs Relacionados",
            "cnae_raw": "CNAE 2.0",
            "INDICE_PRIORIDADE_AJUSTADO": "Prioridade",
            "VCR_Ceara_Brasil": "VCR Est.",
            "VCR_Brasil_Mundo": "VCR Nac.",
        }

        cols_display = [
            "headingCode",
            "heading",
            "Cenário Estratégico",
            "ncm8",
            "cnae_raw",
            "INDICE_PRIORIDADE_AJUSTADO",
            "VCR_Ceara_Brasil",
            "VCR_Brasil_Mundo",
        ]

        st.dataframe(
            df_view[cols_display].rename(columns=mapping),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Prioridade": st.column_config.ProgressColumn(
                    format="%.2f", min_value=0, max_value=1
                ),
                "Posicionamento Estratégico": st.column_config.TextColumn(
                    width="large"
                ),
                "NCMs Relacionados": st.column_config.TextColumn(width="medium"),
            },
        )

        csv = df_view[cols_display].to_csv(index=False).encode("utf-8")
        st.download_button("📥 Baixar Relatório", csv, "priorizacao.csv", "text/csv")
    else:
        st.info("Nenhum dado encontrado para os filtros aplicados.")


def render_tab_comex(comexstat_df):
    """
    Renderiza a aba ComexStat (Tab 2).
    """
    st.header("Dados do ComexStat")

    # --- FILTROS DENTRO DA ABA ---
    with st.expander("Opções de Filtragem", expanded=True):
        col_state, col_year, col_hs = st.columns(3)

        # 1. Filtro de Estado (UF)
        states = sorted(comexstat_df["state"].dropna().unique().tolist())
        default_state = ["Ceará"] if "Ceará" in states else states[:1]

        selected_states = col_state.multiselect(
            "Selecione o(s) Estado(s)",
            options=states,
            default=default_state,
            key="comex_state_select",
        )

        # 2. Filtro de Ano
        years = sorted(comexstat_df["year"].dropna().unique().astype(int).tolist())
        selected_years = col_year.multiselect(
            "Selecione o(s) Ano(s)", years, default=years, key="comex_year_select"
        )

        # 3. Filtro de Código HS (Lógica completa)
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
            "Selecione o(s) Código(s) HS", products_options, key="comex_hs_select"
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

    # --- DATAFRAME: EXIBIÇÃO DA VCR ---
    if not comexstat_filtered.empty:
        df_vcr_display = calcular_vcr_dentro_selecao(comexstat_filtered, comexstat_df)
        df_display = df_vcr_display[
            ["state", "headingCode", "heading", "metricFOB", "VCR"]
        ].copy()

        # Renomear e formatar
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

        # --- GRÁFICO DE BARRAS FOB (Top Headings) ---
        df_agg = (
            comexstat_filtered.groupby(["heading", "state"])["metricFOB"]
            .sum()
            .reset_index()
        )
        # Lógica de agrupamento "Demais/Outros" (MANTIDA)
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


def render_tab_harvard(harvard_df):
    """
    Renderiza a aba Harvard Dataverse (Tab 3).
    """
    st.header("Dados do Harvard Dataverse")

    # --- FILTROS DENTRO DA ABA ---
    with st.expander("Opções de Filtragem"):
        df_filtered = harvard_df.copy()
        col_year, col_country, col_hs = st.columns(3)

        # 1. Filtro de Ano
        years = sorted(df_filtered["year"].dropna().unique().astype(int).tolist())
        selected_years = col_year.multiselect(
            "Selecione o(s) Ano(s)", years, default=years, key="harvard_year_select"
        )
        if selected_years:
            df_filtered = df_filtered[df_filtered["year"].isin(selected_years)]

        # 2. Filtro de País
        countries_options = sorted(
            df_filtered["country_iso3_code"].dropna().unique().astype(str).tolist()
        )
        default_country = (
            ["BRA"] if "BRA" in countries_options else countries_options[:1]
        )

        selected_countries = col_country.multiselect(
            "Selecione o(s) País(es) (ISO3)",
            options=countries_options,
            default=default_country,
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

    harvard_filtered = df_filtered

    # --- AGREGAÇÃO PARA EXIBIÇÃO SUMARIZADA E LIMPA ---
    if not harvard_filtered.empty:
        group_cols = ["country_iso3_code", "year"]

        df_aggregated = (
            harvard_filtered.groupby(group_cols)
            .agg(
                {
                    "export_value": "sum",
                    "import_value": "sum",
                    "global_share": "mean",
                    "export_rca": "mean",
                    "distance": "mean",
                    "cog": "mean",
                    "pci": "mean",
                    "product_id": "count",
                }
            )
            .reset_index()
        )

        # Renomear colunas
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

        # Formatação
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

        st.subheader("Tabela Agregada por País e Ano (Sumário)")
        st.dataframe(df_aggregated, width="stretch")

        with st.expander("Visualizar Detalhes por Produto (Granularidade Máxima)"):
            st.dataframe(harvard_filtered, width="stretch")

        # --- GRÁFICO DE BARRA DE PROPORÇÃO DE PRODUTOS ---
        st.subheader("Distribuição de Exportação por Produto (Top 10)")
        df_product_export = (
            harvard_filtered.groupby("product_hs92_code")
            .agg(
                total_export=("export_value", "sum"),
                average_pci=("pci", "mean"),
            )
            .reset_index()
        )

        total_global_export = df_product_export["total_export"].sum()
        df_product_export["proportion"] = (
            df_product_export["total_export"] / total_global_export
        )
        df_plot_product = df_product_export.sort_values(
            by="total_export", ascending=False
        ).head(15)

        fig = px.bar(
            df_plot_product,
            x="product_hs92_code",
            y="proportion",
            color="proportion",
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
            template="plotly_dark",
        )
        fig.update_layout(yaxis_tickformat=".0%")

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhum dado encontrado com os filtros aplicados.")


def render_tab_comtrade(comtrade_df):
    """
    Renderiza a aba Comtrade (Tab 4).
    """
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
