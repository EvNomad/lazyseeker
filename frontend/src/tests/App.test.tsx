/**
 * Phase 1 — App routing tests.
 *
 * Verifies that all 5 routes render their placeholder headings.
 * All tests fail with a module-not-found error until the Vite scaffold
 * (App.tsx + view placeholders) is implemented.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'

describe('App routing — Phase 1 scaffold', () => {
  it('renders Job Feed view at /', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    )
    expect(screen.getByRole('heading', { name: /job feed/i })).toBeInTheDocument()
  })

  it('renders Radar view at /radar', () => {
    render(
      <MemoryRouter initialEntries={['/radar']}>
        <App />
      </MemoryRouter>
    )
    expect(screen.getByRole('heading', { name: /radar/i })).toBeInTheDocument()
  })

  it('renders Profile view at /profile', () => {
    render(
      <MemoryRouter initialEntries={['/profile']}>
        <App />
      </MemoryRouter>
    )
    expect(screen.getByRole('heading', { name: /profile/i })).toBeInTheDocument()
  })

  it('renders Job Detail view at /jobs/:id', () => {
    render(
      <MemoryRouter initialEntries={['/jobs/test-job-id']}>
        <App />
      </MemoryRouter>
    )
    expect(screen.getByRole('heading', { name: /job detail/i })).toBeInTheDocument()
  })

  it('renders Suggestions view at /jobs/:id/suggestions', () => {
    render(
      <MemoryRouter initialEntries={['/jobs/test-job-id/suggestions']}>
        <App />
      </MemoryRouter>
    )
    expect(screen.getByRole('heading', { name: /suggestions/i })).toBeInTheDocument()
  })
})
