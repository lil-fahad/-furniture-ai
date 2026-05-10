import React, { useState } from 'react'
import { searchIKEA, searchAlibaba } from '../api/api'
import FurnitureCard from '../components/FurnitureCard'

const CATEGORIES = [
  { value: '', label: 'All Categories' },
  { value: 'sofa', label: 'Sofa' },
  { value: 'chair', label: 'Chair' },
  { value: 'table', label: 'Table' },
  { value: 'bed', label: 'Bed' },
  { value: 'storage', label: 'Storage' },
  { value: 'wardrobe', label: 'Wardrobe' },
  { value: 'tv_unit', label: 'TV Unit' },
]

const FurnitureSearch = () => {
  const [tab, setTab] = useState('ikea')
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [maxResults, setMaxResults] = useState(10)
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const onSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const fn = tab === 'ikea' ? searchIKEA : searchAlibaba
      const data = await fn(query, category || null, maxResults)
      setProducts(data.products || [])
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      setProducts([])
    } finally {
      setLoading(false)
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter') onSearch()
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Furniture Search</h2>

      {/* Source tabs */}
      <div className="flex border-b">
        {['ikea', 'alibaba'].map((src) => (
          <button
            key={src}
            onClick={() => { setTab(src); setProducts([]) }}
            className={`px-5 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
              tab === src
                ? src === 'ikea'
                  ? 'border-yellow-500 text-yellow-700'
                  : 'border-orange-500 text-orange-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {src === 'ikea' ? 'IKEA' : 'Alibaba / AliExpress'}
          </button>
        ))}
      </div>

      {/* Search controls */}
      <div className="flex flex-wrap gap-2">
        <input
          className="border rounded px-3 py-2 flex-1 min-w-48 text-sm"
          placeholder={`Search ${tab === 'ikea' ? 'IKEA' : 'Alibaba'} products…`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <select
          className="border rounded px-3 py-2 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <select
          className="border rounded px-3 py-2 text-sm"
          value={maxResults}
          onChange={(e) => setMaxResults(Number(e.target.value))}
        >
          {[5, 10, 20, 50].map((n) => (
            <option key={n} value={n}>{n} results</option>
          ))}
        </select>
        <button
          className={`px-4 py-2 text-white rounded text-sm font-medium ${
            tab === 'ikea' ? 'bg-yellow-500 hover:bg-yellow-600' : 'bg-orange-500 hover:bg-orange-600'
          }`}
          onClick={onSearch}
          disabled={loading}
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded p-3">
          {error}
        </div>
      )}

      {/* Results */}
      {products.length > 0 && (
        <div>
          <div className="text-sm text-gray-500 mb-2">{products.length} products found</div>
          <div className="grid grid-cols-1 gap-2">
            {products.map((p) => (
              <FurnitureCard key={p.item_id} item={p} />
            ))}
          </div>
        </div>
      )}

      {!loading && products.length === 0 && query && !error && (
        <div className="text-gray-400 text-sm text-center py-8">No products found. Try a different keyword.</div>
      )}
    </div>
  )
}

export default FurnitureSearch
