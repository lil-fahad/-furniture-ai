import React from 'react'

const SOURCE_COLORS = {
  ikea: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  alibaba: 'bg-orange-100 text-orange-800 border-orange-300',
}

const FurnitureCard = ({ item }) => {
  const isExternal = !!item.source
  const badgeClass = SOURCE_COLORS[item.source] || 'bg-gray-100 text-gray-700 border-gray-300'

  return (
    <div className="border rounded-lg p-3 mb-3 flex gap-3 shadow-sm hover:shadow-md transition-shadow">
      {item.image_url && (
        <img
          src={item.image_url}
          alt={item.name}
          className="w-20 h-20 object-cover rounded flex-shrink-0"
          onError={(e) => { e.target.style.display = 'none' }}
        />
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="font-semibold text-sm leading-tight">{item.name}</div>
          {item.source && (
            <span className={`text-xs px-2 py-0.5 rounded border flex-shrink-0 ${badgeClass}`}>
              {item.source.toUpperCase()}
            </span>
          )}
        </div>
        <div className="text-xs text-gray-500 mt-0.5 capitalize">{item.category}</div>
        {item.price != null && (
          <div className="text-sm font-medium text-green-700 mt-1">
            {item.currency || 'USD'} {item.price.toFixed(2)}
          </div>
        )}
        {item.score != null && (
          <div className="text-xs text-gray-500 mt-0.5">
            AI Match: {(item.score * 100).toFixed(1)}%
          </div>
        )}
        {item.description && (
          <div className="text-xs text-gray-500 mt-1 line-clamp-2">{item.description}</div>
        )}
        {item.product_url && (
          <a
            href={item.product_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block mt-2 text-xs text-blue-600 hover:underline"
          >
            View Product →
          </a>
        )}
      </div>
    </div>
  )
}

export default FurnitureCard
