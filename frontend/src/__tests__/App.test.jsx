import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'

// Stub out heavy 3D and page components so tests stay fast
vi.mock('../pages/BlueprintStudio', () => ({ default: () => <div data-testid="blueprint-studio">BlueprintStudio</div> }))
vi.mock('../pages/FurnitureCatalog', () => ({ default: () => <div data-testid="furniture-catalog">FurnitureCatalog</div> }))
vi.mock('../pages/DesignStudio',     () => ({ default: () => <div data-testid="design-studio">DesignStudio</div> }))

describe('App', () => {
  it('renders the header with brand name', () => {
    render(<App />)
    expect(screen.getByText('FurnitureAI')).toBeInTheDocument()
  })

  it('renders all navigation tabs', () => {
    render(<App />)
    expect(screen.getByText('Blueprint Studio')).toBeInTheDocument()
    expect(screen.getByText('Furniture Catalog')).toBeInTheDocument()
    expect(screen.getByText('3D Design Studio')).toBeInTheDocument()
  })

  it('shows Blueprint Studio page by default', () => {
    render(<App />)
    expect(screen.getByTestId('blueprint-studio')).toBeInTheDocument()
    expect(screen.queryByTestId('furniture-catalog')).not.toBeInTheDocument()
    expect(screen.queryByTestId('design-studio')).not.toBeInTheDocument()
  })

  it('switches to Furniture Catalog tab on click', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByText('Furniture Catalog'))
    expect(screen.getByTestId('furniture-catalog')).toBeInTheDocument()
    expect(screen.queryByTestId('blueprint-studio')).not.toBeInTheDocument()
  })

  it('switches to 3D Design Studio tab on click', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByText('3D Design Studio'))
    expect(screen.getByTestId('design-studio')).toBeInTheDocument()
    expect(screen.queryByTestId('blueprint-studio')).not.toBeInTheDocument()
  })

  it('renders the footer', () => {
    render(<App />)
    const footer = document.querySelector('footer')
    expect(footer).toBeInTheDocument()
    expect(footer.textContent).toMatch(/FurnitureAI/i)
  })

  it('renders integration badges in header', () => {
    render(<App />)
    expect(screen.getByText('IKEA')).toBeInTheDocument()
    expect(screen.getByText('Alibaba')).toBeInTheDocument()
    expect(screen.getByText('AI Powered')).toBeInTheDocument()
  })
})
