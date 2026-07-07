'use client'

import { useState } from 'react'
import { ShoppingCart } from 'lucide-react'
import { lookupCuratedProduct } from '@/lib/curatedProductLookup'
import { safeHref } from '@/lib/safeHref'

interface ProductItem {
  name: string
  price?: number
  url?: string
  image_url?: string
  merchant?: string
  description?: string
}

interface InlineProductCardProps {
  products: ProductItem[]
}

const RANK_LABELS = ['Top Pick', 'Best Value', 'Premium']
const RANK_EMOJIS = ['\u{1F3C6}', '\u26A1', '\u2728']

function getRankBadge(index: number): { label: string; emoji?: string } {
  if (index < RANK_LABELS.length) {
    return { label: RANK_LABELS[index], emoji: RANK_EMOJIS[index] }
  }
  return { label: `#${index + 1}` }
}

function ProductImage({ name, imageUrl }: { name: string; imageUrl: string | null }) {
  const [errored, setErrored] = useState(false)

  if (!imageUrl || errored) {
    return (
      <div
        data-testid="product-image-placeholder"
        className="w-16 h-16 rounded-lg flex-shrink-0 flex items-center justify-center"
        style={{ backgroundColor: 'var(--surface-hover)' }}
      >
        <ShoppingCart size={20} style={{ color: 'var(--text-secondary)' }} />
      </div>
    )
  }

  return (
    <img
      src={imageUrl}
      alt={name}
      className="w-16 h-16 rounded-lg object-cover flex-shrink-0"
      onError={() => setErrored(true)}
    />
  )
}

export default function InlineProductCard({ products }: InlineProductCardProps) {
  return (
    <div className="flex flex-col w-full overflow-hidden">
      {products.map((product, index) => {
        const { imageUrl: curatedImage, affiliateUrl: curatedUrl } = lookupCuratedProduct(product.name)
        const imageUrl = product.image_url || curatedImage
        const linkUrl =
          product.url ||
          curatedUrl ||
          `https://www.amazon.com/s?k=${encodeURIComponent(product.name)}&tag=revguide-20`

        const { label, emoji } = getRankBadge(index)

        return (
          <div
            key={index}
            className="h-16 flex flex-row items-center gap-3 px-1 overflow-hidden border-b border-[var(--border)] last:border-b-0"
          >
            {/* Product image */}
            <ProductImage name={product.name} imageUrl={imageUrl} />

            {/* Center: rank + name + description */}
            <div className="flex-1 min-w-0 flex flex-col justify-center">
              <div className="flex items-center gap-1.5 min-w-0">
                <span
                  className="text-xs font-medium px-1.5 py-0.5 rounded flex-shrink-0 inline-flex items-center gap-0.5"
                  style={{
                    backgroundColor: 'var(--surface-hover)',
                    color: 'var(--text-secondary)',
                  }}
                >
                  {emoji && <span aria-hidden="true">{emoji}</span>}
                  <span>{label}</span>
                </span>
                <span className="font-semibold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
                  {product.name}
                </span>
              </div>
              {product.description && (
                <p
                  className="text-xs truncate mt-0.5"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {product.description}
                </p>
              )}
            </div>

            {/* Right: price + buy link */}
            <div className="flex flex-col items-end flex-shrink-0 gap-0.5">
              {product.price != null && (
                <span className="font-semibold text-base" style={{ color: 'var(--text-primary)' }}>
                  ${product.price}
                </span>
              )}
              <a
                href={safeHref(linkUrl)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-medium whitespace-nowrap"
                style={{ color: 'var(--primary)' }}
              >
                Buy on Amazon
              </a>
            </div>
          </div>
        )
      })}
    </div>
  )
}
