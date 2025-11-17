import React from 'react'

const RoomCard = ({ room }) => {
  const [x1, y1, x2, y2] = room.bbox
  return (
    <div className="border rounded p-3 mb-2">
      <div className="font-semibold">{room.label}</div>
      <div className="text-sm text-gray-600">Confidence: {(room.confidence * 100).toFixed(1)}%</div>
      <div className="text-xs text-gray-500">BBox: [{x1.toFixed(1)}, {y1.toFixed(1)}] - [{x2.toFixed(1)}, {y2.toFixed(1)}]</div>
    </div>
  )
}

export default RoomCard
