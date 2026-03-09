import { Routes, Route } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import JobFeedView from './views/JobFeedView'
import JobDetailView from './views/JobDetailView'
import SuggestionsView from './views/SuggestionsView'
import RadarView from './views/RadarView'
import ProfileView from './views/ProfileView'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<JobFeedView />} />
        <Route path="/radar" element={<RadarView />} />
        <Route path="/profile" element={<ProfileView />} />
        <Route path="/jobs/:id" element={<JobDetailView />} />
        <Route path="/jobs/:id/suggestions" element={<SuggestionsView />} />
      </Routes>
    </AppShell>
  )
}
