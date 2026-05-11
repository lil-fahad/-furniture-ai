import React from 'react'

// Simple file uploader — drag-and-drop is handled inline in BlueprintStudio
const FileUploader = ({ onChange, label, accept = 'image/*' }) => {
  return (
    <div>
      {label && <label className="block text-sm font-medium text-slate-600 mb-1">{label}</label>}
      <input
        type="file"
        accept={accept}
        onChange={(e) => onChange && onChange(e.target.files[0])}
        className="block w-full text-sm text-slate-500 file:mr-3 file:py-2 file:px-4
                   file:rounded-lg file:border-0 file:text-sm file:font-semibold
                   file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 cursor-pointer"
      />
    </div>
  )
}

export default FileUploader
