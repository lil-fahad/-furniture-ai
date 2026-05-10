import React, { useState, useRef, useEffect } from 'react'
import { aiChat, aiRecommend } from '../api/api'

const STYLES = ['modern', 'minimalist', 'scandinavian', 'industrial', 'bohemian', 'classic', 'contemporary']

const AIChat = () => {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I am your AI interior design consultant powered by Alibaba Cloud (Qwen). Ask me anything about furniture, room design, or get personalized recommendations!',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('chat')

  // Recommend tab state
  const [style, setStyle] = useState('modern')
  const [budget, setBudget] = useState('')
  const [rooms, setRooms] = useState('')
  const [recResult, setRecResult] = useState(null)
  const [recLoading, setRecLoading] = useState(false)

  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const userMsg = { role: 'user', content: input.trim() }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    setLoading(true)
    setError(null)

    try {
      // Send all messages except the initial assistant greeting
      const apiMessages = newMessages.filter((m, i) => !(i === 0 && m.role === 'assistant'))
      const data = await aiChat(apiMessages)
      setMessages([...newMessages, { role: 'assistant', content: data.reply }])
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message
      setError(errMsg)
      setMessages([...newMessages, { role: 'assistant', content: `Error: ${errMsg}` }])
    } finally {
      setLoading(false)
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const onGetRecommendations = async () => {
    setRecLoading(true)
    setError(null)
    try {
      const roomList = rooms.split(',').map((r) => r.trim()).filter(Boolean)
      const data = await aiRecommend({
        style,
        budget: budget ? parseFloat(budget) : null,
        rooms: roomList.length ? roomList : null,
      })
      setRecResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setRecLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-xl font-bold">AI Design Assistant</h2>
        <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">
          Powered by Alibaba Cloud Qwen
        </span>
      </div>

      {/* Tabs */}
      <div className="flex border-b">
        {['chat', 'recommend'].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
              tab === t
                ? 'border-orange-500 text-orange-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'chat' ? 'Chat' : 'AI Recommendations'}
          </button>
        ))}
      </div>

      {tab === 'chat' && (
        <div className="flex flex-col h-[500px]">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto border rounded-lg p-4 space-y-3 bg-gray-50">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap ${
                    msg.role === 'user'
                      ? 'bg-orange-500 text-white'
                      : 'bg-white border text-gray-800 shadow-sm'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border rounded-lg px-4 py-2 text-sm text-gray-400 shadow-sm">
                  Thinking...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="flex gap-2 mt-3">
            <textarea
              className="flex-1 border rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-orange-300"
              rows={2}
              placeholder="Ask about furniture, room design, styles... (Enter to send)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              disabled={loading}
            />
            <button
              className="px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium disabled:opacity-50"
              onClick={sendMessage}
              disabled={loading || !input.trim()}
            >
              Send
            </button>
          </div>

          {error && (
            <div className="text-red-600 text-xs mt-1 bg-red-50 border border-red-200 rounded p-2">
              {error}
            </div>
          )}
        </div>
      )}

      {tab === 'recommend' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Style</label>
              <select
                className="w-full border rounded px-3 py-2 text-sm"
                value={style}
                onChange={(e) => setStyle(e.target.value)}
              >
                {STYLES.map((s) => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Budget (USD)</label>
              <input
                className="w-full border rounded px-3 py-2 text-sm"
                type="number"
                placeholder="e.g. 2000"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Rooms (comma-separated)</label>
              <input
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="e.g. living room, bedroom"
                value={rooms}
                onChange={(e) => setRooms(e.target.value)}
              />
            </div>
          </div>

          <button
            className="px-5 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded text-sm font-medium disabled:opacity-50"
            onClick={onGetRecommendations}
            disabled={recLoading}
          >
            {recLoading ? 'Getting AI Recommendations...' : 'Get AI Recommendations'}
          </button>

          {error && (
            <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded p-3">
              {error}
            </div>
          )}

          {recResult && (
            <div className="space-y-4">
              {recResult.summary && (
                <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap">
                  <div className="font-medium text-orange-700 mb-1">AI Summary</div>
                  {recResult.summary}
                </div>
              )}

              {recResult.recommendations?.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-gray-700 mb-2">
                    Recommended Items ({recResult.recommendations.length})
                  </div>
                  <div className="grid grid-cols-1 gap-3">
                    {recResult.recommendations.map((item, i) => (
                      <div key={i} className="border rounded-lg p-4 bg-white shadow-sm">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="font-medium text-gray-900">{item.name}</div>
                            <div className="text-xs text-gray-500 mt-0.5">
                              {item.category} &bull; {item.price_range || 'Price varies'}
                            </div>
                          </div>
                          {item.source && (
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                              item.source?.toLowerCase().includes('ikea')
                                ? 'bg-yellow-100 text-yellow-700'
                                : 'bg-orange-100 text-orange-700'
                            }`}>
                              {item.source}
                            </span>
                          )}
                        </div>
                        {item.reason && (
                          <div className="text-xs text-gray-600 mt-2">{item.reason}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AIChat
