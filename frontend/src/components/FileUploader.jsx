import React from 'react'

const FileUploader = ({ onChange, label }) => {
  return (
    <div className="uploader">
      <label className="block text-sm font-medium mb-2">{label}</label>
      <input type="file" accept="image/*" onChange={(e) => onChange(e.target.files[0])} />
    </div>
  )
}

export default FileUploader
