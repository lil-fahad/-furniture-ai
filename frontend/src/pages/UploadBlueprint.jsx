import React, { useState } from 'react'
import FileUploader from '../components/FileUploader'
import { analyzeBlueprint } from '../api/api'
import RoomCard from '../components/RoomCard'

const UploadBlueprint = () => {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const onAnalyze = async () => {
    if (!file) return
    setLoading(true)
    const data = await analyzeBlueprint(file)
    setResult(data)
    setLoading(false)
  }

  return (
    <div className="space-y-4">
      <FileUploader label="Upload Blueprint" onChange={setFile} />
      <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={onAnalyze} disabled={loading}>
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>
      {result?.preview_url && <img src={result.preview_url} alt="Preview" className="max-w-md" />}
      <div>
        {result?.rooms?.map((room, idx) => (
          <RoomCard key={idx} room={room} />
        ))}
      </div>
    </div>
  )
}

export default UploadBlueprint
