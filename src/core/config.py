import os

# --- Configurações de API e Variáveis de Ambiente ---
HARVARD_API_KEY: str | None = None
COMTRADE_API_KEY: str | None = None

# --- URLs Base ---
COMEXSTAT_BASE_URL: str = "https://api-comexstat.mdic.gov.br"
HARVARD_BASE_URL: str = "https://dataverse.harvard.edu"

# --- Arquivos e Recursos ---
# O caminho para o certificado ComexStat (necessário para a requisição)
COMEXSTAT_CERT_PATH: str = "resources/certificate/mdic-gov-br.pem"

# Diretório para cache local dos dados (Parquet)
CACHE_DIR: str = "data_cache"

# --- Parâmetros de Consulta Padrão ---

# Harvard Dataverse
HARVARD_DOI: str = "doi:10.7910/DVN/T4CHWJ"
HARVARD_TARGET_FILE: str = "hs92_country_product_year_4.csv"

# Comtrade (Parâmetros de Exemplo para a query original)
COMTRADE_DEFAULT_FILTERS = {
    "partnerCode": "76",
    "typeCode": "C",
    "freqCode": "A",
    "clCode": "HS",
    "period": "2023",
    "cmdCode": "AG4",  # Alterado para AG4 (all goods - 4 digit level)
    "flowCode": "X",  # Exports
    "breakdownMode": "plus",
    "includeDesc": True,
    "reporterCode": None,
    "partner2Code": "0",
    "customsCode": "C00",
    "motCode": None,
}

# ComexStat (Parâmetros de Exemplo para a query original)
COMEXSTAT_DEFAULT_PARAMS = {
    "flow": "export",
    "period_from": "2023-01",
    "period_to": "2023-12",
    "data_type": "general",
    "filters": [
        # {"filter": "partner", "values": ["245"]},  # Exemplo: 245 é a China
        {"filter": "state", "values": ["23"]},  # Exemplo: 23 é o Ceará
    ],
    "details": ["state", "heading"],
    "metrics": ["metricFOB", "metricKG", "metricCIF"],
}

# --- Constantes do Dashboard ---
# O código do estado alvo para análise de VCR/PCI (e.g., Ceará: 23)
TARGET_STATE_CODE = 23

# O código do parceiro alvo para filtros (e.g., China: 245)
TARGET_PARTNER_CODE = 245
