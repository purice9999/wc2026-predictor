import { Outlet } from 'react-router-dom'
import Navbar from './Navbar.jsx'

export default function Layout() {
  return (
    <div className="min-h-screen bg-navy-950 flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-navy-700 py-4 text-center text-xs text-gray-500">
        WC 2026 Predictor — proiect educațional de statistică. Nu este un instrument de pariuri.
      </footer>
    </div>
  )
}
