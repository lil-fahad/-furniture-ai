import React, { useState } from 'react'
import BlueprintStudio from './pages/BlueprintStudio'
import FurnitureCatalog from './pages/FurnitureCatalog'
import DesignStudio from './pages/DesignStudio'

const NAV_TABS = [
  { id: 'blueprint', label: 'Blueprint Studio', emoji: '📐' },
  { id: 'catalog',   label: 'Furniture Catalog', emoji: '🛋️' },
  { id: 'design',    label: '3D Design Studio',  emoji: '🏠' },
]

const App = () => {
  const [activeTab, setActiveTab] = useState('blueprint')

  return (
    <div className="min-h-screen bg-slate-50">
      {/* ── Header ── */}
      <header className="hero-gradient text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-white/20 rounded-xl flex items-center justify-center text-xl">🏡</div>
              <div>
                <h1 className="text-lg font-bold leading-tight">FurnitureAI</h1>
                <p className="text-xs text-white/70 leading-tight">Blueprint → Design → Shop</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-white/80">
              <span className="px-2 py-1 bg-white/10 rounded-lg">IKEA</span>
              <span className="px-2 py-1 bg-white/10 rounded-lg">Alibaba</span>
              <span className="px-2 py-1 bg-white/10 rounded-lg">AI Powered</span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Tab Navigation ── */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex gap-1 py-2">
            {NAV_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm transition-all duration-200 ${
                  activeTab === tab.id ? 'tab-active' : 'tab-inactive'
                }`}
              >
                <span>{tab.emoji}</span>
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* ── Page Content ── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'blueprint' && <BlueprintStudio />}
        {activeTab === 'catalog'   && <FurnitureCatalog />}
        {activeTab === 'design'    && <DesignStudio />}
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-slate-200 bg-white mt-16">
        <div className="max-w-7xl mx-auto px-4 py-6 text-center text-sm text-slate-400">
          FurnitureAI — AI-powered interior design from blueprints &nbsp;·&nbsp; IKEA &amp; Alibaba integration
        </div>
      </footer>
    </div>
  )
}

export default App
