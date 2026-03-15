import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Scissors } from 'lucide-react'
import { login } from '../api'
import { setToken } from '../auth'

export default function LoginPage() {
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login(password)
      setToken(data.token)
      navigate('/')
    } catch {
      setError('Hatalı şifre.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 flex items-center justify-center p-4">
      <div className="w-full max-w-[340px]">
        {/* Brand */}
        <div className="flex flex-col items-center mb-8">
          <div className="flex items-center justify-center w-10 h-10 bg-rose-500 rounded-xl mb-4">
            <Scissors size={18} className="text-white" />
          </div>
          <h1 className="text-xl font-semibold text-zinc-900">İzellik Admin</h1>
          <p className="text-sm text-zinc-400 mt-1">Yönetim Paneline Giriş</p>
        </div>

        {/* Card */}
        <div className="bg-white border border-zinc-200 rounded-2xl p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label htmlFor="password" className="block text-xs font-medium text-zinc-600 mb-1.5">
                Şifre
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoFocus
                placeholder="••••••••"
                className="w-full px-3 py-2.5 border border-zinc-200 rounded-lg text-sm text-zinc-900 placeholder:text-zinc-300 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent transition"
              />
            </div>

            {error && (
              <p className="text-xs text-red-500">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-rose-500 hover:bg-rose-600 disabled:opacity-60 text-white font-medium text-sm py-2.5 px-4 rounded-lg transition-colors"
            >
              {loading ? 'Giriş yapılıyor...' : 'Giriş Yap'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
