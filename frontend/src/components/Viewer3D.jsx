import React, { useRef, useEffect, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

const LABEL_COLORS = {
  'living room': '#93C5FD',
  'bedroom':     '#86EFAC',
  'kitchen':     '#FCD34D',
  'bathroom':    '#C4B5FD',
  'office':      '#FDE68A',
  'dining room': '#FBCFE8',
  'room':        '#E2E8F0',
  'sofa':        '#92400E',
  'chair':       '#78350F',
  'table':       '#D97706',
  'bed':         '#1D4ED8',
  'desk':        '#B45309',
  'storage':     '#6B7280',
  'rug':         '#9D174D',
  'lamp':        '#F59E0B',
  'object':      '#94A3B8',
}

const Viewer3D = ({ meshes }) => {
  const mountRef  = useRef(null)
  const sceneRef  = useRef(null)
  const [legend, setLegend] = useState([])

  useEffect(() => {
    if (!meshes || meshes.length === 0) return
    const mount = mountRef.current
    if (!mount) return

    // ── Scene setup ──────────────────────────────────────────────────────
    const width  = mount.clientWidth  || 800
    const height = mount.clientHeight || 480

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.setClearColor(0xf8fafc, 1)
    mount.appendChild(renderer.domElement)

    const scene  = new THREE.Scene()
    sceneRef.current = scene

    // Fog for depth
    scene.fog = new THREE.Fog(0xf8fafc, 20, 60)

    // ── Camera ───────────────────────────────────────────────────────────
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 200)
    camera.position.set(8, 10, 14)
    camera.lookAt(0, 0, 0)

    // ── Lights ───────────────────────────────────────────────────────────
    const ambient = new THREE.AmbientLight(0xffffff, 0.6)
    scene.add(ambient)

    const sun = new THREE.DirectionalLight(0xfff5e0, 1.2)
    sun.position.set(10, 20, 10)
    sun.castShadow = true
    sun.shadow.mapSize.width  = 2048
    sun.shadow.mapSize.height = 2048
    sun.shadow.camera.near = 0.5
    sun.shadow.camera.far  = 100
    sun.shadow.camera.left = sun.shadow.camera.bottom = -20
    sun.shadow.camera.right = sun.shadow.camera.top   =  20
    scene.add(sun)

    const fill = new THREE.DirectionalLight(0xc7d2fe, 0.4)
    fill.position.set(-8, 5, -5)
    scene.add(fill)

    // ── Grid floor ───────────────────────────────────────────────────────
    const grid = new THREE.GridHelper(40, 40, 0xdde1e7, 0xe8eaed)
    grid.position.y = -0.01
    scene.add(grid)

    // ── Build meshes ─────────────────────────────────────────────────────
    const legendMap = {}
    let minX = Infinity, maxX = -Infinity
    let minZ = Infinity, maxZ = -Infinity

    meshes.forEach((m) => {
      if (!m.vertices || !m.faces) return

      const geometry = new THREE.BufferGeometry()
      const positions = new Float32Array(m.vertices.flat())
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))

      const indices = new Uint16Array(m.faces.flat())
      geometry.setIndex(new THREE.BufferAttribute(indices, 1))
      geometry.computeVertexNormals()

      const hexColor = LABEL_COLORS[m.label?.toLowerCase()] || m.color || '#94A3B8'
      const color    = new THREE.Color(hexColor)

      // Rooms get wireframe + transparent fill; furniture gets solid
      const isRoom = ['room', 'living room', 'bedroom', 'kitchen', 'bathroom', 'office', 'dining room'].includes(m.label?.toLowerCase())

      const material = new THREE.MeshLambertMaterial({
        color,
        transparent: true,
        opacity: isRoom ? 0.15 : 0.92,
        side: THREE.DoubleSide,
      })
      const mesh3d = new THREE.Mesh(geometry, material)
      mesh3d.castShadow    = !isRoom
      mesh3d.receiveShadow = true
      scene.add(mesh3d)

      // Wireframe edges
      const edges    = new THREE.EdgesGeometry(geometry)
      const lineMat  = new THREE.LineBasicMaterial({
        color: isRoom ? 0x94a3b8 : new THREE.Color(hexColor).multiplyScalar(0.6),
        linewidth: 1,
        transparent: true,
        opacity: isRoom ? 0.5 : 0.8,
      })
      scene.add(new THREE.LineSegments(edges, lineMat))

      // Track bounds for camera centering
      m.vertices.forEach(([vx, , vz]) => {
        minX = Math.min(minX, vx); maxX = Math.max(maxX, vx)
        minZ = Math.min(minZ, vz); maxZ = Math.max(maxZ, vz)
      })

      // Legend
      if (m.label && !legendMap[m.label]) {
        legendMap[m.label] = hexColor
      }
    })

    setLegend(Object.entries(legendMap))

    // Center camera on scene
    const cx = (minX + maxX) / 2
    const cz = (minZ + maxZ) / 2
    const span = Math.max(maxX - minX, maxZ - minZ, 4)
    camera.position.set(cx + span * 0.8, span * 0.9, cz + span * 0.8)
    camera.lookAt(cx, 0, cz)

    // ── Controls ─────────────────────────────────────────────────────────
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(cx, 0, cz)
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controls.minDistance   = 2
    controls.maxDistance   = 60
    controls.maxPolarAngle = Math.PI / 2.1
    controls.update()

    // ── Resize handler ───────────────────────────────────────────────────
    const onResize = () => {
      const w = mount.clientWidth
      const h = mount.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', onResize)

    // ── Animation loop ───────────────────────────────────────────────────
    let animId
    const animate = () => {
      animId = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    // ── Cleanup ──────────────────────────────────────────────────────────
    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', onResize)
      controls.dispose()
      renderer.dispose()
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement)
      }
    }
  }, [meshes])

  if (!meshes || meshes.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center bg-slate-100 rounded-2xl border-2 border-dashed border-slate-300">
        <div className="text-center text-slate-400">
          <div className="text-4xl mb-2">🏠</div>
          <p className="font-medium">3D layout will appear here</p>
          <p className="text-sm">Generate a layout to see your room in 3D</p>
        </div>
      </div>
    )
  }

  return (
    <div className="relative">
      {/* Canvas */}
      <div
        ref={mountRef}
        className="w-full rounded-2xl overflow-hidden border border-slate-200"
        style={{ height: '480px' }}
      />

      {/* Legend */}
      {legend.length > 0 && (
        <div className="absolute bottom-3 left-3 bg-white/90 backdrop-blur-sm rounded-xl p-3 shadow-card">
          <p className="text-xs font-semibold text-slate-600 mb-2">Legend</p>
          <div className="space-y-1">
            {legend.map(([label, color]) => (
              <div key={label} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-sm flex-shrink-0" style={{ backgroundColor: color }} />
                <span className="text-xs text-slate-600 capitalize">{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Controls hint */}
      <div className="absolute bottom-3 right-3 bg-white/80 backdrop-blur-sm rounded-lg px-2 py-1">
        <p className="text-xs text-slate-400">🖱️ Drag · Scroll · Right-click</p>
      </div>
    </div>
  )
}

export default Viewer3D
