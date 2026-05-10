import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000'
})

export const analyzeBlueprint = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await client.post('/analyze/blueprint', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export const recommendFurniture = async (payload) => {
  const { data } = await client.post('/recommend/furniture', payload)
  return data
}

export const generate3DLayout = async (payload) => {
  const { data } = await client.post('/layout3d/generate', payload)
  return data
}

// IKEA product search
export const searchIKEA = async (query, category = null, maxResults = 10) => {
  const params = { query, max_results: maxResults }
  if (category) params.category = category
  const { data } = await client.get('/search/ikea', { params })
  return data
}

// Alibaba product search
export const searchAlibaba = async (query, category = null, maxResults = 10) => {
  const params = { query, max_results: maxResults }
  if (category) params.category = category
  const { data } = await client.get('/search/alibaba', { params })
  return data
}

// Combined blueprint-based recommendation (AI + IKEA + Alibaba)
export const blueprintRecommend = async (payload) => {
  const { data } = await client.post('/search/blueprint-recommend', payload)
  return data
}

// Alibaba Cloud DashScope AI endpoints
export const aiChat = async (messages, systemPrompt = null) => {
  const payload = { messages }
  if (systemPrompt) payload.system_prompt = systemPrompt
  const { data } = await client.post('/ai/chat', payload)
  return data
}

export const aiRecommend = async (payload) => {
  const { data } = await client.post('/ai/recommend', payload)
  return data
}

export const aiBlueprintAnalysis = async (detectedRooms, style = 'modern') => {
  const { data } = await client.post('/ai/blueprint-analysis', {
    detected_rooms: detectedRooms,
    style,
  })
  return data
}

export const aiStatus = async () => {
  const { data } = await client.get('/ai/status')
  return data
}

export default client
