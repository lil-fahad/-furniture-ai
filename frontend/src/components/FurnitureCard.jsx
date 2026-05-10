import React, { useState } from 'react'

const StarRating = ({ rating }) => {
  if (!rating) return null
  const full  = Math.floor(rating)
  const half  = rating % 1 >= 0.5
  const empty = 5 - full - (half ? 1 : 0)
  return (
    <span className="text-yellow-400 text-xs">
      {'★'.repeat(full)}
      {half ? '½' : ''}
      <span className="text-slate-300">{'★'.repeat(empty)}</span>
    </span>
  )
}

const SourceBadge = ({ source }) => {
  if (source === 'ikea')    return <span className="badge-ikea">🔵 IKEA</span>
  if (source === 'alibaba') return <span className="badge-alibaba">🟠 Alibaba</span>
  return null
}

const FurnitureCard = ({ item, catalog = false }) => {
  const [imgError, setImgError] = useState(false)

  // Support both recommendation shape and catalog shape
  const product = item?.product || item
  const score   = item?.score
  const reason  = item?.reason

  if (!product) return null

  const {
    name, category, source, price, currency = 'USD',
    image_url, buy_url, description, dimensions,
    colors, rating, reviews, in_stock,
  } = product

  const dimStr = dimensions
    ? `${dimensions.w}×${dimensions.d}×${dimensions.h} ${dimensions.unit}`
    : null

  return (
    <div className="card flex flex-col hover:shadow-card-hover transition-shadow duration-200 group">
      {/* ── Product Image ── */}
      <div className="relative bg-slate-100 h-44 overflow-hidden">
        {image_url && !imgError ? (
          <img
            src={image_url}
            alt={name}
            onError={() => setImgError(true)}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-5xl">
            {category === 'sofa'    ? '🛋️'
            : category === 'chair'  ? '🪑'
            : category === 'table'  ? '🪵'
            : category === 'bed'    ? '🛏️'
            : category === 'desk'   ? '🖥️'
            : category === 'storage'? '🗄️'
            : category === 'lighting'? '💡'
            : category === 'rug'    ? '🟫'
            : '🪑'}
          </div>
        )}
        {/* Source badge overlay */}
        <div className="absolute top-2 left-2">
          <SourceBadge source={source} />
        </div>
        {/* Score badge */}
        {score !== undefined && (
          <div className="absolute top-2 right-2 bg-white/90 backdrop-blur-sm rounded-lg px-2 py-0.5 text-xs font-bold text-brand-600">
            {(score * 100).toFixed(0)}%
          </div>
        )}
        {/* Out of stock */}
        {in_stock === false && (
          <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
            <span className="bg-white text-slate-700 text-xs font-bold px-3 py-1 rounded-full">Out of Stock</span>
          </div>
        )}
      </div>

      {/* ── Content ── */}
      <div className="p-4 flex flex-col flex-1 gap-2">
        {/* Name + Category */}
        <div>
          <h3 className="font-semibold text-slate-800 text-sm leading-tight line-clamp-2">{name}</h3>
          <span className="text-xs text-slate-400 capitalize">{category}</span>
        </div>

        {/* Rating */}
        {rating && (
          <div className="flex items-center gap-1.5">
            <StarRating rating={rating} />
            <span className="text-xs text-slate-400">{rating} {reviews ? `(${reviews.toLocaleString()})` : ''}</span>
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-slate-500 line-clamp-2">{description}</p>
        )}

        {/* Reason (from recommendation) */}
        {reason && (
          <p className="text-xs text-brand-600 bg-brand-50 rounded-lg px-2 py-1 line-clamp-2">
            💡 {reason}
          </p>
        )}

        {/* Dimensions */}
        {dimStr && (
          <p className="text-xs text-slate-400">📐 {dimStr}</p>
        )}

        {/* Colors */}
        {colors && colors.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {colors.slice(0, 3).map((c, i) => (
              <span key={i} className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded-md">{c}</span>
            ))}
            {colors.length > 3 && (
              <span className="text-xs text-slate-400">+{colors.length - 3}</span>
            )}
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Price + Buy Button */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-100">
          <div>
            {price ? (
              <span className="text-lg font-bold text-slate-800">
                ${price.toLocaleString()}
                <span className="text-xs font-normal text-slate-400 ml-1">{currency}</span>
              </span>
            ) : (
              <span className="text-sm text-slate-400">Price on request</span>
            )}
          </div>
          {buy_url && (
            <a
              href={buy_url}
              target="_blank"
              rel="noopener noreferrer"
              className={source === 'ikea' ? 'btn-ikea' : 'btn-alibaba'}
              onClick={(e) => e.stopPropagation()}
            >
              {source === 'ikea' ? 'Buy at IKEA' : 'Buy on Alibaba'}
            </a>
          )}
        </div>
      </div>
    </div>
  )
}

export default FurnitureCard
