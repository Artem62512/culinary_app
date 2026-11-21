import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'
import { Toaster } from '@/components/ui/sonner'
import { FlyingCartProvider } from '@/components/FlyingCartContext'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <FlyingCartProvider>
        <App />
        <Toaster position="top-center" />
      </FlyingCartProvider>
    </QueryClientProvider>
  </StrictMode>,
)
