import { useEffect, useState, useCallback } from 'react'
import { getAppointments, updateAppointment } from '../api'
import type { Booking } from '../api'
import { format, parseISO } from 'date-fns'
import { Loader2, ChevronLeft, ChevronRight, SlidersHorizontal, X } from 'lucide-react'

const PAGE_SIZE = 50

function formatDate(s: string) {
  try { return format(parseISO(s), 'dd.MM.yyyy') } catch { return s }
}

function formatPrice(n: number) {
  return n ? n.toLocaleString('tr-TR') + ' TL' : '—'
}

function locationLabel(t: string) {
  if (t === 'studio') return 'Stüdyo'
  if (t === 'hotel') return 'Otel'
  if (t === 'out_of_city') return 'Şehir Dışı'
  return t
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

export default function AppointmentsPage() {
  const [items, setItems] = useState<Booking[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  const [dateFilter, setDateFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [staffFilter, setStaffFilter] = useState('')

  const hasFilters = dateFilter || statusFilter || staffFilter

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await getAppointments({
        date: dateFilter || undefined,
        status: statusFilter || undefined,
        staff: staffFilter || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      setItems(result.items)
      setTotal(result.total)
    } catch {
      setError('Randevular yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [dateFilter, statusFilter, staffFilter, page])

  useEffect(() => { void fetchData() }, [fetchData])

  async function handleCancel(id: number) {
    setActionLoading(id)
    try {
      await updateAppointment(id, 'cancelled')
      await fetchData()
    } catch {
      setError('İşlem başarısız oldu.')
    } finally {
      setActionLoading(null)
    }
  }

  function clearFilters() {
    setDateFilter('')
    setStatusFilter('')
    setStaffFilter('')
    setPage(0)
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-zinc-900">Randevular</h1>
        <p className="text-sm text-zinc-400 mt-0.5">{total} kayıt</p>
      </div>

      {/* Filters */}
      <div className="bg-white border border-zinc-200 rounded-xl px-4 py-3 flex flex-wrap items-center gap-2">
        <SlidersHorizontal size={14} className="text-zinc-400 shrink-0" />
        <input
          type="date"
          value={dateFilter}
          onChange={(e) => { setDateFilter(e.target.value); setPage(0) }}
          className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm text-zinc-700 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent"
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(0) }}
          className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm text-zinc-700 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent"
        >
          <option value="">Tüm durumlar</option>
          <option value="confirmed">Onaylı</option>
          <option value="cancelled">İptal</option>
        </select>
        <input
          type="text"
          placeholder="Sanatçı ara..."
          value={staffFilter}
          onChange={(e) => { setStaffFilter(e.target.value); setPage(0) }}
          className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm text-zinc-700 placeholder:text-zinc-300 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent min-w-[160px]"
        />
        {hasFilters && (
          <button onClick={clearFilters} className="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-600 transition-colors">
            <X size={12} />Temizle
          </button>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}

      {/* Table */}
      <div className="bg-white border border-zinc-200 rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="animate-spin text-rose-500" size={24} />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-100">
                  {['#', 'Müşteri', 'Telefon', 'Hizmet', 'Sanatçı', 'Tarih', 'Saat', 'Konum', 'Kişi', 'Tutar', 'Durum', ''].map((h, i) => (
                    <th key={i} className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((b) => (
                  <tr key={b.id} className="border-b border-zinc-50 hover:bg-zinc-50 transition-colors">
                    <td className="px-4 py-3 text-xs text-zinc-300">{b.id}</td>
                    <td className="px-4 py-3 text-sm font-medium text-zinc-900 whitespace-nowrap">{b.customer_name}</td>
                    <td className="px-4 py-3 text-sm text-zinc-500 whitespace-nowrap">{b.customer_phone}</td>
                    <td className="px-4 py-3 text-sm text-zinc-600">{b.service}</td>
                    <td className="px-4 py-3 text-sm text-zinc-600 whitespace-nowrap">{b.staff_name}</td>
                    <td className="px-4 py-3 text-sm text-zinc-600 whitespace-nowrap">{formatDate(b.appointment_date)}</td>
                    <td className="px-4 py-3 text-sm text-zinc-600">{b.appointment_time}</td>
                    <td className="px-4 py-3 text-sm text-zinc-600 whitespace-nowrap">{locationLabel(b.location_type)}</td>
                    <td className="px-4 py-3 text-sm text-zinc-600 text-center">{b.guest_count}</td>
                    <td className="px-4 py-3 text-sm text-zinc-600 text-right whitespace-nowrap">{formatPrice(b.total_price_tl)}</td>
                    <td className="px-4 py-3"><StatusBadge status={b.status} /></td>
                    <td className="px-4 py-3">
                      {b.status === 'confirmed' && (
                        <button
                          onClick={() => void handleCancel(b.id)}
                          disabled={actionLoading === b.id}
                          className="text-xs text-zinc-400 hover:text-red-500 transition-colors disabled:opacity-40 whitespace-nowrap"
                        >
                          {actionLoading === b.id ? '...' : 'İptal Et'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={12} className="px-4 py-12 text-center text-sm text-zinc-300">
                      Randevu bulunamadı.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-400">
          Sayfa {page + 1} / {totalPages}
        </span>
        <div className="flex gap-1">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="flex items-center gap-1 px-3 py-1.5 text-xs text-zinc-500 border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-30 transition-colors"
          >
            <ChevronLeft size={14} /> Önceki
          </button>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="flex items-center gap-1 px-3 py-1.5 text-xs text-zinc-500 border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-30 transition-colors"
          >
            Sonraki <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
