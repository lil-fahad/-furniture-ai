import React from 'react'

const Viewer3D = ({ meshes }) => {
  return (
    <div className="border rounded p-4 h-64 overflow-auto">
      <div className="font-semibold mb-2">3D Meshes</div>
      {meshes && meshes.length > 0 ? (
        <pre className="text-xs bg-gray-100 p-2 rounded h-full">{JSON.stringify(meshes, null, 2)}</pre>
      ) : (
        <div className="text-gray-500">No meshes available</div>
      )}
    </div>
  )
}

export default Viewer3D
