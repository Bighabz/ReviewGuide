/**
 * Playground fixtures — realistic product data in the EXACT ProductCard shape
 * from ProductCards.tsx / the backend ui_blocks contract (Section 4 of the brief).
 * Includes both legacy fields and new MCP fields, a missing-image case, badges,
 * and best_offer entries. No backend required.
 */

export interface FixtureProduct {
  // legacy fields
  rank?: number
  title?: string
  price?: number
  currency?: string
  image_url?: string
  affiliate_link?: string
  merchant?: string
  specs?: string[]
  pros?: string[]
  cons?: string[]
  rating?: number
  review_count?: number
  // new (MCP) fields
  id?: string
  name?: string
  url?: string
  snippet?: string
  score?: number
  best_offer?: { merchant: string; price: number; currency: string; url: string }
  badges?: string[]
}

/** Ranked shortlist — the canonical "best X under $Y" answer payload */
export const SHORTLIST_QUERY = 'Best noise-cancelling headphones under $400'

export const shortlistProducts: FixtureProduct[] = [
  {
    id: 'sony-wh1000xm6',
    rank: 1,
    name: 'Sony WH-1000XM6',
    title: 'Sony WH-1000XM6',
    snippet:
      'The benchmark everyone else is chasing. Class-leading noise cancellation, 36-hour battery, and the most balanced default tuning Sony has shipped.',
    price: 349.99,
    currency: 'USD',
    image_url: '/images/products/mosaic-headphones.webp',
    merchant: 'Amazon',
    affiliate_link: 'https://www.amazon.com/s?k=sony+wh-1000xm6&tag=revguide-20',
    best_offer: {
      merchant: 'Amazon',
      price: 349.99,
      currency: 'USD',
      url: 'https://www.amazon.com/s?k=sony+wh-1000xm6&tag=revguide-20',
    },
    badges: ['Top Pick', 'Best for most people'],
    rating: 4.7,
    review_count: 12834,
    pros: ['Best-in-class noise cancellation', '36-hour battery with fast charge', 'Folds flat for travel'],
    cons: ['Touch controls misfire in the cold', 'No IP water resistance'],
    specs: ['Over-ear, closed-back', '254 g', 'Bluetooth 5.4 / LDAC'],
  },
  {
    id: 'bose-qc-ultra',
    rank: 2,
    name: 'Bose QuietComfort Ultra',
    title: 'Bose QuietComfort Ultra',
    snippet:
      'The comfort king. If you wear headphones eight hours a day, the plush fit and lighter clamp beat the Sony — at the cost of some battery.',
    price: 379.0,
    currency: 'USD',
    image_url: '/images/products/mosaic-speaker.webp',
    merchant: 'Best Buy',
    affiliate_link: 'https://www.bestbuy.com/site/searchpage.jsp?st=bose+quietcomfort+ultra',
    best_offer: {
      merchant: 'Best Buy',
      price: 379.0,
      currency: 'USD',
      url: 'https://www.bestbuy.com/site/searchpage.jsp?st=bose+quietcomfort+ultra',
    },
    badges: ['Most comfortable'],
    rating: 4.6,
    review_count: 8417,
    pros: ['All-day comfort, light clamp force', 'Immersive spatial audio mode'],
    cons: ['24-hour battery trails the field', 'Case is bulkier than rivals'],
  },
  {
    id: 'sennheiser-momentum-4',
    rank: 3,
    name: 'Sennheiser Momentum 4',
    title: 'Sennheiser Momentum 4',
    snippet:
      'The audiophile pick. Warmest, most detailed sound of the group and a 60-hour battery — ANC is a clear step behind Sony and Bose.',
    price: 299.95,
    currency: 'USD',
    image_url: '/images/products/mosaic-laptop.webp',
    merchant: 'Amazon',
    affiliate_link: 'https://www.amazon.com/s?k=sennheiser+momentum+4&tag=revguide-20',
    best_offer: {
      merchant: 'Amazon',
      price: 299.95,
      currency: 'USD',
      url: 'https://www.amazon.com/s?k=sennheiser+momentum+4&tag=revguide-20',
    },
    badges: ['Best sound'],
    rating: 4.5,
    review_count: 6212,
    pros: ['Reference-grade sound signature', '60-hour battery is double the field'],
    cons: ['ANC merely good, not great', 'Bland looks for the price'],
  },
  {
    id: 'anker-space-one-pro',
    rank: 4,
    name: 'Anker Soundcore Space One Pro',
    title: 'Anker Soundcore Space One Pro',
    snippet:
      'The budget escape hatch. Eighty percent of the flagship experience for a third of the price — the pads and the app are where you feel the savings.',
    price: 129.99,
    currency: 'USD',
    // image_url intentionally missing — exercises the no-image fallback path
    merchant: 'Amazon',
    affiliate_link: 'https://www.amazon.com/s?k=anker+space+one+pro&tag=revguide-20',
    best_offer: {
      merchant: 'Amazon',
      price: 129.99,
      currency: 'USD',
      url: 'https://www.amazon.com/s?k=anker+space+one+pro&tag=revguide-20',
    },
    badges: ['Best value'],
    rating: 4.4,
    review_count: 19340,
    pros: ['Unbeatable price-to-ANC ratio', 'Folds smaller than anything here'],
    cons: ['Pads get warm after two hours', 'App nags about firmware'],
  },
  {
    id: 'airpods-max',
    rank: 5,
    name: 'Apple AirPods Max',
    title: 'Apple AirPods Max',
    snippet:
      'Still the pick inside Apple’s walls — instant pairing, audio handoff, and build quality nothing else matches. Heavy, and the price stings.',
    price: 399.0,
    currency: 'USD',
    image_url: '/images/products/mosaic-smartwatch.webp',
    merchant: 'Walmart',
    affiliate_link: 'https://www.walmart.com/search?q=airpods+max',
    best_offer: {
      merchant: 'Walmart',
      price: 399.0,
      currency: 'USD',
      url: 'https://www.walmart.com/search?q=airpods+max',
    },
    badges: ['Best for Apple users'],
    rating: 4.3,
    review_count: 498,
    pros: ['Aluminium build feels permanent', 'Seamless across Apple devices'],
    cons: ['384 g — heaviest by far', 'Charges via Lightning, still'],
  },
]

