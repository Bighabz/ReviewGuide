'use client'

import { Plane, Clock, ExternalLink, Search, ArrowRight } from 'lucide-react'
import { trackAffiliateClick } from '@/lib/trackAffiliate'
import { formatDate } from '@/lib/formatDate'
import { safeHref } from '@/lib/safeHref'

// Traditional flight card with full details
interface FlightCard {
  type?: 'flight_card'
  carrier: string
  flight_number: string
  origin: string
  destination: string
  depart_time: string
  arrive_time: string
  duration_minutes: number
  stops: number
  price: number
  currency: string
  cabin_class: string
  deeplink: string
}

// PLP link - search results page link
interface FlightPLPLink {
  type: 'plp_link'
  provider: string
  origin: string
  destination: string
  search_url: string
  title: string
  departure_date?: string
  return_date?: string
  passengers?: number
}

type Flight = FlightCard | FlightPLPLink

interface FlightCardsProps {
  flights: Flight[]
  fullHeight?: boolean  // When true, card stretches to fill container height
}

// Type guard to check if flight is a PLP link
function isPLPLink(flight: Flight): flight is FlightPLPLink {
  return flight.type === 'plp_link'
}

// PLP Link Card Component
function PLPLinkCard({ flight, fullHeight = false }: { flight: FlightPLPLink; fullHeight?: boolean }) {
  // Uses shared formatDate from @/lib/formatDate (dedup 2026-04-21)
  const isRoundTrip = !!flight.return_date

  return (
    <a
      href={safeHref(flight.search_url)}
      target="_blank"
      rel="noopener noreferrer"
      className={`block bg-[var(--surface)] border border-[var(--border)] rounded-xl p-8 transition-all shadow-card hover:shadow-card-hover product-card-hover ${fullHeight ? 'h-full flex flex-col' : ''}`}
      onClick={(e) => {
        e.preventDefault()
        trackAffiliateClick({
          provider: flight.provider || 'flight',
          product_name: flight.title,
          category: 'flight',
          url: flight.search_url,
        })
      }}
    >
      <div className={`flex flex-col items-center text-center ${fullHeight ? 'h-full justify-between' : ''}`}>
        {/* Search icon */}
        <div className="w-16 h-16 rounded-full flex items-center justify-center mb-5 bg-[var(--primary-light)]">
          <Search size={28} strokeWidth={1.5} className="text-[var(--primary)]" />
        </div>

        {/* Title */}
        <h4 className="font-serif text-xl mb-3 text-[var(--text)]">
          {flight.title}
        </h4>

        {/* Route visualization */}
        <div className="flex items-center gap-3 mb-4 text-[var(--text)]">
          <span className="text-xl font-bold tracking-wider">
            {flight.origin}
          </span>
          <div className="flex items-center gap-2 px-3">
            <div className="w-8 h-[2px] bg-[var(--border-strong)]"></div>
            <Plane size={18} strokeWidth={1.5} className="text-[var(--text-muted)] transform rotate-90 sm:rotate-0" />
            <div className="w-8 h-[2px] bg-[var(--border-strong)]"></div>
          </div>
          <span className="text-xl font-bold tracking-wider">
            {flight.destination}
          </span>
        </div>

        {/* Date info */}
        {flight.departure_date && (
          <p className="text-sm mb-2 text-[var(--text-secondary)]">
            {formatDate(flight.departure_date)}
            {flight.return_date && ` - ${formatDate(flight.return_date)}`}
          </p>
        )}

        {/* Passengers if available */}
        {flight.passengers && (
          <p className="text-sm mb-5 text-[var(--text-secondary)]">
            {flight.passengers} passenger{flight.passengers > 1 ? 's' : ''}
          </p>
        )}

        {/* Provider badge */}
        <div className="text-xs font-medium px-3 py-1.5 rounded-full mb-6 bg-[var(--surface-strong)] text-[var(--text-muted)] border border-[var(--border)]">
          Powered by {flight.provider.charAt(0).toUpperCase() + flight.provider.slice(1)}
        </div>

        {/* CTA Button */}
        <button
          className="w-full px-6 py-3 bg-[var(--primary)] text-white rounded-lg transition-all flex items-center justify-center gap-2 text-base font-medium hover:opacity-90"
        >
          Search Flights
          <ExternalLink size={16} strokeWidth={1.5} />
        </button>
      </div>
    </a>
  )
}

