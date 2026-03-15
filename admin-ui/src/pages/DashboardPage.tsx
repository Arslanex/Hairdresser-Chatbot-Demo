import { useEffect, useState } from 'react'
import { getDashboard } from '../api'
import type { DashboardData, Booking } from '../api'
import { format, parseISO } from 'date-fns'
import { Loader2 } from 'lucide-react'

function formatDate(s: string) {
  try { return format(parseISO(s), 'dd.MM.yyyy') } catch { return s }
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'confirmed') {
    return <span className="inline-flex px-2 py-0.5 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700">Onaylı</span>
  }
  if (status === 'cancelled') {
    return <span className="inline-flex px-2 py-0.5 rounded-md text-xs font-medium bg-red-50 text-red-600">İptal</span>
  }
  return <span className="inline-flex px-2 py-0.5 rounded-md text-xs font-medium bg-zinc-100 text-zinc-600">{status}</span>
}

function StatCard({ label, value, description }: { label: string; value: number; description: string }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-xl p-5">
      <p className="text-xs font-medium text-zinc-400 uppercase tracking-wider">{label}</p>
      <p className="text-3xl font-semibold text-zinc-900 mt-1.5 tabular-nums">{value}</p>
      <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">{description}</p>
    </div>
  )
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function fetchData() {
    try {
      setData(await getDashboard())
      setError('')
    } catch {
      setError('Veriler yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchData()
    const id = setInterval(() => { void fetchData() }, 30_000)
    return () => clearInterval(id)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-rose-500" size={28} />
      </div>
    )
  }

  if (error || !data) {
    return <p className="text-sm text-zinc-400">{error || 'Veri yok.'}</p>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-zinc-900">Dashboard</h1>
        <p className="text-sm text-zinc-400 mt-0.5">Her 30 saniyede otomatik güncellenir</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          label="Bugünkü Randevular"
          value={data.today_bookings}
          description="Bugün onaylanmış randevu sayısı"
        />
        <StatCard
          label="Toplam Onaylı"
          value={data.total_confirmed}
          description="Tüm zamanlarda onaylanmış randevu"
        />
        <StatCard
          label="İptal Edilen"
          value={data.total_cancelled}
          description="İptal edilmiş veya vazgeçilmiş randevu"
        />
        <StatCard
          label="Aktif Konuşmalar"
          value={data.active_sessions}
          description="Şu an rezervasyon akışında olan kullanıcı"
        />
        <StatCard
          label="Bot Devre Dışı"
          value={data.takeover_active}
          description="Admin devralma açık olan kullanıcı sayısı"
        />
        <StatCard
          label="Toplam Kullanıcı"
          value={data.total_users}
          description="Sisteme kayıtlı WhatsApp kullanıcısı"
        />
      </div>

      {/* Recent bookings */}
      <div className="bg-white border border-zinc-200 rounded-xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-zinc-100">
          <h2 className="text-sm font-semibold text-zinc-900">Son Onaylı Randevular</h2>
          <p className="text-xs text-zinc-400 mt-0.5">En son oluşturulmuş 8 onaylı randevu</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-100">
                <th className="px-5 py-2.5 text-left text-xs font-medium text-zinc-400">Tarih & Saat</th>
                <th className="px-5 py-2.5 text-left text-xs font-medium text-zinc-400">Müşteri Adı</th>
                <th className="px-5 py-2.5 text-left text-xs font-medium text-zinc-400">Hizmet</th>
                <th className="px-5 py-2.5 text-left text-xs font-medium text-zinc-400">Sanatçı</th>
                <th className="px-5 py-2.5 text-left text-xs font-medium text-zinc-400">Durum</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_bookings.slice(0, 8).map((b: Booking) => (
                <tr key={b.id} className="border-b border-zinc-50 hover:bg-zinc-50 transition-colors">
                  <td className="px-5 py-3 text-sm text-zinc-500">
                    {formatDate(b.appointment_date)}
                    <span className="ml-2 text-zinc-400">{b.appointment_time}</span>
                  </td>
                  <td className="px-5 py-3 text-sm font-medium text-zinc-900">{b.customer_name}</td>
                  <td className="px-5 py-3 text-sm text-zinc-500">{b.service}</td>
                  <td className="px-5 py-3 text-sm text-zinc-500">{b.staff_name}</td>
                  <td className="px-5 py-3"><StatusBadge status={b.status} /></td>
                </tr>
              ))}
              {data.recent_bookings.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-sm text-zinc-300">
                    Henüz onaylı randevu yok.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
