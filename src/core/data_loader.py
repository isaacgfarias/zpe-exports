import polars as pl
from polars.datatypes.classes import Utf8
import streamlit as st
import os

# Definição das constantes de caminho (mover de app.py)
COMEXSTAT_PATH = "resources/comexstat_data.csv"
HARVARD_PATH = "resources/harvard_data.csv"
COMTRADE_PATH = "resources/comtrade_data.csv"


def check_data_files():
    """Verifica a presença dos arquivos de dados e interrompe o app se não encontrados."""
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
    Carrega dados de um arquivo CSV usando Polars e converte para Pandas.
    (Lógica original de load_data)
    """
    # Schema de leitura forçada (MANTER A LÓGICA COMPLETA DE SCHEMAS AQUI)
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
            "refPeriodId": pl.Int16,
            "refYear": pl.Int16,
            "refMonth": pl.Int16,
            "period": pl.Int64,
            "reporterCode": pl.Utf8,
            "reporterISO": pl.Utf8,
            "reporterDesc": pl.Utf8,
            "flowCode": pl.Utf8,
            "flowDesc": pl.Utf8,
            "partnerCode": pl.Utf8,
            "partnerISO": pl.Utf8,
            "partnerDesc": pl.Utf8,
            "partner2Code": pl.Utf8,
            "partner2ISO": pl.Utf8,
            "partner2Desc": pl.Utf8,
            "classificationCode": pl.Utf8,
            "classificationSearchCode": pl.Utf8,
            "isOriginalClassification": pl.Boolean,  # Indicador booleano
            "cmdCode": pl.Utf8,
            "cmdDesc": pl.Utf8,
            "aggrLevel": pl.Int8,  # Nível de agregação costuma ser pequeno
            "isLeaf": pl.Boolean,  # Indicador booleano
            "customsCode": pl.Utf8,
            "customsDesc": pl.Utf8,
            "mosCode": pl.Utf8,
            "motCode": pl.Utf8,
            "motDesc": pl.Utf8,
            "qtyUnitCode": pl.Utf8,
            "qtyUnitAbbr": pl.Utf8,
            "qty": pl.Float64,  # Quantidade
            "isQtyEstimated": pl.Boolean,  # Indicador booleano
            "altQtyUnitCode": pl.Utf8,
            "altQtyUnitAbbr": pl.Utf8,
            "altQty": pl.Float64,  # Quantidade Alternativa
            "isAltQtyEstimated": pl.Boolean,  # Indicador booleano
            "netWgt": pl.Float64,  # Peso Líquido
            "isNetWgtEstimated": pl.Boolean,  # Indicador booleano
            "grossWgt": pl.Float64,  # Peso Bruto
            "isGrossWgtEstimated": pl.Boolean,  # Indicador booleano
            "cifvalue": pl.Float64,  # Valor CIF
            "fobvalue": pl.Float64,  # Valor FOB
            "primaryValue": pl.Float64,  # Valor Primário
            "legacyEstimationFlag": pl.Utf8,  # Flag de sistema antigo
            "isReported": pl.Boolean,  # Indicador booleano
            "isAggregate": pl.Boolean,  # Indicador booleano
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


def get_all_data():
    """Função principal para carregar e retornar todos os DataFrames."""
    check_data_files()

    comexstat_df = load_data(COMEXSTAT_PATH)
    harvard_df = load_data(HARVARD_PATH)
    comtrade_df = load_data(COMTRADE_PATH)

    # Garantir a coerência do tipo 'headingCode' para merge (mantida a correção)
    comexstat_df["headingCode"] = comexstat_df["headingCode"].astype(str)

    return comexstat_df, harvard_df, comtrade_df
