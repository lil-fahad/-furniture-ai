import React from 'react'

const FurnitureCard = ({ item }) => {
  return (
    <div className="border rounded p-3 mb-2">
      <div className="font-semibold">{item.name}</div>
      <div className="text-sm text-gray-600">Category: {item.category}</div>
      <div className="text-sm text-gray-600">Score: {(item.score * 100).toFixed(1)}%</div>
    </div>
  )
}

export default FurnitureCard
