import React, { useState } from 'react'
import { generate3DLayout, recommendFurniture } from '../api/api'
import Viewer3D from '../components/Viewer3D'
import FurnitureCard from '../components/FurnitureCard'

const ROOM_PRESETS = [
  { label: 'Living Room', rooms: [{ label: 'living room', confidence: 1, bbox: [0, 0, 500, 400], room_type: 'living room' }] },
  { label: 'Bedroom',     rooms: [{ label: 'bedroom',     confidence: 1, bbox: [0, 0, 400, 400], room_type: 'bedroom' }] },
  { label: 'Office',      rooms: [{ label: 'office',      confidence: 1, bbox: [0, 0, 350, 300], room_type: 'office' }] },
  { label: 'Full Apt',    rooms: [
    { label: 'living room', confidence: 1, bbox: [0, 0, 500, 400], room_type: 'living room' },
    { label: 'bedroom',     confidence: 1, bbox: [0, 0, 400, 400], room_type: 'bedroom' },
    { label: 'office',      confidence: 1, bbox: [0, 0, 300, 300], room_type: 'office' },
  ]},
]

const STYLES = ['modern', 'scandinavian', 'industrial', 'luxury', 'minimalist', 'classic']

const DesignStudio = () => {
  const [preset, setPreset]     = useState(0)
  const [style, setStyle]       = useState('modern')
  const [budget, setBudget]     = useState('')
  const [sources, setSources]   = useState(['ikea', 'alibaba'])
  const [meshes, setMeshes]     = useState([])
  const [recs, setRecs]         = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  const toggleSource = (src) => {
    setSources(prev => prev.includes(src) ? prev.filter(s => s !== src) : [...prev, src])
  }

  const onGenerate = async () => {
    setLoading(true)
    setError(null)
    try {
      const rooms = ROOM_PRESETS[preset].rooms
      const [layoutData, recData] = await Promise.all([
        generate3DLayout({ rooms, style }),
        recommendFurniture({
          style,
          budget: budget ? parseFloat(budget) : null,
          rooms: rooms.map(r => r.room_type),
          preferred_sources: sources,
        }),
      ])
      setMeshes(layoutData.meshes || [])
      setRecs(recData.recommendations || [])
    } catch (e) {
      setError('Generation failed. Make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">3D Design Studio</h2>
        <p className="text-slate-500 text-sm mt-0.5">Design your space and get furniture recommendations instantly</p>
      </div>

      {/* ── Controls ── */}
      <div className="card p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
          {/* Room Preset */}
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Room Type</label>
            <div className="grid grid-cols-2 gap-1.5">
              {ROOM_PRESETS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => setPreset(i)}
                  className={`px-2 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    preset === i
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'bg-white text-slate-600 border-slate-200 hover:border-brand-300'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Style */}
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Design Style</label>
            <select value={style} onChange={(e) => setStyle(e.target.value)} className="input-field">
              {STYLES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
            </select>
          </div>

          {/* Budget */}
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Budget (USD)</label>
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="No limit"
              className="input-field"
            />
          </div>

          {/* Sources */}
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">Shop From</label>
            <div className="flex gap-2 mt-1">
              {['ikea', 'alibaba'].map(src => (
                <button
                  key={src}
                  onClick={() => toggleSource(src)}
                  className={`flex-1 py-2 rounded-lg text-sm font-semibold border transition-all ${
                    sources.includes(src)
                      ? src === 'ikea'
                        ? 'bg-ikea text-white border-ikea'
                        : 'bg-alibaba text-white border-alibaba'
                      : 'bg-white text-slate-500 border-slate-200'
                  }`}
                >
                  {src === 'ikea' ? '🔵 IKEA' : '🟠 Alibaba'}
                </button>
              ))}
            </div>
          </div>
        </div>

        <button
          className="btn-primary w-full sm:w-auto"
          onClick={onGenerate}
          disabled={loading || sources.length === 0}
        >
          {loading ? '⏳ Generating design...' : '✨ Generate 3D Design + Furniture'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* ── 3D Viewer ── */}
      {meshes.length > 0 && (
        <div className="card p-6">
          <h3 className="section-title mb-4">
            🏠 {ROOM_PRESETS[preset].label} — {style.charAt(0).toUpperCase() + style.slice(1)} Style
          </h3>
          <Viewer3D meshes={meshes} />
          <p className="text-xs text-slate-400 mt-2 text-center">
            Drag to rotate · Scroll to zoom · Right-click to pan
          </p>
        </div>
      )}

      {/* ── Recommendations ── */}
      {recs.length > 0 && (
        <div className="card p-6">
          <h3 className="section-title mb-4">🛒 Recommended Furniture ({recs.length})</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {recs.map((rec) => (
              <FurnitureCard key={rec.item_id} item={rec} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default DesignStudio
