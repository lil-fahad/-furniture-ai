import React, { useState } from 'react'
import FileUploader from '../components/FileUploader'
import { analyzeBlueprint } from '../api/api'
import RoomCard from '../components/RoomCard'

const UploadBlueprint = () => {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const onAnalyze = async () => {
    if (!file) {
      setError('Please choose a blueprint file first.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await analyzeBlueprint(file)
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <FileUploader label="Upload Blueprint" onChange={setFile} />
      <button
        className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
        onClick={onAnalyze}
        disabled={loading}
      >
        {loading ? 'Analyzing…' : 'Analyze'}
      </button>
      {error && <div className="text-sm text-red-600">{error}</div>}
      {result?.preview_url && (
        <img src={result.preview_url} alt="Preview" className="max-w-md rounded border" />
      )}
      <div>
        {result?.rooms?.map((room, idx) => (
          <RoomCard key={idx} room={room} />
        ))}
      </div>
    </div>
  )
}

export default UploadBlueprint