// Traditional Flight Card Component - Google Flights Style
function TraditionalFlightCard({ flight }: { flight: FlightCard }) {
  const formatTime = (datetime: string) => {
    try {
      return new Date(datetime).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      })
    } catch {
      return datetime
    }
  }

  const formatDuration = (minutes: number) => {
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    return `${hours}h ${mins}m`
  }

  return (
    <a
      href={safeHref(flight.deeplink)}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 transition-all shadow-card hover:shadow-card-hover product-card-hover"
      onClick={(e) => {
        e.preventDefault()
        trackAffiliateClick({
          provider: flight.carrier || 'flight',
          product_name: `${flight.carrier} ${flight.origin} to ${flight.destination}`,
          category: 'flight',
          url: flight.deeplink,
        })
      }}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Flight Details Section */}
        <div className="flex-1 flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-8">
          {/* Carrier Logo/Name */}
          <div className="flex items-center gap-3 min-w-[140px]">
            <div className="w-10 h-10 rounded-full bg-[var(--surface-strong)] flex items-center justify-center border border-[var(--border)]">
              <Plane size={18} strokeWidth={1.5} className="text-[var(--text-secondary)]" />
            </div>
            <div>
              <div className="font-medium text-sm text-[var(--text)]">{flight.carrier}</div>
              <div className="text-xs text-[var(--text-muted)] tracking-wide">{flight.flight_number}</div>
            </div>
          </div>

          {/* Times & Route */}
          <div className="flex-1 flex items-center justify-between sm:justify-start sm:gap-8">
            <div className="text-left">
              <div className="text-xl font-bold text-[var(--text)]">{formatTime(flight.depart_time)}</div>
              <div className="text-xs text-[var(--text-secondary)] font-medium uppercase tracking-wider">{flight.origin}</div>
            </div>

            <div className="flex flex-col items-center px-4">
              <div className="text-xs text-[var(--text-muted)] mb-1.5 font-medium">{formatDuration(flight.duration_minutes)}</div>
              <div className="w-20 h-[2px] bg-[var(--border-strong)] relative flex items-center justify-center">
                <div className={`w-2 h-2 rounded-full ${flight.stops === 0 ? 'bg-[var(--success)]' : 'bg-[var(--accent)]'}`}></div>
              </div>
              <div className={`text-xs mt-1.5 font-medium ${flight.stops === 0 ? 'text-[var(--success)]' : 'text-[var(--accent)]'}`}>
                {flight.stops === 0 ? 'Non-stop' : `${flight.stops} stop${flight.stops > 1 ? 's' : ''}`}
              </div>
            </div>

            <div className="text-right">
              <div className="text-xl font-bold text-[var(--text)]">{formatTime(flight.arrive_time)}</div>
              <div className="text-xs text-[var(--text-secondary)] font-medium uppercase tracking-wider">{flight.destination}</div>
            </div>
          </div>
        </div>

        {/* Price & Action Section */}
        <div className="flex items-center justify-between sm:justify-end sm:gap-6 pt-4 sm:pt-0 border-t sm:border-t-0 border-[var(--border)] sm:pl-6 sm:border-l sm:border-[var(--border)]">
          <div className="text-left sm:text-right">
            <div className="text-xl font-bold text-[var(--text)]">{flight.currency} {flight.price?.toFixed(0)}</div>
            <div className="text-xs text-[var(--text-muted)]">{flight.cabin_class}</div>
          </div>

          <button className="px-5 py-2.5 rounded-lg bg-[var(--primary)] text-white text-sm font-medium hover:opacity-90 transition-all">
            Select
          </button>
        </div>
      </div>
    </a>
  )
}

export default function FlightCards({ flights, fullHeight = false }: FlightCardsProps) {
  if (!flights || flights.length === 0) return null

  // Check if all flights are PLP links
  const allPLPLinks = flights.every(isPLPLink)

  return (
    <div className={`space-y-6 ${fullHeight ? 'h-full flex flex-col' : ''}`}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h3 className="font-serif text-2xl text-[var(--text)] flex items-center gap-3">
            <Plane size={24} strokeWidth={1.5} className="text-[var(--primary)]" />
            Recommended Flights
          </h3>
          <div className="h-[1px] bg-[var(--border)] mt-3"></div>
        </div>
        {!allPLPLinks && (
          <span className="text-xs font-medium px-3 py-1.5 rounded-full bg-[var(--surface-strong)] text-[var(--text-secondary)] border border-[var(--border)] ml-4">
            {flights.length} options
          </span>
        )}
      </div>

      {allPLPLinks ? (
        // PLP links - grid
        <div className={`grid grid-cols-1 gap-4 ${fullHeight ? 'flex-1' : ''}`}>
          {flights.map((flight, idx) => (
            <PLPLinkCard key={idx} flight={flight as FlightPLPLink} fullHeight={fullHeight} />
          ))}
        </div>
      ) : (
        // List for traditional flight cards
        <div className="space-y-4">
          {flights.map((flight, idx) => (
            isPLPLink(flight) ? (
              <PLPLinkCard key={idx} flight={flight} />
            ) : (
              <TraditionalFlightCard key={idx} flight={flight} />
            )
          ))}
        </div>
      )}
    </div>
  )
}
