import React, { useState } from 'react'
import { recommendFurniture } from '../api/api'
import FurnitureCard from '../components/FurnitureCard'

const FurnitureRecommend = () => {
  const [style, setStyle] = useState('modern')
  const [budget, setBudget] = useState('')
  const [items, setItems] = useState([])

  const onSubmit = async () => {
    const payload = { style, budget: budget ? parseFloat(budget) : null }
    const data = await recommendFurniture(payload)
    setItems(data.recommendations)
  }

  return (
    <div className="space-y-4">
      <div className="flex space-x-2">
        <input className="border p-2" value={style} onChange={(e) => setStyle(e.target.value)} placeholder="Style" />
        <input className="border p-2" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="Budget" />
        <button className="px-4 py-2 bg-green-600 text-white rounded" onClick={onSubmit}>Recommend</button>
      </div>
      <div>
        {items.map((item) => (
          <FurnitureCard key={item.item_id} item={item} />
        ))}
      </div>
    </div>
  )
}

export default FurnitureRecommend
