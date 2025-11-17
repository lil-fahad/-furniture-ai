import React from 'react'
import RoomDetection from './pages/RoomDetection'
import FurnitureRecommend from './pages/FurnitureRecommend'
import Auto3D from './pages/Auto3D'

const App = () => {
  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <h1 className="text-3xl font-bold">Furniture AI System</h1>
      <RoomDetection />
      <FurnitureRecommend />
      <Auto3D />
    </div>
  )
}

export default App
