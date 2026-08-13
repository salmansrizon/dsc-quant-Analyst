import {
  CandlestickChart,
  FileBarChart,
  Newspaper,
  PieChart,
  Target,
  type LucideIcon,
} from 'lucide-react';

// #87: the shared zone-type vocabulary that Stock Detail (#90), the Dashboard
// feed (#96), and the full reskin (#97) build their layouts from, instead of
// each page inventing its own section taxonomy.
export type ZoneType = 'price' | 'fundamentals' | 'fit' | 'sector' | 'news';

export const ZONE_TYPES: ZoneType[] = ['price', 'fundamentals', 'fit', 'sector', 'news'];

export interface ZoneConfig {
  type: ZoneType;
  label: string;
  description: string;
  /** CSS var() reference into the --zone-* tokens defined in index.css. */
  colorVar: string;
  Icon: LucideIcon;
}

const ZONE_CONFIG: Record<ZoneType, ZoneConfig> = {
  price: {
    type: 'price',
    label: 'Price & Chart',
    description: 'Price history, candles, and technical overlays.',
    colorVar: 'var(--zone-price)',
    Icon: CandlestickChart,
  },
  fundamentals: {
    type: 'fundamentals',
    label: 'Fundamentals',
    description: 'Earnings, dividends, and valuation ratios.',
    colorVar: 'var(--zone-fundamentals)',
    Icon: FileBarChart,
  },
  fit: {
    type: 'fit',
    label: 'Fit for you',
    description: "How this matches your stated preferences — not a buy/sell signal.",
    colorVar: 'var(--zone-fit)',
    Icon: Target,
  },
  sector: {
    type: 'sector',
    label: 'Sector Comparison',
    description: 'How this stacks up against its sector peers.',
    colorVar: 'var(--zone-sector)',
    Icon: PieChart,
  },
  news: {
    type: 'news',
    label: 'News & Sentiment',
    description: 'Recent news and sentiment context.',
    colorVar: 'var(--zone-news)',
    Icon: Newspaper,
  },
};

export function getZoneConfig(type: ZoneType): ZoneConfig {
  return ZONE_CONFIG[type];
}
