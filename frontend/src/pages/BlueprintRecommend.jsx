import React, { useState } from 'react'
import FileUploader from '../components/FileUploader'
import FurnitureCard from '../components/FurnitureCard'
import { analyzeBlueprint, blueprintRecommend } from '../api/api'

const STYLES = ['modern', 'classic', 'minimalist', 'industrial', 'scandinavian', 'bohemian']

const BlueprintRecommend = () => {
  const [file, setFile] = useState(null)
  const [style, setStyle] = useState('modern')
  const [budget, setBudget] = useState('')
  const [sources, setSources] = useState(['ikea', 'alibaba'])
  const [maxPerSource, setMaxPerSource] = useState(5)

  const [step, setStep] = useState('idle') // idle | analyzing | recommending | done
  const [preview, setPreview] = useState(null)
  const [rooms, setRooms] = useState([])
  const [ikea, setIkea] = useState([])
  const [alibaba, setAlibaba] = useState([])
  const [aiRecs, setAiRecs] = useState([])
  const [error, setError] = useState(null)

  const toggleSource = (src) => {
    setSources((prev) =>
      prev.includes(src) ? prev.filter((s) => s !== src) : [...prev, src]
    )
  }

  const onRun = async () => {
    if (!file) return
    setError(null)
    setIkea([])
    setAlibaba([])
    setAiRecs([])

    try {
      // Step 1: analyze blueprint
      setStep('analyzing')
      const analysis = await analyzeBlueprint(file)
      setPreview(analysis.preview_url || null)
      const detectedRooms = (analysis.rooms || []).map((r) => r.label)
      setRooms(detectedRooms)

      // Step 2: get recommendations
      setStep('recommending')
      const result = await blueprintRecommend({
        style,
        budget: budget ? parseFloat(budget) : null,
        rooms: detectedRooms,
        sources,
        max_per_source: maxPerSource,
      })
      setIkea(result.ikea_products || [])
      setAlibaba(result.alibaba_products || [])
      setAiRecs(result.ai_recommendations || [])
      setStep('done')
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      setStep('idle')
    }
  }

  const isLoading = step === 'analyzing' || step === 'recommending'

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-bold">Blueprint → Furniture Recommendations</h2>
      <p className="text-sm text-gray-500">
        Upload a floor plan image. The AI will detect rooms and suggest matching furniture from IKEA and Alibaba.
      </p>

      {/* Controls */}
      <div className="bg-gray-50 border rounded-lg p-4 space-y-3">
        <FileUploader label="Upload Floor Plan / Blueprint" onChange={setFile} />

        <div className="flex flex-wrap gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">Style</label>
            <select
              className="border rounded px-3 py-1.5 text-sm"
              value={style}
              onChange={(e) => setStyle(e.target.value)}
            >
              {STYLES.map((s) => (
                <option key={s} value={s} className="capitalize">{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">Budget (USD)</label>
            <input
              className="border rounded px-3 py-1.5 text-sm w-32"
              placeholder="e.g. 2000"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              type="number"
              min="0"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">Results per store</label>
            <select
              className="border rounded px-3 py-1.5 text-sm"
              value={maxPerSource}
              onChange={(e) => setMaxPerSource(Number(e.target.value))}
            >
              {[3, 5, 10, 20].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex gap-4">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={sources.includes('ikea')}
              onChange={() => toggleSource('ikea')}
              className="accent-yellow-500"
            />
            <span className="font-medium text-yellow-700">IKEA</span>
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={sources.includes('alibaba')}
              onChange={() => toggleSource('alibaba')}
              className="accent-orange-500"
            />
            <span className="font-medium text-orange-700">Alibaba / AliExpress</span>
          </label>
        </div>

        <button
          className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium disabled:opacity-50"
          onClick={onRun}
          disabled={isLoading || !file}
        >
          {step === 'analyzing' ? 'Analyzing blueprint…' : step === 'recommending' ? 'Fetching products…' : 'Analyze & Recommend'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded p-3">{error}</div>
      )}

      {/* Blueprint preview */}
      {preview && (
        <div>
          <div className="text-sm font-medium text-gray-600 mb-1">Blueprint Preview</div>
          <img src={preview} alt="Blueprint preview" className="max-w-sm rounded border" />
          {rooms.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {rooms.map((r, i) => (
                <span key={i} className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                  {r}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Results */}
      {step === 'done' && (
        <div className="space-y-6">
          {/* IKEA */}
          {ikea.length > 0 && (
            <div>
              <h3 className="text-base font-semibold text-yellow-700 mb-2">
                IKEA Suggestions ({ikea.length})
              </h3>
              {ikea.map((p) => <FurnitureCard key={p.item_id} item={p} />)}
            </div>
          )}

          {/* Alibaba */}
          {alibaba.length > 0 && (
            <div>
              <h3 className="text-base font-semibold text-orange-700 mb-2">
                Alibaba / AliExpress Suggestions ({alibaba.length})
              </h3>
              {alibaba.map((p) => <FurnitureCard key={p.item_id} item={p} />)}
            </div>
          )}

          {/* AI recommendations */}
          {aiRecs.length > 0 && (
            <div>
              <h3 className="text-base font-semibold text-purple-700 mb-2">
                AI Recommendations ({aiRecs.length})
              </h3>
              {aiRecs.map((p) => <FurnitureCard key={p.item_id} item={p} />)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default BlueprintRecommend
