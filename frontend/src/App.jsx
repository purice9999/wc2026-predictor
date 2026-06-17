import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import GroupStage from './pages/GroupStage.jsx'
import MatchDetail from './pages/MatchDetail.jsx'
import History from './pages/History.jsx'
import BettingSlip from './pages/BettingSlip.jsx'
import Bracket from './pages/Bracket.jsx'
import ModelIntel from './pages/ModelIntel.jsx'
import LiveTracking from './pages/LiveTracking.jsx'

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'groups', element: <GroupStage /> },
      { path: 'groups/:groupId', element: <GroupStage /> },
      { path: 'match/:matchId', element: <MatchDetail /> },
      { path: 'bracket', element: <Bracket /> },
      { path: 'history', element: <History /> },
      { path: 'slip', element: <BettingSlip /> },
      { path: 'model', element: <ModelIntel /> },
      { path: 'tracking', element: <LiveTracking /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
