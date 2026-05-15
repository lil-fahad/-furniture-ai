import React, { useState } from 'react'
import { recommendFurniture } from '../api/api'
import FurnitureCard from '../components/FurnitureCard'

const FurnitureRecommend = () => {
  const [style, setStyle] = useState('modern')
  const [budget, setBudget] = useState('')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const onSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = { style, budget: budget ? parseFloat(budget) : null }
      const data = await recommendFurniture(payload)
      setItems(data.recommendations)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <input
          className="border p-2 rounded"
          value={style}
          onChange={(e) => setStyle(e.target.value)}
          placeholder="Style (e.g. modern)"
        />
        <input
          className="border p-2 rounded"
          value={budget}
          onChange={(e) => setBudget(e.target.value)}
          placeholder="Budget"
        />
        <button
          className="px-4 py-2 bg-green-600 text-white rounded disabled:opacity-50"
          onClick={onSubmit}
          disabled={loading}
        >
          {loading ? 'Loading…' : 'Recommend'}
        </button>
      </div>
      {error && <div className="text-sm text-red-600">{error}</div>}
      <div>
        {items.map((item) => (
          <FurnitureCard key={item.item_id} item={item} />
        ))}
      </div>
    </div>
  )
}

export default FurnitureRecommend
