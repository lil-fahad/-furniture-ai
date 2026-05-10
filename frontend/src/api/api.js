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

// ── AI Assist (Alibaba Cloud DashScope / Qwen) ───────────────────────────────

/**
 * Generate an AI furniture plan for given rooms.
 * @param {Object} payload - { room_types, area_sqm, style, budget }
 */
export const getRoomPlan = async (payload) => {
  const { data } = await client.post('/ai/room-plan', payload)
  return data
}

/**
 * Get an AI-suggested color palette for a room.
 * @param {Object} payload - { style, room_type, existing_colors }
 */
export const getColorPalette = async (payload) => {
  const { data } = await client.post('/ai/color-palette', payload)
  return data
}

/**
 * Enrich a product description using Qwen AI.
 * @param {Object} payload - { product_name, category, styles, dimensions, colors }
 */
export const enrichProductDescription = async (payload) => {
  const { data } = await client.post('/ai/enrich-description', payload)
  return data
}

/**
 * Chat with the AI interior design assistant.
 * @param {string} message - User message
 * @param {string} [context] - Optional context string
 */
export const aiChat = async (message, context = null) => {
  const { data } = await client.post('/ai/chat', { message, context })
  return data
}

export default client
