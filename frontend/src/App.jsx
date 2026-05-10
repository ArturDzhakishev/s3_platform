import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard }     from './pages/Dashboard'
import { Clusters }      from './pages/Clusters'
import { ClusterDetail } from './pages/ClusterDetail'
import { Jobs }          from './pages/Jobs'
import { JobDetail }     from './pages/JobDetail'
import { Hosts }         from './pages/Hosts'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/"                      element={<Dashboard />} />
          <Route path="/clusters"              element={<Clusters />} />
          <Route path="/clusters/new"          element={<Clusters />} />
          <Route path="/clusters/:id"          element={<ClusterDetail />} />
          <Route path="/jobs"                  element={<Jobs />} />
          <Route path="/jobs/:id"              element={<JobDetail />} />
          <Route path="/hosts"                 element={<Hosts />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
