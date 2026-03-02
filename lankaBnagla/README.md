# Lankabangla Stock Data Scraper - Complete Guide

Complete web scraping solution for Lankabangla financial portal stock market data.

---

## 📋 Overview

Two main scripts work together to collect comprehensive stock market data:

| Script | Purpose | Source | Output |
|--------|---------|--------|--------|
| **main.py** | Fetch latest stock data matrix | DataMatrix | All 414 stocks, current fundamentals |
| **priceArchive.py** | Fetch historical price data | PriceArchive | Price history for last 3 years |

---

## 📊 main.py - Stock Data Matrix

**Fetches from**: `https://lankabd.com/Home/DataMatrix`

### What it does:
- Extracts all 414 stock symbols from 21 different sectors
- Gets current market data (price, volume, technical indicators)
- Supports filtering by sector
- Saves data to CSV with 34 columns of data

### Available Sectors:
Bank, Cement, Ceramics, Corporate Bond, Debenture, Engineering, Financial Institutions, Food & Allied, Fuel & Power, G-SEC, Insurance, IT Sector, Jute, Miscellaneous, Mutual Funds, Paper & Printing, Pharmaceuticals & Chemicals, Services & Real Estate, Stock Brokers, Tannery Industries, Telecommunication, Textile, Travel & Leisure

### Usage:

```python
from main import scrape_lankabd, scrape_all_sectors

# Option 1: All data
df = scrape_lankabd()  # → lankabd_data.csv

# Option 2: Specific sector
df = scrape_lankabd(sector='Bank')  # → lankabd_data_bank.csv

# Option 3: All sectors separately then combined
df = scrape_all_sectors()  # → lankabd_data_all_sectors.csv
```

### Output Files:
- `lankabd_data.csv` - All stocks (414 rows × 34 columns)
- `lankabd_data_bank.csv` - Bank sector only (36 stocks)
- `lankabd_data_all_sectors.csv` - All sectors combined (414 rows)

### Data Columns (34 total):
`Symbol, Sector, LTP, Open, High, Low, Close, YCP, Change, Change %, YCP-Close, YCP % change, Volume(Qty), Value(Turnover), MktCap, PE, EPS, NAV, Reserve, Contingent, Provision, General, Director, EPS SH, Audited P/E, RSI, Beta, Turnover Velocity, Buy/Sell, Market Category...`

---

## 💰 priceArchive.py - Historical Price Data

**Fetches from**: `https://lankabd.com/Home/PriceArchive`

### What it does:
- Fetches 3 years of daily historical price data
- Covers all 414 symbols from main.py
- Gets 30 columns including price, volume, and technical indicators
- Supports filtering by symbol or sector
- Custom date range selection

### Date Range:
- **Default**: Last 3 years (2023-02-28 to 2026-02-27)
- **Custom**: Can specify any date range

### Usage:

```python
from priceArchive import (
    scrape_all_symbols_price_data,
    scrape_price_archive_by_symbol,
    scrape_price_archive_by_sector
)

# Option 1: All symbols (all 414 stocks)
df = scrape_all_symbols_price_data()  # → lankabd_price_archive_3years.csv

# Option 2: Single symbol
df = scrape_price_archive_by_symbol('ABBANK')  # → lankabd_price_ABBANK_*.csv

# Option 3: Sector-wide
df = scrape_price_archive_by_sector('Bank')  # → lankabd_price_Bank_3years.csv

# Custom date range
df = scrape_price_archive_by_symbol(
    'ABBANK',
    from_date='2024-01-01',
    to_date='2025-12-31'
)
```

### Output Files:
- `lankabd_price_archive_3years.csv` - All 414 symbols combined
- `lankabd_price_ABBANK_2023-02-28_to_2026-02-27.csv` - Individual symbol
- `lankabd_price_Bank_3years.csv` - Sector-specific

### Data Per Symbol:
~716 daily records per stock (3-year period)

### Data Columns (30 total):
Date, Symbol, LTP, High, Low, Open, Close, YCP, Change %, Weekly %, Bi-weekly %, Monthly %, Yearly %, Trade, Turnover(mn), Volume(Qty), Volume Change %, Block Max/Min Price, Block Trades/Quantity/Value, Market Cap, PE, RSI, Beta, Velocity...

