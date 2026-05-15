import React from 'react'
import RoomDetection from './pages/RoomDetection'
import FurnitureRecommend from './pages/FurnitureRecommend'
import Auto3D from './pages/Auto3D'

const Section = ({ title, children }) => (
  <section className="bg-white shadow rounded-lg p-6 space-y-4">
    <h2 className="text-xl font-semibold border-b pb-2">{title}</h2>
    {children}
  </section>
)

const App = () => {
  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold">Furniture AI System</h1>
        <p className="text-slate-600">
          Blueprint analysis, furniture recommendations, and 3D layout synthesis.
        </p>
      </header>
      <Section title="Room Detection">
        <RoomDetection />
      </Section>
      <Section title="Furniture Recommendation">
        <FurnitureRecommend />
      </Section>
      <Section title="3D Layout Generation">
        <Auto3D />
      </Section>
    </div>
  )
}

export default App
