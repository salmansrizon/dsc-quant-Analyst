import requests
from bs4 import BeautifulSoup
import pandas as pd
pd.set_option('future.no_silent_downcasting', True)
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode


# logging utility
from utils.logger import Log
from utils.bigquery_helper import BigQueryHelper
from scrapers.common import HEADERS, get_session, get_date_range, get_symbol_universe, header_keyed_rows

# create a module-level logger with file output
from datetime import datetime as _dt

log_filename = f"logs/priceArchive_{_dt.now().strftime('%Y%m%d_%H%M%S')}.log"
logger = Log(name="priceArchive", filename=log_filename)

def scrape_price_archive(symbol, from_date, to_date):
    """Scrape price archive data for a specific symbol and date range"""
    url = "https://lankabd.com/Home/PriceArchive"
    
    try:
        logger.info(f"Starting scrape for symbol={symbol}, range={from_date} to {to_date}")
        session = get_session()
        
        headers = HEADERS.copy()
        headers.update({
            'Referer': 'https://lankabd.com/',
            'Dnt': '1',
        })
        
        # First request to set cookies
        logger.debug("Making initial request to root to obtain cookies")
        session.get("https://lankabd.com/", headers=headers, timeout=30)
        
        # Build URL with parameters
        params = {
            'symbol': symbol,
            'fromDate': from_date,
            'toDate': to_date
        }
        
        request_url = f"{url}?{urlencode(params)}"
        logger.debug(f"Constructed request URL: {request_url}")
        
        response = session.get(request_url, headers=headers, timeout=30)
        response.raise_for_status()
        logger.debug("Received response from price archive page")
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find the table with price data
        table = soup.find('table', {'class': ['table', 'dataTable', 'price-table']})
        
        if not table:
            # Try to find any table
            tables = soup.find_all('table')
            if len(tables) > 1:
                table = tables[1]  # Usually the second table is the data table
        
        if not table:
            logger.warning(f"No table found for {symbol}")
            return None
        
        # Header-zip the chosen table via the shared helper (#60).
        rows = header_keyed_rows(table)
        if not rows:
            logger.warning(f"Parsed table but no header-keyed rows for {symbol}")
            return None
        df = pd.DataFrame(rows)

        # Standardize column names to match migration and CSV headers
        df.rename(columns={
            'symbol': 'Symbol',
            'date': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            # Alternative cases
            'Opening': 'Open',
            'Highest': 'High',
            'Lowest': 'Low',
            'Closing': 'Close',
            'Volume ': 'Volume',
            'LTP*': 'LTP',
            'CLOSEP*': 'Close',
            'YCP*': 'YCP'
        }, inplace=True, errors='ignore')

        # Add symbol column and indicators placeholders if not present
        if 'Symbol' not in df.columns:
            df['Symbol'] = symbol
        
        # Add technical indicator placeholders consistent with schema
        df['SMA_20'] = None
        df['Volatility_20d'] = None
        df['Price_Momentum_20d'] = None
        if 'Sector' not in df.columns:
            df['Sector'] = None

        logger.info(f"Successfully parsed data for {symbol} ({len(df)} rows)")
        
        return df
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while fetching {symbol}: {str(e)[:50]}")
        return None
    except Exception as e:
        logger.error(f"General error processing {symbol}: {str(e)[:50]}")
        return None