---

## 🚀 Quick Start

### 1. Run Stock Data Collection:
```bash
cd /Users/salmansakib/Documents/Projects/Data_Science_projects/lankaBnagla
source venv/bin/activate
python main.py
```

### 2. Run Price History Collection:
```bash
python priceArchive.py
```

### 3. Run Demo Examples:
```bash
python priceArchive_demo.py
```

---

## 📁 Generated Files

### After main.py:
```
lankabd_data.csv (86 KB)
lankabd_data_bank.csv (7.5 KB)
lankabd_data_all_sectors.csv (86 KB)
```

### After priceArchive.py:
```
lankabd_price_ABBANK_2023-02-28_to_2026-02-27.csv (106 KB)
lankabd_price_archive_3years.csv (large file - multiple MB)
lankabd_price_Bank_3years.csv (1.5+ MB)
```

---

## 🔍 Data Analysis Examples

### Example 1: Compare sector performance
```python
import pandas as pd

# Load all stocks
stocks = pd.read_csv('lankabd_data_all_sectors.csv')

# Group by sector
sector_stats = stocks.groupby('Sector').agg({
    'LTP': 'mean',
    'Volume(Qty)': 'sum'
}).sort_values('LTP', ascending=False)

print(sector_stats)
```

### Example 2: Find top gainers
```python
import pandas as pd

stocks = pd.read_csv('lankabd_data.csv')
stocks['Change %'] = pd.to_numeric(stocks['Change %'], errors='coerce')

top_gainers = stocks.nlargest(10, 'Change %')[['Symbol', 'Sector', 'LTP', 'Change %']]
print(top_gainers)
```

### Example 3: Analyze price trends
```python
import pandas as pd
import matplotlib.pyplot as plt

# Load price data
df = pd.read_csv('lankabd_price_ABBANK_2023-02-28_to_2026-02-27.csv')
df['Date'] = pd.to_datetime(df['Date'], format='%Y/%m/%d')

# Plot trend
plt.figure(figsize=(14, 6))
plt.plot(df['Date'], df['CLOSEP*'], label='Close Price')
plt.title('ABBANK Stock Price Trend')
plt.xlabel('Date')
plt.ylabel('Price (BDT)')
plt.legend()
plt.grid(True)
plt.show()
```

---

## ⚙️ Performance

| Task | Time | Notes |
|------|------|-------|
| Run main.py | 2-3 min | Fetch all 414 stocks with filters |
| Fetch one symbol price | 2-3 sec | ~716 records |
| Fetch all symbols prices | 5-10 min | Includes server delays |
| Fetch sector prices | 1-2 min | Bank sector: 36 stocks |

---

## 📦 Dependencies

```
requests==2.31.0
beautifulsoup4==4.12.2
pandas>=2.2.0
lxml>=4.10.0
```

Install with:
```bash
pip install -r requirements.txt
```

---

## 🛠️ Troubleshooting

### No data table found error
- Make sure you're connected to the internet
- The website might be rate-limiting - wait and retry
- Update the table selector if the website changed

### Virtual environment issues
```bash
cd /Users/salmansakib/Documents/Projects/Data_Science_projects/lankaBnagla
source venv/bin/activate
```

### Missing CSV files
- Run `main.py` first to generate `lankabd_data_all_sectors.csv`
- This is required for `priceArchive.py` to work

---

## 📝 Notes

- **Server Friendly**: Scripts include delays to avoid overwhelming the server
- **Retry Logic**: Automatic retries for failed requests
- **Date Format**: Price data uses `YYYY/MM/DD` format
- **Large Files**: Combined price archive can be large (100+ MB) - normal
- **Update Frequency**: Main.py data updates daily on the website

---

## 📧 Support

For issues or questions:
1. Check that all dependencies are installed
2. Verify internet connection
3. Try running individual functions vs full script
4. Check generated files for correct format

---

Created: February 27, 2026
Last Updated: February 27, 2026
