import React, { useState, useEffect } from 'react'
import { getCatalogProducts } from '../api/api'
import FurnitureCard from '../components/FurnitureCard'

const CATEGORIES = ['all', 'sofa', 'chair', 'table', 'storage', 'bed', 'desk', 'lighting', 'rug']
const STYLES     = ['all', 'modern', 'scandinavian', 'industrial', 'luxury', 'minimalist', 'classic']
const SOURCES    = ['all', 'ikea', 'alibaba']

const FurnitureCatalog = () => {
  const [products, setProducts]   = useState([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const [category, setCategory]   = useState('all')
  const [style, setStyle]         = useState('all')
  const [source, setSource]       = useState('all')
  const [maxPrice, setMaxPrice]   = useState('')
  const [search, setSearch]       = useState('')

  const fetchProducts = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (category !== 'all') params.category = category
      if (style !== 'all')    params.style = style
      if (source !== 'all')   params.source = source
      if (maxPrice)           params.max_price = parseFloat(maxPrice)
      const data = await getCatalogProducts(params)
      setProducts(data)
    } catch (e) {
      setError('Could not load catalog. Make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchProducts() }, [category, style, source, maxPrice])

  const filtered = search
    ? products.filter(p =>
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        p.description?.toLowerCase().includes(search.toLowerCase())
      )
    : products

  const ikeaCount    = filtered.filter(p => p.source === 'ikea').length
  const alibabaCount = filtered.filter(p => p.source === 'alibaba').length

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Furniture Catalog</h2>
          <p className="text-slate-500 text-sm mt-0.5">
            Browse {filtered.length} products from
            <span className="text-ikea font-semibold"> IKEA ({ikeaCount})</span> &amp;
            <span className="text-alibaba font-semibold"> Alibaba ({alibabaCount})</span>
          </p>
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="🔍 Search furniture..."
          className="input-field max-w-xs"
        />
      </div>

      {/* ── Filters ── */}
      <div className="card p-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Source */}
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Source</label>
            <div className="flex gap-1 flex-wrap">
              {SOURCES.map(s => (
                <button
                  key={s}
                  onClick={() => setSource(s)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all ${
                    source === s
                      ? s === 'ikea' ? 'bg-ikea text-white border-ikea'
                        : s === 'alibaba' ? 'bg-alibaba text-white border-alibaba'
                        : 'bg-brand-600 text-white border-brand-600'
                      : 'bg-white text-slate-500 border-slate-200 hover:border-slate-300'
                  }`}
                >
                  {s === 'ikea' ? '🔵 IKEA' : s === 'alibaba' ? '🟠 Alibaba' : 'All'}
                </button>
              ))}
            </div>
          </div>

          {/* Category */}
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Category</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)} className="input-field text-xs py-1.5">
              {CATEGORIES.map(c => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
            </select>
          </div>

          {/* Style */}
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Style</label>
            <select value={style} onChange={(e) => setStyle(e.target.value)} className="input-field text-xs py-1.5">
              {STYLES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
            </select>
          </div>

          {/* Max Price */}
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Max Price (USD)</label>
            <input
              type="number"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
              placeholder="No limit"
              className="input-field text-xs py-1.5"
            />
          </div>
        </div>
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* ── Products Grid ── */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-3">
              <div className="skeleton h-40 w-full" />
              <div className="skeleton h-4 w-3/4" />
              <div className="skeleton h-3 w-1/2" />
              <div className="skeleton h-8 w-full" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <div className="text-5xl mb-3">🔍</div>
          <p className="font-medium">No products found</p>
          <p className="text-sm">Try adjusting your filters</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((product) => (
            <FurnitureCard key={product.item_id} item={{ product, score: product.rating / 5 }} catalog />
          ))}
        </div>
      )}
    </div>
  )
}

export default FurnitureCatalog
