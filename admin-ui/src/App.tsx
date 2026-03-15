import { Navigate, Route, Routes } from 'react-router-dom'
import { isAuthenticated } from './auth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import AppointmentsPage from './pages/AppointmentsPage'
import ConversationsPage from './pages/ConversationsPage'
import ChatPage from './pages/ChatPage'
import SettingsPage from './pages/SettingsPage'
import type { JSX } from 'react'

function ProtectedRoute({ children }: { children: JSX.Element }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return children
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout>
              <DashboardPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/appointments"
        element={
          <ProtectedRoute>
            <Layout>
              <AppointmentsPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/conversations"
        element={
          <ProtectedRoute>
            <Layout>
              <ConversationsPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/conversations/:id"
        element={
          <ProtectedRoute>
            <Layout>
              <ChatPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <Layout>
              <SettingsPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="*"
        element={
          isAuthenticated() ? (
            <Navigate to="/" replace />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  )
}

export default App
