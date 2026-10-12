import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import UniversityNewsPage from './pages/UniversityNewsPage'
import './styles.css'
import './university-site.css'
import './studio-workspace.css'
import './ud-studio.css'
import './workspace-tools.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {window.location.pathname.startsWith('/university-news') ? <UniversityNewsPage /> : <App />}
  </React.StrictMode>,
)
