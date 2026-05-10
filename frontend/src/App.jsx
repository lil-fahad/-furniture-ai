import React, { useState } from 'react'
import RoomDetection from './pages/RoomDetection'
import FurnitureRecommend from './pages/FurnitureRecommend'
import Auto3D from './pages/Auto3D'
import FurnitureSearch from './pages/FurnitureSearch'
import BlueprintRecommend from './pages/BlueprintRecommend'

const TABS = [
  { id: 'blueprint', label: 'Blueprint → Furniture' },
  { id: 'search', label: 'Search Products' },
  { id: 'detect', label: 'Room Detection' },
  { id: 'recommend', label: 'AI Recommend' },
  { id: '3d', label: '3D Layout' },
]

const App = () => {
  const [activeTab, setActiveTab] = useState('blueprint')

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Furniture AI System</h1>
        <p className="text-gray-500 text-sm mt-1">
          Design your space from a floor plan — get furniture from IKEA and Alibaba
        </p>
      </div>

      {/* Navigation */}
      <div className="flex flex-wrap gap-1 border-b mb-6">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium rounded-t border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-blue-600 text-blue-700 bg-blue-50'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Page content */}
      <div>
        {activeTab === 'blueprint' && <BlueprintRecommend />}
        {activeTab === 'search' && <FurnitureSearch />}
        {activeTab === 'detect' && <RoomDetection />}
        {activeTab === 'recommend' && <FurnitureRecommend />}
        {activeTab === '3d' && <Auto3D />}
      </div>
    </div>
  )
}

export default App
