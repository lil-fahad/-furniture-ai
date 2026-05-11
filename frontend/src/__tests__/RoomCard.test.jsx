import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import RoomCard from '../components/RoomCard'

const LIVING_ROOM = {
  label: 'living room',
  room_type: 'living room',
  confidence: 0.92,
  bbox: [0, 0, 300, 200],
  area_sqm: 18.5,
}

const BEDROOM = {
  label: 'bedroom',
  room_type: 'bedroom',
  confidence: 0.88,
  bbox: [300, 0, 500, 200],
  area_sqm: 12.0,
}

const UNKNOWN_ROOM = {
  label: 'storage',
  room_type: 'storage',
  confidence: 0.75,
  bbox: [10, 10, 100, 100],
  area_sqm: null,
}

describe('RoomCard', () => {
  it('renders room label', () => {
    render(<RoomCard room={LIVING_ROOM} />)
    expect(screen.getByText('living room')).toBeInTheDocument()
  })

  it('renders confidence percentage', () => {
    render(<RoomCard room={LIVING_ROOM} />)
    expect(screen.getByText(/Confidence: 92%/)).toBeInTheDocument()
  })

  it('renders area in square metres', () => {
    render(<RoomCard room={LIVING_ROOM} />)
    expect(screen.getByText(/Area: 18.5 m²/)).toBeInTheDocument()
  })

  it('renders bounding box coordinates', () => {
    render(<RoomCard room={LIVING_ROOM} />)
    expect(screen.getByText(/0,0 → 300,200/)).toBeInTheDocument()
  })

  it('does not render area when area_sqm is null', () => {
    render(<RoomCard room={UNKNOWN_ROOM} />)
    expect(screen.queryByText(/Area:/)).not.toBeInTheDocument()
  })

  it('renders bedroom label', () => {
    render(<RoomCard room={BEDROOM} />)
    expect(screen.getByText('bedroom')).toBeInTheDocument()
  })

  it('renders correct confidence for bedroom', () => {
    render(<RoomCard room={BEDROOM} />)
    expect(screen.getByText(/Confidence: 88%/)).toBeInTheDocument()
  })
})
