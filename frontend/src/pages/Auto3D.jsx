import React, { useState } from 'react'
import { generate3DLayout } from '../api/api'
import Viewer3D from '../components/Viewer3D'

const Auto3D = () => {
  const [meshes, setMeshes] = useState([])
  const [blueprintUrl, setBlueprintUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const onGenerate = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = { blueprint_url: blueprintUrl || null }
      const data = await generate3DLayout(payload)
      setMeshes(data.meshes || [])
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <input
        className="border p-2 w-full rounded"
        value={blueprintUrl}
        onChange={(e) => setBlueprintUrl(e.target.value)}
        placeholder="Blueprint URL (optional)"
      />
      <button
        className="px-4 py-2 bg-purple-600 text-white rounded disabled:opacity-50"
        onClick={onGenerate}
        disabled={loading}
      >
        {loading ? 'Generating…' : 'Generate 3D Layout'}
      </button>
      {error && <div className="text-sm text-red-600">{error}</div>}
      <Viewer3D meshes={meshes} />
    </div>
  )
}

export default Auto3D
