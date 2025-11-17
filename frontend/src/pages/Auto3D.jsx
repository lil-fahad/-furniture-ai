import React, { useState } from 'react'
import { generate3DLayout } from '../api/api'
import Viewer3D from '../components/Viewer3D'

const Auto3D = () => {
  const [meshes, setMeshes] = useState([])
  const [blueprintUrl, setBlueprintUrl] = useState('')

  const onGenerate = async () => {
    const payload = { blueprint_url: blueprintUrl || null }
    const data = await generate3DLayout(payload)
    setMeshes(data.meshes)
  }

  return (
    <div className="space-y-4">
      <input className="border p-2 w-full" value={blueprintUrl} onChange={(e) => setBlueprintUrl(e.target.value)} placeholder="Blueprint URL (optional)" />
      <button className="px-4 py-2 bg-purple-600 text-white rounded" onClick={onGenerate}>Generate 3D Layout</button>
      <Viewer3D meshes={meshes} />
    </div>
  )
}

export default Auto3D
