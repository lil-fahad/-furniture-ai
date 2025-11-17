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

export default client
