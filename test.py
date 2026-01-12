import polars as pl


comtrade = pl.read_csv("resources/comtrade_data.csv").to_pandas()

print(comtrade.columns)

print("\n", comtrade["refMonth"].head())
