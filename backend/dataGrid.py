import requests
from bs4 import BeautifulSoup
import pandas as pd
pd.set_option('future.no_silent_downcasting', True)
import time
import json
import sys


# logging utility
from utils.logger import Log
from utils.bigquery_helper import BigQueryHelper
from datetime import datetime as _dt

# module logger
log_filename = f"logs/main_{_dt.now().strftime('%Y%m%d_%H%M%S')}.log"
logger = Log(name="main", filename=log_filename)

# Headers to mimic a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0',
}

def get_session():
    session = requests.Session()
    # Add retry strategy
    retry_strategy = requests.adapters.Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def get_available_sectors():
    """Fetch all available sectors from the DataMatrix page"""
    try:
        session = get_session()
        headers = HEADERS.copy()
        headers['Referer'] = 'https://lankabd.com/'
        
        logger.info("Fetching available sectors...")
        response = session.get("https://lankabd.com/", headers=headers, timeout=30)
        response = session.get("https://lankabd.com/Home/DataMatrix", headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        select = soup.find('select', {'id': 'sectorddl'})
        
        sectors = []
        if select:
            options = select.find_all('option')
            for option in options:
                value = option.get('value', '').strip()
                text = option.text.strip()
                if value and value != '--Select--':
                    sectors.append(value)
        
        logger.info(f"Found {len(sectors)} sectors")
        return sectors
    except Exception as e:
        logger.error(f"Error fetching sectors: {e}")
        return []

def scrape_lankabd(sector=None):
    url = "https://lankabd.com/Home/DataMatrix"
    
    try:
        logger.info(f"Fetching data from {url}...")
        
        # First, get the main page to set cookies
        session = get_session()
        
        # Add more headers to mimic a real browser
        headers = HEADERS.copy()
        headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Sec-Ch-Ua': '"Not.A/Brand";v="8", "Chromium";v="114"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://lankabd.com/',
            'Dnt': '1',
        })
        
        # First request to get cookies
        logger.debug("Making initial request to get cookies...")
        response = session.get("https://lankabd.com/", headers=headers, timeout=30)
        response.raise_for_status()
        
        # Now try to access the DataMatrix page
        logger.debug("Accessing DataMatrix page...")
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        logger.info("Successfully fetched the page")
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find the table with ID 'TableDataMatrix'
        table = soup.find('table', {'id': 'TableDataMatrix'})
        
        if not table:
            logger.warning("No data table found on the page")
            return None
            
        # Extract table headers
        headers_list = [th.text.strip() for th in table.find('thead').find_all('th')]
        
        # Extract table rows
        data = []
        rows = table.find('tbody').find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            data.append([col.text.strip() for col in cols])
        
        # Create a DataFrame
        df = pd.DataFrame(data, columns=headers_list)
        
        # Standardize column naming and drop unnamed columns
        df.rename(columns={
            'Symbol': 'Symbol',
            'Sector': 'Sector',
            'LTP': 'LTP',
            'Volume(Qty)': 'Volume(Qty)',
            'Value(Turnover)': 'Value(Turnover)',
        }, inplace=True, errors='ignore')

        # Drop truly empty or "Unnamed" columns that confuse SQL importers
        df = df.loc[:, ~df.columns.astype(str).str.contains('^Unnamed|^$', case=False, na=False)]
        df = df.loc[:, df.columns.astype(str) != ""] # Extra check for literally empty names

        # Replace standard placeholders with None (NULL) for SQL compat
        import numpy as np
        df = df.replace(['-', 'N/A', 'n/a', 'nan', 'inf', '-inf'], np.nan)

        # Convert numeric columns to match BigQuery schema
        for col in df.columns:
            if col not in ['Symbol', 'Sector', 'Trade', 'Market Category', 'Last Dividend Declaration Date', 'Last AGM Date', 'Date', 'captured_at_timestamp']:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')

        # Explicitly keep only common columns that exist in the database schema
        allowed_columns = [
            "Symbol", "Sector", "LTP", "Open", "High", "Low", "Close", "YCP", 
            "Change", "% Change", "Volume(Qty)", "Value(Turnover)", "Trade", 
            "Market_Cap", "PE", "EPS", "Div_Yield", "ROE", "Net_Asset", 
            "SMA_20", "SMA_50", "RSI_14", "Bollinger_Upper", "Bollinger_Lower", "Volatility_20d"
        ]
        df = df[[col for col in allowed_columns if col in df.columns]]

        # Apply sector filter if specified
        if sector:
            if 'Sector' in df.columns:
                df = df[df['Sector'] == sector]
                logger.info(f"Filtered data for sector: {sector} ({len(df)} rows)")
            else:
                logger.warning("'Sector' column not found in data")
        
        return df
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching the page: {e}")
        return None
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None

