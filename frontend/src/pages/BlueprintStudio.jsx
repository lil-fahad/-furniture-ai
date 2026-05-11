import React, { useState, useCallback } from 'react'
import { analyzeBlueprint, recommendFurniture, generate3DLayout } from '../api/api'
import RoomCard from '../components/RoomCard'
import FurnitureCard from '../components/FurnitureCard'
import Viewer3D from '../components/Viewer3D'

const STYLES = ['modern', 'scandinavian', 'industrial', 'luxury', 'minimalist', 'classic', 'office']

const StepBadge = ({ n, active, done }) => (
  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all
    ${done ? 'bg-green-500 text-white' : active ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500'}`}>
    {done ? '✓' : n}
  </div>
)

const BlueprintStudio = () => {
  const [file, setFile]           = useState(null)
  const [preview, setPreview]     = useState(null)
  const [rooms, setRooms]         = useState([])
  const [meshes, setMeshes]       = useState([])
  const [recs, setRecs]           = useState([])
  const [style, setStyle]         = useState('modern')
  const [budget, setBudget]       = useState('')
  const [sources, setSources]     = useState(['ikea', 'alibaba'])
  const [step, setStep]           = useState(0)   // 0=upload 1=detected 2=recs 3=3d
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const [dragOver, setDragOver]   = useState(false)

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setRooms([])
    setRecs([])
    setMeshes([])
    setStep(0)
    setError(null)
  }

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f && f.type.startsWith('image/')) handleFile(f)
  }, [])

  const onAnalyze = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const data = await analyzeBlueprint(file)
      setRooms(data.rooms || [])
      if (data.preview_url) setPreview(data.preview_url)
      setStep(1)
    } catch (e) {
      setError('Blueprint analysis failed. Make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  const onRecommend = async () => {
    setLoading(true)
    setError(null)
    try {
      const roomNames = rooms.map(r => r.room_type || r.label)
      const payload = {
        style,
        budget: budget ? parseFloat(budget) : null,
        rooms: roomNames,
        preferred_sources: sources,
      }
      const data = await recommendFurniture(payload)
      setRecs(data.recommendations || [])
      setStep(2)
    } catch (e) {
      setError('Recommendation failed. Make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  const onGenerate3D = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = { rooms, style }
      const data = await generate3DLayout(payload)
      setMeshes(data.meshes || [])
      setStep(3)
    } catch (e) {
      setError('3D generation failed. Make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  const toggleSource = (src) => {
    setSources(prev =>
      prev.includes(src) ? prev.filter(s => s !== src) : [...prev, src]
    )
  }

  return (
    <div className="space-y-8">
      {/* ── Steps indicator ── */}
      <div className="flex items-center gap-3">
        {['Upload Blueprint', 'Detect Rooms', 'Get Furniture', 'View 3D'].map((label, i) => (
          <React.Fragment key={i}>
            <div className="flex items-center gap-2">
              <StepBadge n={i + 1} active={step === i} done={step > i} />
              <span className={`text-sm hidden sm:inline ${step >= i ? 'text-slate-700 font-medium' : 'text-slate-400'}`}>
                {label}
              </span>
            </div>
            {i < 3 && <div className={`flex-1 h-0.5 ${step > i ? 'bg-brand-400' : 'bg-slate-200'}`} />}
          </React.Fragment>
        ))}
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm flex items-center gap-2">
          <span>⚠️</span> {error}
        </div>
      )}

      {/* ── Step 0: Upload ── */}
      <div className="card p-6">
        <h2 className="section-title mb-4">📐 Upload Floor Plan Blueprint</h2>
        <div
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => document.getElementById('bp-input').click()}
          className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200
            ${dragOver ? 'border-brand-400 bg-brand-50' : 'border-slate-300 hover:border-brand-300 hover:bg-slate-50'}`}
        >
          <input
            id="bp-input"
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => handleFile(e.target.files[0])}
          />
          {preview && !preview.startsWith('data:') ? (
            <img src={preview} alt="Blueprint preview" className="max-h-48 mx-auto rounded-xl object-contain" />
          ) : (
            <>
              <div className="text-5xl mb-3">🗺️</div>
              <p className="text-slate-600 font-medium">Drop your floor plan here or click to browse</p>
              <p className="text-slate-400 text-sm mt-1">PNG, JPG, SVG supported</p>
            </>
          )}
        </div>

        {/* Annotated preview after analysis */}
        {preview && preview.startsWith('data:') && (
          <div className="mt-4">
            <p className="text-sm font-medium text-slate-600 mb-2">Annotated Blueprint</p>
            <img src={preview} alt="Annotated blueprint" className="max-h-64 rounded-xl border border-slate-200 object-contain" />
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-3 items-end">
          <button className="btn-primary" onClick={onAnalyze} disabled={!file || loading}>
            {loading && step === 0 ? '⏳ Analyzing...' : '🔍 Analyze Blueprint'}
          </button>
          {file && (
            <span className="text-sm text-slate-500">📄 {file.name}</span>
          )}
        </div>
      </div>

      {/* ── Step 1: Detected Rooms ── */}
      {rooms.length > 0 && (
        <div className="card p-6">
          <h2 className="section-title mb-4">🏠 Detected Rooms ({rooms.length})</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
            {rooms.map((room, idx) => (
              <RoomCard key={idx} room={room} />
            ))}
          </div>

          {/* Preferences for recommendations */}
          <div className="bg-slate-50 rounded-xl p-4 space-y-4">
            <h3 className="font-semibold text-slate-700">Furniture Preferences</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-500 mb-1 block">Style</label>
                <select
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  className="input-field"
                >
                  {STYLES.map(s => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 mb-1 block">Budget (USD)</label>
                <input
                  type="number"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  placeholder="e.g. 2000"
                  className="input-field"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 mb-1 block">Sources</label>
                <div className="flex gap-2 mt-1">
                  {['ikea', 'alibaba'].map(src => (
                    <button
                      key={src}
                      onClick={() => toggleSource(src)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-semibold border transition-all ${
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
            <button className="btn-primary" onClick={onRecommend} disabled={loading || sources.length === 0}>
              {loading && step === 1 ? '⏳ Finding furniture...' : '🛋️ Get Furniture Recommendations'}
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2: Recommendations ── */}
      {recs.length > 0 && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title">🛒 Recommended Furniture ({recs.length})</h2>
            <button className="btn-secondary text-sm" onClick={onGenerate3D} disabled={loading}>
              {loading && step === 2 ? '⏳ Generating...' : '🏠 Generate 3D Layout'}
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {recs.map((rec) => (
              <FurnitureCard key={rec.item_id} item={rec} />
            ))}
          </div>
        </div>
      )}

      {/* ── Step 3: 3D Viewer ── */}
      {meshes.length > 0 && (
        <div className="card p-6">
          <h2 className="section-title mb-4">🏠 3D Room Layout</h2>
          <Viewer3D meshes={meshes} />
        </div>
      )}
    </div>
  )
}

export default BlueprintStudio
