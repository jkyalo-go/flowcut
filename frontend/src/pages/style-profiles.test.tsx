import { render, screen, waitFor } from '@testing-library/react'
import StyleProfilesPage from '@pages/style-profiles'
import { vi, beforeEach } from 'vitest'
import * as apiModule from '@/lib/api'

vi.mock('next/router', () => ({
  useRouter: () => ({ pathname: '/style-profiles', replace: vi.fn() }),
}))

describe('StyleProfilesPage', () => {
  beforeEach(() => {
    vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
      if (path.includes('genres')) return Promise.resolve(['gaming', 'education'])
      return Promise.resolve([
        { id: 'p1', name: 'My Profile', genre: 'gaming', version: 3,
          dimension_locks: {}, confidence_scores: {}, style_doc: '' }
      ])
    })
  })

  it('renders profiles after load', async () => {
    render(<StyleProfilesPage />)
    await waitFor(() => expect(screen.getByText('My Profile')).toBeInTheDocument())
  })

  it('renders new profile form', async () => {
    render(<StyleProfilesPage />)
    await waitFor(() => expect(screen.getByText(/new profile/i)).toBeInTheDocument())
  })
})
