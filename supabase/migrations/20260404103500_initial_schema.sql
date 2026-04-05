-- Supabase Migration: Updated Schema with Exact CSV Header Mapping
-- ==========================================================

-- Enable standard UUID generation from the 'pgcrypto' extension (built-in for Supabase)
-- (uuid-ossp is also fine, but gen_random_uuid() is often simpler)

-- 1. Table for DataMatrix/DataGrid snapshots (Mapped to lankabd_data_all_sectors.csv)
CREATE TABLE IF NOT EXISTS public.lankabd_datamatrix (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "Symbol" TEXT NOT NULL,
    "Sector" TEXT,
    "LTP" NUMERIC,
    "Open" NUMERIC,
    "High" NUMERIC,
    "Low" NUMERIC,
    "Close" NUMERIC,
    "YCP" NUMERIC,
    "Change" NUMERIC,
    "% Change" NUMERIC,
    "Volume(Qty)" BIGINT,
    "Value(Turnover)" NUMERIC,
    "Market Category" TEXT,
    "Audited PE" NUMERIC,
    "Forward PE" NUMERIC,
    "Free Float" NUMERIC,
    "Director Holdings" NUMERIC,
    "Govt. Holdings" NUMERIC,
    "Institute Holdings" NUMERIC,
    "Foreign Holdings" NUMERIC,
    "Public Holdings" NUMERIC,
    "Market Capitalization (mn)" NUMERIC,
    "Paid Up Capital (mn)" NUMERIC,
    "Last Dividend Declaration Date" DATE,
    "Last AGM Date" DATE,
    "Dividend Yield(%)" NUMERIC,
    "Cash Dividend" NUMERIC,
    "Stock Dividend" NUMERIC,
    "EPS" NUMERIC,
    "NAV(Quarter End)" NUMERIC,
    "RSI(14)" NUMERIC,
    "Turnover Velocity(22)" NUMERIC,
    "Beta(5)" NUMERIC,
    "SMA_20" NUMERIC,
    "SMA_50" NUMERIC,
    "Volatility_20d" NUMERIC,
    "Date" DATE DEFAULT CURRENT_DATE,
    "captured_at_timestamp" TIMESTAMPTZ DEFAULT now(),
    UNIQUE ("Symbol", "Date")
);

-- 2. Table for Market Announcements (Mapped to dse_announcements.csv)
CREATE TABLE IF NOT EXISTS public.lankabd_announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "Symbol" TEXT NOT NULL,
    "Date" DATE,
    "Announcement_Type" TEXT,
    "Details" TEXT,
    "Sentiment" TEXT,
    "Expected_Price_Impact" TEXT,
    "Importance" TEXT,
    "Sector" TEXT,
    "captured_at_timestamp" TIMESTAMPTZ DEFAULT now(),
    UNIQUE ("Symbol", "Date", "Details")
);

-- 3. Table for Historical Price Archives (Mapped to dse_historical_prices.csv)
CREATE TABLE IF NOT EXISTS public.lankabd_price_archive (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "Symbol" TEXT NOT NULL,
    "Date" DATE NOT NULL,
    "Open" NUMERIC,
    "High" NUMERIC,
    "Low" NUMERIC,
    "Close" NUMERIC,
    "Volume" NUMERIC,
    "SMA_20" NUMERIC,
    "SMA_50" NUMERIC,
    "RSI_14" NUMERIC,
    "Bollinger_Upper" NUMERIC,
    "Bollinger_Lower" NUMERIC,
    "Volatility_20d" NUMERIC,
    "Price_Momentum_20d" NUMERIC,
    "Sector" TEXT,
    "captured_at_timestamp" TIMESTAMPTZ DEFAULT now(),
    UNIQUE ("Symbol", "Date")
);

-- Enable RLS
ALTER TABLE public.lankabd_datamatrix ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lankabd_announcements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lankabd_price_archive ENABLE ROW LEVEL SECURITY;

-- Allow public read access
CREATE POLICY "Public read" ON public.lankabd_datamatrix FOR SELECT USING (true);
CREATE POLICY "Public read" ON public.lankabd_announcements FOR SELECT USING (true);
CREATE POLICY "Public read" ON public.lankabd_price_archive FOR SELECT USING (true);
