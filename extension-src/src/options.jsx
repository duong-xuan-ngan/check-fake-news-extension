import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import OptionsApp from './components/OptionsApp.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <OptionsApp />
  </StrictMode>
)