/** Same products in ProductCarousel's legacy shape */
export const carouselItems = shortlistProducts.map((p) => ({
  product_id: p.id || '',
  title: p.title || '',
  price: p.price,
  currency: p.currency || 'USD',
  affiliate_link: p.affiliate_link || '',
  merchant: p.merchant || '',
  image_url: p.image_url,
  rating: p.rating,
  review_count: p.review_count,
  best_price: p.rank === 4,
  savings: p.rank === 4 ? 30 : undefined,
  compared_retailer: p.rank === 4 ? 'Best Buy' : undefined,
}))

/** InlineProductCard's shape */
export const inlineProducts = shortlistProducts.slice(0, 3).map((p) => ({
  name: p.name || '',
  price: p.price,
  url: p.affiliate_link,
  image_url: p.image_url,
  merchant: p.merchant,
  description: p.snippet,
}))

/** AffiliateLinks' shape — cross-retailer offers for the top pick */
export const affiliateLinksFixture = {
  product_name: 'Sony WH-1000XM6',
  rank: 1,
  affiliate_links: [
    {
      product_id: 'sony-wh1000xm6',
      title: 'Sony WH-1000XM6 Wireless Noise Cancelling Headphones',
      price: 349.99,
      currency: 'USD',
      affiliate_link: 'https://www.amazon.com/s?k=sony+wh-1000xm6&tag=revguide-20',
      merchant: 'Amazon',
      rating: 4.7,
      review_count: 12834,
    },
    {
      product_id: 'sony-wh1000xm6-bb',
      title: 'Sony WH-1000XM6 Wireless Noise Cancelling Headphones',
      price: 359.99,
      currency: 'USD',
      affiliate_link: 'https://www.bestbuy.com/site/searchpage.jsp?st=sony+wh-1000xm6',
      merchant: 'Best Buy',
      rating: 4.8,
      review_count: 3211,
    },
    {
      product_id: 'sony-wh1000xm6-wm',
      title: 'Sony WH-1000XM6 Wireless Noise Cancelling Headphones',
      price: 364.0,
      currency: 'USD',
      affiliate_link: 'https://www.walmart.com/search?q=sony+wh-1000xm6',
      merchant: 'Walmart',
      rating: 4.6,
      review_count: 1876,
    },
  ],
}

/** Briefing stories for the proposed Discover front page */
export const briefingStories = [
  {
    kicker: 'Audio',
    title: 'The headphone hierarchy just changed',
    dek: 'Sony’s XM6 resets the benchmark — and makes three rivals suddenly look overpriced.',
    query: 'Best noise-cancelling headphones 2026',
    image: '/images/products/mosaic-headphones.webp',
  },
  {
    kicker: 'Travel',
    title: 'Tokyo, without the tourist tax',
    dek: 'When to book, where to stay, what the guidebooks miss.',
    query: 'Tokyo travel guide flights hotels hidden gems',
    image: '/images/travel/hero-asia.webp',
  },
  {
    kicker: 'Computing',
    title: 'Student laptops worth four years',
    dek: 'Five machines that survive a degree.',
    query: 'Best laptops for students 2026',
    image: '/images/products/mosaic-laptop.webp',
  },
  {
    kicker: 'Home',
    title: 'Robot vacuums vs. pet hair',
    dek: 'Three actually cope. Two pretend.',
    query: 'Best robot vacuums for pet hair',
    image: '/images/products/mosaic-espresso.webp',
  },
  {
    kicker: 'Fitness',
    title: 'Running shoes, ranked honestly',
    dek: 'From trail to treadmill, minus the hype.',
    query: 'Best running shoes trail treadmill 2026',
    image: '/images/products/mosaic-sneakers.webp',
  },
]
