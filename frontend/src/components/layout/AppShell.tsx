import { ReactNode } from 'react'
import { Link } from 'react-router-dom'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <div>
      <nav>
        <Link to="/">Job Feed</Link>
        <Link to="/radar">Radar</Link>
        <Link to="/profile">Profile</Link>
      </nav>
      <main>{children}</main>
    </div>
  )
}
