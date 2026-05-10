import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000,
})

// ── Blueprint Analysis ──────────────────────────────────────────────────────
export const analyzeBlueprint = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await client.post('/analyze/blueprint', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

// ── Furniture Recommendations ───────────────────────────────────────────────
export const recommendFurniture = async (payload) => {
  const { data } = await client.post('/recommend/furniture', payload)
  return data
}

// ── 3D Layout ───────────────────────────────────────────────────────────────
export const generate3DLayout = async (payload) => {
  const { data } = await client.post('/layout3d/generate', payload)
  return data
}

// ── Catalog ─────────────────────────────────────────────────────────────────
export const getCatalogProducts = async (params = {}) => {
  const { data } = await client.get('/catalog/products', { params })
  return data
}

export const getCatalogCategories = async () => {
  const { data } = await client.get('/catalog/categories')
  return data
}

export default client
