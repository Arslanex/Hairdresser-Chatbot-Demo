import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getConversations, setTakeover } from '../api'
import type { Conversation } from '../api'
import { format, parseISO } from 'date-fns'
import { Loader2, MessageSquare, BotOff, Bot } from 'lucide-react'

function formatDate(s: string) {
  try { return format(parseISO(s), 'dd.MM HH:mm') } catch { return s }
}

function truncate(s: string, n: number) {
  return s.length <= n ? s : s.slice(0, n) + '…'
}

function initials(name: string | null, fallback: string): string {
  if (!name) return fallback.slice(-2)
  const parts = name.trim().split(' ')
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return parts[0].slice(0, 2).toUpperCase()
}

export default function ConversationsPage() {
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [togglingId, setTogglingId] = useState<string | null>(null)

  async function fetchData() {
    try {
      setConversations(await getConversations())
      setError('')
    } catch {
      setError('Konuşmalar yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void fetchData() }, [])

  async function handleTakeover(id: string, current: boolean) {
    setTogglingId(id)
    try {
      await setTakeover(id, !current)
      setConversations((prev) =>
        prev.map((c) => c.whatsapp_id === id ? { ...c, takeover: !current } : c)
      )
    } catch {
      setError('Ayar değiştirilemedi.')
    } finally {
      setTogglingId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-rose-500" size={24} />
      </div>
    )
  }

  const activeCount = conversations.filter((c) => c.state === 'booking').length
  const takeoverCount = conversations.filter((c) => c.takeover).length

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-zinc-900">Mesajlar</h1>
        <p className="text-sm text-zinc-400 mt-0.5">
          {conversations.length} kullanıcı
          {activeCount > 0 && <span className="ml-2 text-orange-500">· {activeCount} aktif rezervasyon</span>}
          {takeoverCount > 0 && <span className="ml-2 text-rose-500">· {takeoverCount} bot devre dışı</span>}
        </p>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {/* Takeover info banner */}
      <div className="bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 flex items-start gap-3 text-xs text-zinc-500">
        <BotOff size={14} className="text-zinc-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-medium text-zinc-700">Bot Devral nedir?</span>
          {' '}Açık olduğunda bot o kullanıcıya otomatik yanıt vermez.
          Siz doğrudan WhatsApp'tan mesaj yazabilirsiniz.
          Kapattığınızda bot yeniden devreye girer.
        </div>
      </div>

      <div className="bg-white border border-zinc-200 rounded-xl overflow-hidden">
        {conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-16 text-zinc-300">
            <MessageSquare size={28} />
            <p className="text-sm">Henüz konuşma yok.</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {/* Header row */}
            <div className="hidden md:grid grid-cols-[auto_1fr_auto_auto_auto] gap-4 items-center px-5 py-2 bg-zinc-50">
              <div className="w-8" />
              <span className="text-xs font-medium text-zinc-400">Kullanıcı</span>
              <span className="text-xs font-medium text-zinc-400 w-24 text-right">Son Mesaj</span>
              <span className="text-xs font-medium text-zinc-400 w-16 text-center">Durum</span>
              <span className="text-xs font-medium text-zinc-400 w-16 text-center">Bot</span>
            </div>

            {conversations.map((c) => (
              <div
                key={c.whatsapp_id}
                onClick={() => navigate(`/conversations/${c.whatsapp_id}`)}
                className="flex items-center gap-4 px-5 py-3.5 hover:bg-zinc-50 transition-colors cursor-pointer"
              >
                {/* Avatar */}
                <div className={[
                  'w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold',
                  c.takeover ? 'bg-orange-100 text-orange-600' : 'bg-zinc-100 text-zinc-500',
                ].join(' ')}>
                  {initials(c.customer_name, c.whatsapp_id)}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-zinc-900">
                      {c.customer_name ?? <span className="text-zinc-400 font-normal">İsimsiz</span>}
                    </span>
                    <span className="text-xs text-zinc-300 font-mono">{c.whatsapp_id}</span>
                    {c.state === 'booking' && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-orange-50 text-orange-600">
                        <span className="w-1 h-1 rounded-full bg-orange-500 animate-pulse" />
                        Rezervasyon akışında
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-400 truncate mt-0.5">
                    {c.last_message ? truncate(c.last_message, 70) : <span className="italic">Mesaj yok</span>}
                  </p>
                </div>

                {/* Meta */}
                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-right hidden sm:block w-24">
                    <p className="text-xs text-zinc-400">{formatDate(c.last_message_at)}</p>
                    <p className="text-xs text-zinc-300 mt-0.5">{c.message_count} mesaj</p>
                  </div>

                  {/* Takeover toggle */}
                  <div
                    className="flex flex-col items-center gap-0.5 w-16"
                    onClick={(e) => e.stopPropagation()}
                    title={c.takeover ? 'Bot devre dışı — tıkla yeniden etkinleştir' : 'Bot aktif — tıkla devre dışı bırak'}
                  >
                    <button
                      onClick={() => void handleTakeover(c.whatsapp_id, c.takeover)}
                      disabled={togglingId === c.whatsapp_id}
                      className={[
                        'relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none disabled:opacity-50',
                        c.takeover ? 'bg-rose-500' : 'bg-zinc-200',
                      ].join(' ')}
                    >
                      <span className={[
                        'inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform',
                        c.takeover ? 'translate-x-4' : 'translate-x-0.5',
                      ].join(' ')} />
                    </button>
                    <span className="text-[10px] text-zinc-300 flex items-center gap-0.5">
                      {c.takeover ? <><BotOff size={8} />Devralındı</> : <><Bot size={8} />Aktif</>}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
