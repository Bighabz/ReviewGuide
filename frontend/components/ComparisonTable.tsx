'use client'

import { useState } from 'react'
import { Check, X, ExternalLink, Star } from 'lucide-react'

interface ComparisonProduct {
  title: string
  price: number
  currency: string
  rating?: number
  review_count?: number
  merchant: string
  url: string
  image_url?: string
  pros?: string[]
  cons?: string[]
}

interface ComparisonTableData {
  products: ComparisonProduct[]
  criteria: string[]
  summary: string
}

interface ComparisonTableProps {
  data: ComparisonTableData
  title?: string
}

export default function ComparisonTable({ data, title }: ComparisonTableProps) {
  const [hoveredColumn, setHoveredColumn] = useState<number | null>(null)

  if (!data || !data.products || data.products.length === 0) {
    return null
  }

  const { products, summary } = data

  // Find best values for highlighting
  const lowestPrice = Math.min(...products.map(p => p.price || Infinity))
  const highestRating = Math.max(...products.map(p => p.rating || 0))

  const formatPrice = (price: number, currency: string) => {
    if (!price) return 'N/A'
    return `${currency} ${price.toFixed(2)}`
  }

  const renderRating = (rating?: number, review_count?: number) => {
    if (!rating) return <span className="text-[var(--text-muted)]">N/A</span>
    return (
      <div className="flex items-center gap-1">
        <Star size={14} className="fill-yellow-400 text-yellow-400" />
        <span className="font-medium text-[var(--text)]">{rating.toFixed(1)}</span>
        {review_count && (
          <span className="text-xs text-[var(--text-muted)]">
            ({review_count.toLocaleString()})
          </span>
        )}
      </div>
    )
  }

  return (
    <div className="w-full mb-6 mt-4">
      {/* Title */}
      {title && (
        <h3 className="text-lg font-bold font-serif mb-3 text-[var(--text)]">
          {title}
        </h3>
      )}

      {/* Comparison Table Container */}
      <div className="rounded-xl border border-[var(--border)] overflow-hidden shadow-card bg-[var(--surface)]">
        {/* Summary */}
        {summary && (
          <div className="px-5 py-4 border-b border-[var(--border)] text-sm italic text-[var(--text-secondary)] bg-[var(--surface)]">
            {summary}
          </div>
        )}

        {/* Table */}
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full min-w-[700px] border-collapse">
            <thead>
              <tr className="border-b border-[var(--border)]">
                <th className="p-4 text-left text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] w-[140px] sticky left-0 bg-[var(--surface)] z-10 shadow-[4px_0_12px_-4px_rgba(0,0,0,0.1)]">Feature</th>
                {products.map((product, idx) => (
                  <th
                    key={idx}
                    className="p-4 text-center transition-colors duration-200 min-w-[180px]"
                    style={{
                      background: hoveredColumn === idx ? 'var(--surface-hover)' : 'transparent',
                    }}
                    onMouseEnter={() => setHoveredColumn(idx)}
                    onMouseLeave={() => setHoveredColumn(null)}
                  >
                    {/* Product Image */}
                    <div className="flex justify-center mb-3">
                      <div className="w-20 h-20 rounded-lg overflow-hidden border border-[var(--border)] bg-[var(--surface)] p-1">
                        {product.image_url ? (
                          <img
                            src={product.image_url}
                            alt={product.title}
                            loading="lazy"
                            className="w-full h-full object-contain"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-xs text-[var(--text-muted)] bg-[var(--background)]">
                            No Image
                          </div>
                        )}
                      </div>
                    </div>
                    {/* Product Title */}
                    <div className="text-sm font-semibold line-clamp-2 text-[var(--text)] min-h-[40px]" title={product.title}>
                      {product.title}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-[var(--border)]">
              {/* Price Row */}
              <tr>
                <td className="p-4 text-sm font-bold text-[var(--text)] sticky left-0 bg-[var(--surface)] z-10">Price</td>
                {products.map((product, idx) => {
                  const isBest = product.price === lowestPrice && product.price > 0
                  return (
                    <td
                      key={idx}
                      className="p-4 text-center transition-colors duration-200"
                      style={{
                        background: hoveredColumn === idx ? 'var(--surface-hover)' : 'transparent'
                      }}
                      onMouseEnter={() => setHoveredColumn(idx)}
                      onMouseLeave={() => setHoveredColumn(null)}
                    >
                      <span
                        className={`text-lg font-bold ${isBest ? 'text-emerald-600 dark:text-emerald-400' : 'text-[var(--text)]'}`}
                      >
                        {formatPrice(product.price, product.currency)}
                        {isBest && (
                          <span className="ml-1.5 text-[10px] font-bold uppercase tracking-wide text-emerald-600 px-1.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30">
                            Best
                          </span>
                        )}
                      </span>
                    </td>
                  )
                })}
              </tr>

              {/* Rating Row */}
              <tr>
                <td className="p-4 text-sm font-medium text-[var(--text)] sticky left-0 bg-[var(--surface)] z-10">Rating</td>
                {products.map((product, idx) => {
                  const isBest = product.rating === highestRating && (product.rating || 0) > 0
                  return (
                    <td
                      key={idx}
                      className="p-4 transition-colors duration-200"
                      style={{
                        background: hoveredColumn === idx ? 'var(--surface-hover)' : 'transparent'
                      }}
                      onMouseEnter={() => setHoveredColumn(idx)}
                      onMouseLeave={() => setHoveredColumn(null)}
                    >
                      <div className="flex justify-center items-center gap-1">
                        {renderRating(product.rating, product.review_count)}
                        {isBest && product.rating && (
                          <span className="ml-1 text-[10px] text-emerald-600 font-bold bg-emerald-100 px-1.5 py-0.5 rounded-full dark:bg-emerald-900/30 dark:text-emerald-400">Top</span>
                        )}
                      </div>
                    </td>
                  )
                })}
              </tr>

              {/* Merchant Row */}
              <tr>
                <td className="p-4 text-sm font-medium text-[var(--text)] sticky left-0 bg-[var(--surface)] z-10">Merchant</td>
                {products.map((product, idx) => (
                  <td
                    key={idx}
                    className="p-4 text-center text-sm font-medium text-[var(--text-secondary)] transition-colors duration-200"
                    style={{
                      background: hoveredColumn === idx ? 'var(--surface-hover)' : 'transparent'
                    }}
                    onMouseEnter={() => setHoveredColumn(idx)}
                    onMouseLeave={() => setHoveredColumn(null)}
                  >
                    {product.merchant || 'N/A'}
                  </td>
                ))}
              </tr>

              {/* Pros Row */}
              {products.some(p => p.pros && p.pros.length > 0) && (
                <tr>
                  <td className="p-4 text-sm font-medium text-[var(--text)] align-top sticky left-0 bg-[var(--surface)] z-10">Pros</td>
                  {products.map((product, idx) => (
                    <td
                      key={idx}
                      className="p-4 text-left text-xs transition-colors duration-200 align-top"
                      style={{
                        background: hoveredColumn === idx ? 'var(--surface-hover)' : 'transparent'
                      }}
                      onMouseEnter={() => setHoveredColumn(idx)}
                      onMouseLeave={() => setHoveredColumn(null)}
                    >
                      {product.pros && product.pros.length > 0 ? (
                        <ul className="space-y-2">
                          {product.pros.slice(0, 3).map((pro, proIdx) => (
                            <li key={proIdx} className="flex items-start gap-1.5 leading-snug">
                              <Check size={14} className="text-emerald-500 flex-shrink-0 mt-0.5" />
                              <span className="text-[var(--text)] opacity-90">{pro}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-[var(--text-muted)]">-</span>
                      )}
                    </td>
                  ))}
                </tr>
              )}

              {/* Cons Row */}
              {products.some(p => p.cons && p.cons.length > 0) && (
                <tr>
                  <td className="p-4 text-sm font-medium text-[var(--text)] align-top sticky left-0 bg-[var(--surface)] z-10">Cons</td>
                  {products.map((product, idx) => (
                    <td
                      key={idx}
                      className="p-4 text-left text-xs transition-colors duration-200 align-top"
                      style={{
                        background: hoveredColumn === idx ? 'var(--surface-hover)' : 'transparent'
                      }}
                      onMouseEnter={() => setHoveredColumn(idx)}
                      onMouseLeave={() => setHoveredColumn(null)}
                    >
                      {product.cons && product.cons.length > 0 ? (
                        <ul className="space-y-2">
                          {product.cons.slice(0, 3).map((con, conIdx) => (
                            <li key={conIdx} className="flex items-start gap-1.5 leading-snug">
                              <X size={14} className="text-red-500 flex-shrink-0 mt-0.5" />
                              <span className="text-[var(--text)] opacity-90">{con}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-[var(--text-muted)]">-</span>
                      )}
                    </td>
                  ))}
                </tr>
              )}

              {/* Action Row */}
              <tr>
                <td className="p-4 text-sm font-medium text-[var(--text)] sticky left-0 bg-[var(--surface)] z-10">Action</td>
                {products.map((product, idx) => (
                  <td
                    key={idx}
                    className="p-4 text-center transition-colors duration-200"
                    style={{
                      background: hoveredColumn === idx ? 'var(--surface-hover)' : 'transparent'
                    }}
                    onMouseEnter={() => setHoveredColumn(idx)}
                    onMouseLeave={() => setHoveredColumn(null)}
                  >
                    {product.url ? (
                      <a
                        href={product.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center justify-center gap-1.5 w-full px-4 py-2.5 rounded-lg text-sm font-semibold transition-all shadow-card hover:shadow-md active:scale-95"
                        style={{
                          background: 'var(--primary)',
                          color: 'white'
                        }}
                      >
                        View Deal
                        <ExternalLink size={14} />
                      </a>
                    ) : (
                      <span className="text-xs text-[var(--text-muted)]">
                        N/A
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
