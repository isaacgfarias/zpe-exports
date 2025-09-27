# %%
import polars as pl

# import streamlit as st
import os

from comexstat import ComexStat
from comtrade import Comtrade
from dataverse import HarvardDataverse

# %% COMTRADE's
comtrade = Comtrade()

comtrade_df = pl.DataFrame(
    comtrade.query_data(
        # typeCode='C'
        # ,freqCode='A'
        # ,clCode='HS'
        partnerCode="76"
    )
)


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

harvard_df = harvard_df.filter(pl.col("year") == pl.col("year").max())


# %% COMEXSTAT's
comex = ComexStat()

comexstat_df = comex.query_comexstat_data(
    flow="export",
    period_from="2024-01",
    period_to="2024-12",
    filters=[{"filter": "state", "values": [23]}],
    metrics=["metricFOB"],
    details=["state", "heading"],
)

print("Comexstat schema:")
print(comexstat_df.schema)
comexstat_df.write_csv("Dashboard-Base/comexstat_data.csv")
print("\nHarvard schema:")
print(harvard_df.schema)
harvard_df.write_csv("Dashboard-Base/harvard_data.csv")
print("\nComtrade schema:")
print(comtrade_df.schema)
comtrade_df.write_csv("Dashboard-Base/comtrade_data.csv")

# # Convert columns to consistent data types
# # Fix year columns - convert all to Int64
# comexstat_df = comexstat_df.with_columns(
#     pl.col("year").cast(pl.Int64),
#     pl.col("headingCode").cast(pl.Utf8),
#     pl.col("metricFOB").cast(pl.Float64)
# )

# harvard_df = harvard_df.with_columns(
#     pl.col("year").cast(pl.Int64),
#     pl.col("product_hs92_code").cast(pl.Utf8),
#     pl.col("country_iso3_code").cast(pl.Utf8)
# )

# comtrade_df = comtrade_df.with_columns(
#     pl.col("refYear").cast(pl.Int64),
#     pl.col("cmdCode").cast(pl.Utf8),
#     pl.col("reporterISO").cast(pl.Utf8)
# )

# # Filter for valid numeric HS codes (4-digit codes)
# numeric_hs_filter = pl.col("product_hs92_code").str.contains(r"^\d{4}$")
# harvard_numeric = harvard_df.filter(numeric_hs_filter)

# numeric_cmd_filter = pl.col("cmdCode").str.contains(r"^\d{4}$")
# comtrade_numeric = comtrade_df.filter(numeric_cmd_filter)

# # First merge: Harvard and Comtrade
# merged_harvard_comtrade = harvard_numeric.join(
#     comtrade_numeric,
#     left_on=["product_hs92_code", "year", "country_iso3_code"],
#     right_on=["cmdCode", "refYear", "reporterISO"],
#     how="left",
#     suffix="_comtrade"
# )

# # Prepare comexstat data - aggregate to country level
# comexstat_agg = comexstat_df.group_by(["headingCode", "year"]).agg(
#     pl.sum("metricFOB").alias("total_metricFOB"),
#     pl.count().alias("state_records_count")
# )

# # Second merge: Add comexstat data
# final_df = merged_harvard_comtrade.join(
#     comexstat_agg,
#     left_on=["product_hs92_code", "year"],
#     right_on=["headingCode", "year"],
#     how="left",
#     suffix="_comexstat"
# )

# print(f"Final merged dataset shape: {final_df.shape}")
# print("\nFinal columns:")
# print(final_df.columns)

# # Show sample of the merged data
# print("\nSample of merged data:")
# print(final_df.head(5))

# # print (final_df)
# # final_df.write_csv('Dashboard-Base/test_dashboard.csv')
