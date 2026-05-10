import React from 'react'

const ROOM_ICONS = {
  'living room': '🛋️',
  'bedroom':     '🛏️',
  'kitchen':     '🍳',
  'bathroom':    '🚿',
  'office':      '💼',
  'dining room': '🍽️',
  'room':        '🏠',
}

const ROOM_COLORS = {
  'living room': 'bg-blue-50 border-blue-200 text-blue-700',
  'bedroom':     'bg-green-50 border-green-200 text-green-700',
  'kitchen':     'bg-orange-50 border-orange-200 text-orange-700',
  'bathroom':    'bg-purple-50 border-purple-200 text-purple-700',
  'office':      'bg-yellow-50 border-yellow-200 text-yellow-700',
  'dining room': 'bg-pink-50 border-pink-200 text-pink-700',
  'room':        'bg-slate-50 border-slate-200 text-slate-700',
}

const RoomCard = ({ room }) => {
  const [x1, y1, x2, y2] = room.bbox
  const label = room.room_type || room.label || 'room'
  const icon  = ROOM_ICONS[label.toLowerCase()] || '🏠'
  const colorClass = ROOM_COLORS[label.toLowerCase()] || ROOM_COLORS['room']

  return (
    <div className={`border rounded-xl p-3 flex items-start gap-3 ${colorClass}`}>
      <span className="text-2xl mt-0.5">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="font-semibold capitalize text-sm">{label}</div>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <span className="text-xs opacity-75">
            Confidence: {(room.confidence * 100).toFixed(0)}%
          </span>
          {room.area_sqm && (
            <span className="text-xs opacity-75">
              Area: {room.area_sqm} m²
            </span>
          )}
        </div>
        <div className="text-xs opacity-60 mt-0.5">
          {x1.toFixed(0)},{y1.toFixed(0)} → {x2.toFixed(0)},{y2.toFixed(0)}
        </div>
      </div>
      {/* Confidence bar */}
      <div className="w-1 self-stretch rounded-full bg-current opacity-20 relative overflow-hidden">
        <div
          className="absolute bottom-0 left-0 right-0 bg-current opacity-80 rounded-full"
          style={{ height: `${room.confidence * 100}%` }}
        />
      </div>
    </div>
  )
}

export default RoomCard
