# Bitcoin Halving Cycles Interactive Chart

An interactive chart that aims to discover recurring patterns in Bitcoin's market cycles. 

## Features

Per cycle, it shows:
- **% Drawdown from cycle-peak to cycle-low trough (before a new ATH is eventually made)**
- **Number of days from halving to post-halving cycle peak** 

Interactive Plotly chart includes:
- `Range slider` at the bottom to navigate through the timeline. 
- `Preset zoom buttons` (6m/1y/2y/4y/All) at the top-left of the chart for quick jumps
- `Stat cards` below the chart summarizing each cycle (peak, days to peak, trough, drawdown)
and more

## Data Requirements

### 1. Bitcoin Price Data

We need the full daily BTC-USD price history (daily granularity), going back as far as possible. 

Although there are several ways to source the data, I chose to use the CoinStats API. The first script I wrote retrieves the historical Bitcoin price data and outputs a CSV with two columns —— `date` and `price`. This CSV serves as the input for a second script, which generates the interactive chart. 

### 2. Bitcoin Halving Dates

Once halving dates are confirmed, update the `HALVINGS` list at the top of the second script (`regenerate_chart.py`).

There is also a need to update the projected next-halving line on the chart, which is based on `NEXT_HALVING_ESTIMATE`. It is a hardcoded guess, whereby we move it 4 years past the lastest halving date. This is because halvings occur exactly every 210,000 blocks, which is approximately every four years. 

## Quick Setup
1. Save the scripts (`fetch_coinstats_api.py` and `regenerate_chart.py`) in the same folder
2. Open Terminal
3. Navigate to the folder where you saved the .py scripts (E.g., cd ~/Downloads/Cycle) --> I saved the scripts under a folder named 'Cycle' in my Downloads folder. 

## Executing/Running the Commands in the Terminal

Execute the following commands line by line in the Terminal.

### 1. 
```bash
pip3 install requests pandas # installs two Python libraries the scripts depend on 
```

### 2. 
```bash
export COINSTATS_API_KEY="your-actual-api-key" 
```

This line sets a temporary variable in your terminal session holding your API key. The script reads this via os.environ.get("COINSTATS_API_KEY") rather than having the key typed directly into the file —— that way you're not saving your key in plain text inside a script you might share somewhere.

**Important**: Replace `your-actual-api-key` with your own personal CoinStats API key. 

### 3.
```bash
python fetch_coinstats_api.py bitcoin all btc_prices.csv 
```

This runs the first script with 3 arguments it expects (defined by sys.argv in the script):
- bitcoin --> which coin to fetch
- all --> the time period (full history)
- btc_prices.csv --> the CSV filename it should save the output to

### 4. 
```bash
python regenerate_chart.py btc_prices.csv btc_halving_cycles_interactive.html
```
This runs the second script with 2 arguments it expects:
- btc_prices.csv --> the input file
- btc_halving_cycles_interactive.html --> the HTML filename it should save the output to

**Note**: These scripts write files to your computer. After running them, you have to manually open the resulting .html file in the same folder to view the interactive chart. Re-run the scripts anytime for up-to-date data. 

## Clarifications

Peaks are defined using the "significant peak" method: the point that precedes the deepest subsequent drawdown, not just the highest window price. In plain English: instead of asking "What was the highest price reached in this cycle window?" (which can accidentally grab a fresh high made just before the window cuts off, like March 2024), it asks "which high, once broken, caused the worst subsequent decline before price recovered back above it?" 

