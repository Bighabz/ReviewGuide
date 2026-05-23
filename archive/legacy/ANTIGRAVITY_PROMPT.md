# Prompt for Building ReviewGuide.ai Static Affiliate Blog

## Context

I need you to build a fast, static affiliate blog site for ReviewGuide.ai. This is URGENT because Amazon is auditing our affiliate account and we need to demonstrate we're a legitimate affiliate publisher.

## What to Build

A static blog/content site with:

1. **Homepage** - Introduction to ReviewGuide.ai + featured products
2. **5-10 Blog Posts** - Product roundups and reviews with Amazon affiliate links
3. **Product Cards** - Clean design with "Buy on Amazon" buttons
4. **Footer Disclosure** - Required Amazon Associates disclaimer on every page

## Technical Stack (Suggested)

- **Framework:** Astro, Next.js (static export), or Hugo
- **Styling:** TailwindCSS
- **Deployment:** Vercel or Netlify (free tier is fine)
- **Content:** Markdown files for blog posts

## Amazon Affiliate Link Format

Every product link must use this format:
```
https://www.amazon.com/dp/[ASIN]?tag=mikejahshan-20
```

Example:
```
https://www.amazon.com/dp/B09NQNGDGB?tag=mikejahshan-20
```

## Required Footer (on every page)

```
ReviewGuide.ai participates in the Amazon Services LLC Associates Program,
an affiliate advertising program designed to provide a means for sites to
earn advertising fees by advertising and linking to Amazon.com. We may earn
a commission from qualifying purchases made through our links.
```

## Sample Blog Post Structure

```markdown
---
title: "Best Wireless Headphones for 2025"
description: "Our top picks for wireless headphones based on expert reviews and user feedback"
date: 2025-01-07
category: electronics
---

# Best Wireless Headphones for 2025

Looking for the perfect wireless headphones? We've analyzed hundreds of reviews...

## Our Top Picks

### 1. Sony WH-1000XM5
[Product card with image, price, description]
**Why we love it:** Industry-leading noise cancellation...
[Buy on Amazon](https://www.amazon.com/dp/PLACEHOLDER001?tag=mikejahshan-20)

### 2. Apple AirPods Max
[Product card]
[Buy on Amazon](https://www.amazon.com/dp/PLACEHOLDER002?tag=mikejahshan-20)

... etc
```

## Product Card Component

Each product should display:
- Product image
- Product title
- Price (e.g., "$299.99")
- Short description (1-2 lines)
- Star rating if available
- "Buy on Amazon" button (styled, prominent)

## Site Structure

```
/
├── index.html (homepage)
├── blog/
│   ├── best-wireless-headphones-2025/
│   ├── top-kitchen-gadgets/
│   ├── travel-essentials-guide/
│   └── ... more posts
├── about/
├── categories/
│   ├── electronics/
│   ├── home-kitchen/
│   └── travel/
└── (footer with disclosure on all pages)
```

## Design Guidelines

- Clean, modern, trustworthy
- Mobile-first responsive
- Fast loading (aim for 90+ Lighthouse score)
- Color scheme: Professional blues/grays or match ReviewGuide.ai branding
- Prominent CTAs (Buy buttons should stand out)

## SEO Requirements

- Proper `<title>` and `<meta description>` on each page
- Open Graph tags for social sharing
- Schema.org Product markup on product pages
- XML sitemap
- robots.txt

## Additional Affiliate Links (Optional - if time permits)

**Expedia (Travel):**
- Partner ID: `1101l413711`
- Hotel search: `https://www.expedia.com/Hotel-Search?destination=[CITY]&partnerId=1101l413711`

## Note on Product Links (IMPORTANT)

**Use placeholder ASINs for now.** Structure all affiliate links like:
```
https://www.amazon.com/dp/PLACEHOLDER001?tag=mikejahshan-20
https://www.amazon.com/dp/PLACEHOLDER002?tag=mikejahshan-20
```

We'll replace these with real ASINs when Mike provides them. For now:
- Use real, popular product **names** (Sony WH-1000XM5, Apple AirPods Max, etc.)
- Use placeholder ASINs (PLACEHOLDER001, PLACEHOLDER002, etc.)
- The affiliate tag `mikejahshan-20` is correct and should remain

This allows us to build the full site structure now and do a quick find-replace later.

---

## What I'll Provide

- List of specific Amazon products/ASINs to feature (Mike will send these - we'll replace placeholders)
- Any branding assets if available

## Deliverables

1. GitHub repo with the static site code
2. Deployed live URL (Vercel/Netlify)
3. Instructions for adding new blog posts
4. 5-10 initial blog posts with real affiliate links

## Priority

This is **URGENT**. Amazon audit coming soon. Start with a minimal version and iterate. A simple but professional-looking site with working affiliate links is better than a fancy site that takes too long.

---

## Questions to Ask Me

1. Do you have specific products/ASINs, or should I pick popular items?
2. Do you have a logo or brand colors for ReviewGuide.ai?
3. What domain/subdomain should this deploy to?
4. Any existing content I can repurpose?
