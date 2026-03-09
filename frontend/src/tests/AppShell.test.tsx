/**
 * Phase 1 — AppShell layout tests.
 *
 * Verifies that the sidebar navigation renders all 3 primary links and
 * passes children through to the main content area.
 * All tests fail until AppShell is implemented.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'

describe('AppShell — Phase 1 scaffold', () => {
  it('renders navigation links for all primary routes', () => {
    render(
      <MemoryRouter>
        <AppShell>
          <div>content</div>
        </AppShell>
      </MemoryRouter>
    )
    expect(screen.getByRole('link', { name: /job feed/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /radar/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /profile/i })).toBeInTheDocument()
  })

  it('renders children in the main content area', () => {
    render(
      <MemoryRouter>
        <AppShell>
          <div data-testid="test-content">hello</div>
        </AppShell>
      </MemoryRouter>
    )
    expect(screen.getByTestId('test-content')).toBeInTheDocument()
  })
})
