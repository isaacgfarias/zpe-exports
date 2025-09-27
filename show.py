import polars as pl
import os

from dataverse import HarvardDataverse


TOKEN = os.getenv("HARVARD_API_KEY")
DOI: str = "doi:10.7910/DVN/T4CHWJ"

dataverse = HarvardDataverse(api_token=TOKEN)

schema_override = {"product_hs92_code": pl.Utf8}

harvard_df = dataverse.import_df(
    doi=DOI,
    target_filename="hs92_country_product_year_4.csv",
    polars_reader_options={"schema_overrides": schema_override},
)

latest_df = harvard_df.filter(pl.col("year") == pl.col("year").max())

print(latest_df)

harvard_df = harvard_df.select(harvard_df)
