import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import FurnitureCard from '../components/FurnitureCard'

const IKEA_PRODUCT = {
  item_id: 'ikea-kivik-sofa',
  name: 'KIVIK Sofa',
  category: 'sofa',
  source: 'ikea',
  price: 799.0,
  currency: 'USD',
  image_url: null,
  buy_url: 'https://www.ikea.com/us/en/p/kivik-sofa/',
  description: 'A generous seating series with a soft, deep seat.',
  dimensions: { w: 228, d: 95, h: 83, unit: 'cm' },
  colors: ['beige', 'grey', 'dark blue'],
  styles: ['modern', 'scandinavian'],
  rating: 4.6,
  reviews: 1842,
  in_stock: true,
}

const ALIBABA_PRODUCT = {
  item_id: 'ali-nordic-sofa',
  name: 'Nordic Fabric Sofa',
  category: 'sofa',
  source: 'alibaba',
  price: 320.0,
  currency: 'USD',
  image_url: null,
  buy_url: 'https://www.alibaba.com/product-detail/Nordic-Sofa.html',
  description: 'Wholesale Nordic-style 3-seater fabric sofa.',
  dimensions: { w: 210, d: 85, h: 80, unit: 'cm' },
  colors: ['light grey', 'dark grey'],
  styles: ['nordic', 'modern'],
  rating: 4.3,
  reviews: 456,
  in_stock: true,
}

describe('FurnitureCard', () => {
  it('renders product name', () => {
    render(<FurnitureCard item={IKEA_PRODUCT} />)
    expect(screen.getByText('KIVIK Sofa')).toBeInTheDocument()
  })

  it('renders IKEA source badge', () => {
    render(<FurnitureCard item={IKEA_PRODUCT} />)
    expect(screen.getByText('🔵 IKEA')).toBeInTheDocument()
  })

  it('renders Alibaba source badge', () => {
    render(<FurnitureCard item={ALIBABA_PRODUCT} />)
    expect(screen.getByText('🟠 Alibaba')).toBeInTheDocument()
  })

  it('renders product price', () => {
    render(<FurnitureCard item={IKEA_PRODUCT} />)
    expect(screen.getByText(/799/)).toBeInTheDocument()
  })

  it('renders product description', () => {
    render(<FurnitureCard item={IKEA_PRODUCT} />)
    expect(screen.getByText(/generous seating/i)).toBeInTheDocument()
  })

  it('renders category label', () => {
    render(<FurnitureCard item={IKEA_PRODUCT} />)
    expect(screen.getByText('sofa')).toBeInTheDocument()
  })

  it('renders color chips', () => {
    render(<FurnitureCard item={IKEA_PRODUCT} />)
    expect(screen.getByText('beige')).toBeInTheDocument()
    expect(screen.getByText('grey')).toBeInTheDocument()
  })

  it('renders dimensions', () => {
    render(<FurnitureCard item={IKEA_PRODUCT} />)
    expect(screen.getByText(/228×95×83 cm/)).toBeInTheDocument()
  })

  it('renders buy link pointing to the correct URL', () => {
    render(<FurnitureCard item={IKEA_PRODUCT} />)
    const link = screen.getByRole('link', { name: /Buy at IKEA/i })
    expect(link).toHaveAttribute('href', IKEA_PRODUCT.buy_url)
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders Buy on Alibaba link for alibaba source', () => {
    render(<FurnitureCard item={ALIBABA_PRODUCT} />)
    const link = screen.getByRole('link', { name: /Buy on Alibaba/i })
    expect(link).toHaveAttribute('href', ALIBABA_PRODUCT.buy_url)
  })

  it('renders recommendation score badge when score is provided', () => {
    const rec = { product: IKEA_PRODUCT, score: 0.87, reason: 'Great modern match' }
    render(<FurnitureCard item={rec} />)
    expect(screen.getByText('87%')).toBeInTheDocument()
  })

  it('renders recommendation reason when provided', () => {
    const rec = { product: IKEA_PRODUCT, score: 0.87, reason: 'Great modern match' }
    render(<FurnitureCard item={rec} />)
    expect(screen.getByText(/Great modern match/)).toBeInTheDocument()
  })

  it('renders "Out of Stock" overlay when in_stock is false', () => {
    render(<FurnitureCard item={{ ...IKEA_PRODUCT, in_stock: false }} />)
    expect(screen.getByText('Out of Stock')).toBeInTheDocument()
  })

  it('renders "Price on request" when price is null', () => {
    render(<FurnitureCard item={{ ...IKEA_PRODUCT, price: null }} />)
    expect(screen.getByText('Price on request')).toBeInTheDocument()
  })

  it('returns null when no product is provided', () => {
    const { container } = render(<FurnitureCard item={null} />)
    expect(container.firstChild).toBeNull()
  })
})
