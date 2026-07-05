"""
Fetch BTC (or any coin) full price history directly from your own CoinStats API key
and produce the date,price CSV that regenerate_chart.py needs.

Verified against CoinStats's API documentation. 

USAGE:
    export COINSTATS_API_KEY="your-key-here"
    python fetch_coinstats_api.py bitcoin all btc_prices.csv

    args: <coinId> <period: all|24h|1w|1m|3m|6m|1y> <output_csv_path>
"""

import sys
import os
import json
import requests
import pandas as pd

API_URL = "https://api.coinstats.app/v1/coins/charts"


def fetch_chart(coin_id: str, period: str, api_key: str) -> pd.DataFrame:
    resp = requests.get(
        API_URL,
        headers={"X-API-KEY": api_key},
        params={"coinIds": coin_id, "period": period},
        timeout=30,
    )
    if resp.status_code != 200:
        # Print the response body -- CoinStats returns a useful message/requestId on errors
        print(f"CoinStats API returned {resp.status_code}:")
        print(resp.text)
    resp.raise_for_status()
    data = resp.json()

    # Response is a list with one object per requested coin:
    # [{"coinId": "bitcoin", "chart": [[ts, price, vol, mktcap], ...], "errorMessage": "..."}]
    entry = data[0] if isinstance(data, list) else data
    if entry.get("errorMessage"):
        raise RuntimeError(f"CoinStats error for {coin_id}: {entry['errorMessage']}")

    chart = entry["chart"]
    df = pd.DataFrame(chart, columns=["ts", "price", "vol_or_flag", "market_cap"])
    df["date"] = pd.to_datetime(df["ts"], unit="s", utc=True).dt.tz_localize(None)
    df = df[["date", "price"]].drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)

    # collapse to one point per calendar day (recent data can be intraday)
    daily = df.set_index("date")["price"].resample("D").last().dropna()
    return daily.reset_index()


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    coin_id, period, out_csv = sys.argv[1], sys.argv[2], sys.argv[3]
    api_key = os.environ.get("COINSTATS_API_KEY")
    if not api_key:
        print("ERROR: set COINSTATS_API_KEY environment variable first.")
        sys.exit(1)

    prices = fetch_chart(coin_id, period, api_key)
    prices.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv}: {len(prices)} daily points, "
          f"{prices['date'].min().date()} to {prices['date'].max().date()}")


if __name__ == "__main__":
    main()