class PartialScrapeError(RuntimeError):
    """Raised when some sectors failed, so the universe must not be replaced."""


def scrape_all_sectors():
    """Fetch every sector and replace lankabd_datamatrix with the result.

    The upload is a full replace, and this table is the symbol universe: both
    other scrapers take their symbol list from it and the watchlist/portfolio/
    alert queries join against it. Replacing it with a partial scrape silently
    shrinks the universe everywhere downstream, with no way to tell that it
    happened and no way back except a successful rerun (ticket #45). So a
    partial scrape must not be allowed to land — a stale but complete universe
    beats a fresh but partial one.

    Raises PartialScrapeError if any sector failed to scrape. A sector that
    scrapes cleanly but holds no listings (Debenture and G-SEC (T.Bond) are
    always empty) is not a failure — scrape_lankabd returns None on error and
    an empty frame on an empty sector, and only the former blocks the upload.
    """
    sectors = get_available_sectors()

    if not sectors:
        logger.error("No sectors found")
        return None

    all_data = []
    failed_sectors = []

    for sector in sectors:
        logger.info(f"\n--- Fetching data for sector: {sector} ---")
        df = scrape_lankabd(sector=sector)

        if df is None:
            # The scrape itself broke — the sector's symbols are unknown, so
            # replacing the universe now would silently drop them.
            failed_sectors.append(sector)
            logger.warning(f"Failed to scrape sector: {sector}")
        elif len(df) > 0:
            all_data.append(df)
            logger.info(f"Successfully fetched {len(df)} rows")
        else:
            # Scraped fine, genuinely holds no listings. Not a failure.
            logger.info(f"Sector is empty: {sector}")

        time.sleep(1)  # Be polite to the server

    if not all_data:
        logger.warning("\nNo data collected from any sector")
        return None

    combined_df = pd.concat(all_data, ignore_index=True)

    # Always keep the local backup, even when the upload is refused below —
    # it is the only copy of a partial scrape's work.
    output_file = 'lankabd_data_all_sectors.csv'
    combined_df.to_csv(output_file, index=False)
    logger.info(f"\n✓ Combined data saved to {output_file}")

    if failed_sectors:
        raise PartialScrapeError(
            f"{len(failed_sectors)} of {len(sectors)} sectors returned no data "
            f"({', '.join(failed_sectors)}). Refusing to replace lankabd_datamatrix "
            f"with a partial universe; the existing table is untouched and "
            f"{output_file} holds what was scraped."
        )

    try:
        bq = BigQueryHelper()
        bq.upload_dataframe(combined_df, 'lankabd_datamatrix', truncate=True)
        logger.info("✓ Data successfully uploaded to BigQuery.")
    except Exception as e:
        logger.error(f"Error uploading to BigQuery: {e}")
        raise e # Allow failure to propagate for CI/CD retry

    return combined_df


def main() -> int:
    """Entry point. Returns a process exit code."""
    try:
        scrape_all_sectors()
    except PartialScrapeError as e:
        # Non-zero so a scheduler or CI run cannot mistake a refused partial
        # scrape for a successful refresh.
        logger.error(str(e))
        return 1
    return 0


if __name__ == "__main__":
    # Local execution support
    sys.exit(main())