def scrape_all_symbols_price_data(from_date=None, to_date=None):
    """Scrape price data for all symbols from the sectors file"""
    bq = BigQueryHelper()
    
    # Global range fallback
    if to_date is None:
        _, to_date = get_date_range(years=3)
    
    symbols = get_symbol_universe(logger=logger)
    if not symbols:
        logger.error("No symbols found to scrape")
        return None
    
    logger.info(f"Total symbols to process: {len(symbols)}")
    
    all_data = []
    success_count = 0
    failed_symbols = []
    
    for idx, symbol in enumerate(symbols, 1):
        # Fetch incremental date for THIS specific symbol
        symbol_from_date = from_date
        if symbol_from_date is None:
             # Check database for last record of this specific symbol
             try:
                 # Note: In a large table, searching by symbol might be slow without proper indexing.
                 # Our migration already has idx_price_archive_symbol_date.
                 last_date = bq.get_last_date('lankabd_price_archive', 'Date', filter_column='Symbol', filter_value=symbol)
                 if last_date:
                     # Start from the day AFTER the last record
                     last_dt = pd.to_datetime(last_date)
                     symbol_from_date = (last_dt + timedelta(days=1)).strftime('%Y-%m-%d')
                     logger.debug(f"[{symbol}] Resuming from {symbol_from_date}")
                 else:
                     symbol_from_date, _ = get_date_range(years=3)
             except Exception as e:
                 logger.warning(f"Error parsing date for {symbol} ({last_date}): {e}")
                 symbol_from_date, _ = get_date_range(years=3)

        logger.info(f"[{idx}/{len(symbols)}] Fetching price data for {symbol} (from {symbol_from_date})...")
        
        df = scrape_price_archive(symbol, symbol_from_date, to_date)
        
        if df is not None and len(df) > 0:
            import numpy as np
            df = df.replace(['-', 'N/A', 'n/a', 'nan', 'inf', '-inf'], np.nan)
            
            # Convert numeric columns to float to match BigQuery schema
            for col in df.columns:
                if col not in ['Date', 'Symbol', 'Sector', 'Trade']:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
            
            success_count += 1

            all_data.append(df)
            logger.debug(f"Received {len(df)} rows for {symbol}")
        else:
            logger.warning(f"No data returned for {symbol}")
            failed_symbols.append(symbol)
        
        # Be polite to the server
        time.sleep(0.5)
    
    # Combine all data
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Upload to BigQuery ONCE to avoid rate limits
        try:
            bq.upload_dataframe(combined_df, 'lankabd_price_archive')
            logger.info(f"Successfully uploaded {len(combined_df)} records to BigQuery.")
        except Exception as e:
            logger.error(f"Error uploading to BigQuery: {e}")
        
        # Save to CSV
        output_file = 'lankabd_price_archive_3years.csv'
        combined_df.to_csv(output_file, index=False)
        
        logger.info("\n" + "="*60)
        logger.info(f"Price data successfully saved to {output_file}")
        logger.info("="*60)
        logger.info(f"Total symbols with data: {success_count}/{len(symbols)}")
        logger.info(f"Total rows: {len(combined_df)}")
        logger.debug(f"Columns: {list(combined_df.columns)}")
        
        if failed_symbols:
            logger.warning(f"\nSymbols with no data ({len(failed_symbols)}): {', '.join(failed_symbols[:10])}" + (f", ... and {len(failed_symbols)-10} more" if len(failed_symbols) > 10 else ""))
        
        return combined_df
    else:
        print("\nNo data collected from any symbol")
        return None


def scrape_price_archive_by_symbol(symbol, from_date=None, to_date=None):
    """Scrape price data for a specific symbol"""
    
    if from_date is None or to_date is None:
        from_date, to_date = get_date_range(years=3)
    
    logger.info(f"Fetching price data for {symbol}")
    logger.info(f"Date range: {from_date} to {to_date}\n")
    
    df = scrape_price_archive(symbol, from_date, to_date)
    
    if df is not None and len(df) > 0:
        output_file = f'lankabd_price_{symbol}_{from_date}_to_{to_date}.csv'
        df.to_csv(output_file, index=False)
        logger.info(f"Data saved to {output_file}")
        logger.info(f"Total rows: {len(df)}")
        return df
    else:
        logger.warning(f"No price data found for {symbol}")
        return None


def scrape_price_archive_by_sector(sector=None, from_date=None, to_date=None):
    """Scrape price data for all symbols in a specific sector"""
    
    if from_date is None or to_date is None:
        from_date, to_date = get_date_range(years=3)
    
    symbols = get_symbol_universe(sector=sector, logger=logger)

    if len(symbols) == 0:
        logger.error(f"No symbols found for sector: {sector}")
        return None
    
    logger.info(f"\nFetching price data for sector {sector or 'all'}")
    logger.info(f"Date range: {from_date} to {to_date}")
    logger.info(f"Total symbols: {len(symbols)}\n")
    
    all_data = []
    success_count = 0
    
    for idx, symbol in enumerate(symbols, 1):
        logger.info(f"[{idx}/{len(symbols)}] Fetching {symbol}...")
        
        price_df = scrape_price_archive(symbol, from_date, to_date)
        
        if price_df is not None and len(price_df) > 0:
            all_data.append(price_df)
            logger.debug(f"Received {len(price_df)} rows for {symbol}")
            success_count += 1
        else:
            logger.warning(f"No price records for {symbol}")
        
        time.sleep(0.5)
    
    # Combine and save
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        
        sector_name = sector.replace(" ", "_") if sector else "all_sectors"
        output_file = f'lankabd_price_{sector_name}_3years.csv'
        combined_df.to_csv(output_file, index=False)
        
        logger.info("\n" + "="*60)
        logger.info(f"Price data saved to {output_file}")
        logger.info("="*60)
        logger.info(f"Total symbols with data: {success_count}/{len(symbols)}")
        logger.info(f"Total rows: {len(combined_df)}")
        
        return combined_df
    else:
        logger.warning("No price data collected")
        return None



if __name__ == "__main__":
    # Local execution support
    scrape_all_symbols_price_data()
