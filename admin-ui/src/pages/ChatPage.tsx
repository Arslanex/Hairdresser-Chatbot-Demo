import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getUserProfile,
  getMessages,
  sendMessage,
  setTakeover,
  resetSession,
  updateAppointment,
} from '../api'
import type { UserProfile, Message, Booking } from '../api'
import { format, parseISO } from 'date-fns'
import {
  ArrowLeft,
  Bot,
  BotOff,
  Send,
  Loader2,
  RefreshCw,
  Calendar,
  Clock,
  User,
  Users,
  Scissors,
  Phone,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Info,
} from 'lucide-react'

function fmtTime(s: string) {
  try { return format(parseISO(s), 'HH:mm') } catch { return '' }
}
function fmtDate(s: string) {
  try { return format(parseISO(s), 'dd.MM.yyyy HH:mm') } catch { return s }
}
function fmtDateShort(s: string) {
  try { return format(parseISO(s), 'dd.MM.yyyy') } catch { return s }
}
function fmtPrice(n: number) {
  return n ? `${n.toLocaleString('tr-TR')} TL` : '—'
}

const STEP_LABELS: Record<string, string> = {
  select_service: 'Hizmet seçiyor',
  select_location: 'Konum seçiyor',
  select_branch: 'Şube seçiyor',
  get_visit_address: 'Adres giriyor',
  select_staff: 'Sanatçı seçiyor',
  select_date: 'Tarih seçiyor',
  select_time: 'Saat seçiyor',
  get_guest_count: 'Kişi sayısı giriyor',
  get_name: 'İsim giriyor',
  get_phone: 'Telefon giriyor',
  confirm: 'Onay bekliyor',
}

const FLOW_LABELS: Record<string, string> = {
  service: 'Hizmet',
  location_label: 'Konum',
  branch_name: 'Şube',
  visit_address: 'Adres',
  staff_name: 'Sanatçı',
  appointment_date_display: 'Randevu Tarihi',
  appointment_time: 'Randevu Saati',
  guest_count: 'Kişi Sayısı',
  customer_name: 'Müşteri Adı',
  customer_phone: 'Telefon',
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SideCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-xl">
      <div className="px-4 py-3 border-b border-zinc-100">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">{title}</h3>
      </div>
      <div className="px-4 py-3">{children}</div>
    </div>
  )
}

function InfoRow({ icon, label, value, mono = false }: {
  icon: React.ReactNode
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="flex items-start gap-2 py-1 text-xs">
      <span className="text-zinc-300 mt-0.5 shrink-0">{icon}</span>
      <span className="text-zinc-400 shrink-0 w-24">{label}</span>
      <span className={['text-zinc-700 font-medium break-all', mono ? 'font-mono' : ''].join(' ')}>{value}</span>
    </div>
  )
}

function BookingCard({ booking, onCancel, cancelling }: {
  booking: Booking
  onCancel: (id: number) => void
  cancelling: boolean
}) {
  const ok = booking.status === 'confirmed'
  return (
    <div className={['rounded-lg border p-3 text-xs space-y-1', ok ? 'border-emerald-100 bg-emerald-50/50' : 'border-zinc-100 bg-zinc-50 opacity-50'].join(' ')}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-zinc-800 truncate">{booking.service}</span>
        {ok
          ? <span className="shrink-0 flex items-center gap-1 text-emerald-600"><CheckCircle2 size={10} />Onaylı</span>
          : <span className="shrink-0 flex items-center gap-1 text-zinc-400"><XCircle size={10} />İptal edildi</span>
        }
      </div>
      <div className="text-zinc-500 space-y-0.5">
        <div className="flex items-center gap-1"><Calendar size={9} />{booking.appointment_date} {booking.appointment_time}</div>
        <div className="flex items-center gap-1"><Scissors size={9} />{booking.staff_name}</div>
        {booking.guest_count > 1 && (
          <div className="flex items-center gap-1"><Users size={9} />{booking.guest_count} kişi</div>
        )}
        <div className="font-medium text-zinc-700 pt-0.5">{fmtPrice(booking.total_price_tl)}</div>
      </div>
      {ok && (
        <button
          onClick={() => onCancel(booking.id)}
          disabled={cancelling}
          className="w-full mt-1 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 rounded px-2 py-1 transition-colors disabled:opacity-50 border border-red-100"
        >
          {cancelling ? 'İptal ediliyor...' : 'Randevuyu İptal Et'}
        </button>
      )}
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const whatsappId = id ?? ''

  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [togglingTakeover, setTogglingTakeover] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [cancellingId, setCancellingId] = useState<number | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)

  const fetchAll = useCallback(async () => {
    try {
      const [prof, msgs] = await Promise.all([getUserProfile(whatsappId), getMessages(whatsappId)])
      setProfile(prof)
      setMessages(msgs)
      setError('')
    } catch {
      setError('Veriler yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [whatsappId])

  useEffect(() => { void fetchAll() }, [fetchAll])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // When takeover is active, poll for new incoming messages every 5s
  useEffect(() => {
    if (!profile?.session.takeover) return
    const interval = setInterval(async () => {
      try { setMessages(await getMessages(whatsappId)) } catch { /* silent */ }
    }, 5_000)
    return () => clearInterval(interval)
  }, [profile?.session.takeover, whatsappId])

  async function handleTakeover() {
    if (!profile) return
    setTogglingTakeover(true)
    try {
      const current = profile.session.takeover
      await setTakeover(whatsappId, !current)
      setProfile((p) => p ? { ...p, session: { ...p.session, takeover: !current } } : p)
    } catch {
      setError('Devralma ayarı değiştirilemedi.')
    } finally {
      setTogglingTakeover(false)
    }
  }

  async function handleReset() {
    if (!window.confirm('Aktif rezervasyon akışı sıfırlanacak. Müşteri sıfırdan başlamak zorunda kalır. Emin misiniz?')) return
    setResetting(true)
    try {
      await resetSession(whatsappId)
      await fetchAll()
    } catch {
      setError('Oturum sıfırlanamadı.')
    } finally {
      setResetting(false)
    }
  }

  async function handleCancelBooking(bookingId: number) {
    if (!window.confirm('Bu randevuyu iptal etmek istediğinizden emin misiniz?')) return
    setCancellingId(bookingId)
    try {
      await updateAppointment(bookingId, 'cancelled')
      setProfile((p) => p ? {
        ...p,
        bookings: p.bookings.map((b) => b.id === bookingId ? { ...b, status: 'cancelled' } : b),
      } : p)
    } catch {
      setError('Randevu iptal edilemedi.')
    } finally {
      setCancellingId(null)
    }
  }

  async function handleSend() {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    setSending(true)
    try {
      await sendMessage(whatsappId, trimmed)
      setText('')
      setMessages(await getMessages(whatsappId))
    } catch {
      setError('Mesaj gönderilemedi.')
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void handleSend() }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-rose-500" size={24} />
      </div>
    )
  }

  const session = profile?.session
  const takeover = session?.takeover ?? false
  const flowData = session?.flow_data ?? {}

  // Customer name from most recent booking
  const customerName = profile?.bookings?.[0]?.customer_name ?? null

  const flowEntries = Object.entries(FLOW_LABELS)
    .map(([key, label]) => ({ label, value: flowData[key] as string | number | undefined }))
    .filter(({ value }) => value !== undefined && value !== '' && value !== null)

  const confirmedBookings = profile?.bookings.filter((b) => b.status === 'confirmed') ?? []
  const cancelledBookings = profile?.bookings.filter((b) => b.status === 'cancelled') ?? []

  return (
    <div className="flex h-[calc(100vh-112px)] gap-4">

      {/* ── Left panel ─────────────────────────────────────────────────────── */}
      <aside className="w-64 xl:w-72 flex-shrink-0 flex flex-col gap-3 overflow-y-auto pb-2">

        {/* Back + header */}
        <div className="flex items-center gap-2">
          <button onClick={() => navigate('/conversations')} className="text-zinc-400 hover:text-zinc-700 transition-colors">
            <ArrowLeft size={16} />
          </button>
          <div className="flex-1 min-w-0">
            {customerName && (
              <p className="text-sm font-semibold text-zinc-900 truncate">{customerName}</p>
            )}
            <p className="text-xs font-mono text-zinc-400 truncate">{whatsappId}</p>
          </div>
          <button onClick={() => void fetchAll()} className="text-zinc-300 hover:text-rose-500 transition-colors" title="Yenile">
            <RefreshCw size={13} />
          </button>
        </div>

        {error && (
          <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>
        )}

        {/* User info */}
        <SideCard title="Kullanıcı Bilgileri">
          {customerName && (
            <InfoRow icon={<User size={10} />} label="Ad Soyad" value={customerName} />
          )}
          <InfoRow icon={<Phone size={10} />} label="WhatsApp No" value={whatsappId} mono />
          {profile?.booking_phone && profile.booking_phone !== whatsappId && (
            <InfoRow icon={<Phone size={10} />} label="Rezervasyon Tel" value={profile.booking_phone} />
          )}
          <InfoRow icon={<Calendar size={10} />} label="İlk Mesaj" value={fmtDateShort(profile?.created_at ?? '')} />
          <InfoRow icon={<Clock size={10} />} label="Son Görülme" value={fmtDate(profile?.last_seen ?? '')} />
          <InfoRow icon={<User size={10} />} label="Toplam Mesaj" value={`${profile?.message_count ?? 0} mesaj`} />
        </SideCard>

        {/* Session */}
        <SideCard title="Oturum & Bot Kontrolü">
          {/* State badge */}
          <div className="flex items-center gap-2 mb-3">
            <span className={[
              'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium',
              session?.state === 'booking' ? 'bg-orange-50 text-orange-600' : 'bg-zinc-100 text-zinc-500',
            ].join(' ')}>
              {session?.state === 'booking' && <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" />}
              {session?.state === 'booking' ? 'Rezervasyon devam ediyor' : 'Boşta'}
            </span>
          </div>

          {/* Takeover */}
          <div className="border border-zinc-100 rounded-lg p-3 space-y-2">
            <div className="flex items-start gap-2">
              <Info size={11} className="text-zinc-300 mt-0.5 shrink-0" />
              <p className="text-xs text-zinc-400 leading-relaxed">
                {takeover
                  ? 'Bot şu an sessiz. Siz mesaj gönderebilirsiniz. "Serbest Bırak" butonuyla bot tekrar devreye girer.'
                  : 'Bot otomatik yanıt veriyor. "Devral" ile botu durdurabilir, kendiniz mesaj gönderebilirsiniz.'
                }
              </p>
            </div>
            <div className="flex gap-2 pt-1">
              <button
                onClick={() => void handleTakeover()}
                disabled={togglingTakeover}
                className={[
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 flex-1 justify-center',
                  takeover
                    ? 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200'
                    : 'bg-orange-500 text-white hover:bg-orange-600',
                ].join(' ')}
              >
                {takeover ? <><Bot size={11} />Serbest Bırak</> : <><BotOff size={11} />Devral</>}
              </button>

              {session?.state === 'booking' && (
                <button
                  onClick={() => void handleReset()}
                  disabled={resetting}
                  title="Aktif rezervasyon akışını iptal eder, müşteri sıfırdan başlar"
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-50 text-red-600 hover:bg-red-100 transition-colors disabled:opacity-50"
                >
                  {resetting ? <Loader2 size={10} className="animate-spin" /> : <RotateCcw size={10} />}
                  Akışı Sıfırla
                </button>
              )}
            </div>
          </div>

          {/* Current flow step */}
          {session?.flow_step && (
            <div className="mt-2 pt-2 border-t border-zinc-100">
              <p className="text-xs text-zinc-500">
                <span className="font-medium text-zinc-700">Müşteri şu an: </span>
                {STEP_LABELS[session.flow_step] ?? session.flow_step}
              </p>
              {session.last_activity && (
                <p className="text-xs text-zinc-300 mt-0.5">Son aktivite: {fmtDate(session.last_activity)}</p>
              )}
            </div>
          )}
        </SideCard>

        {/* Flow data — what customer has selected so far */}
        {flowEntries.length > 0 && (
          <SideCard title="Müşterinin Seçimleri">
            <p className="text-xs text-zinc-400 mb-2">Rezervasyon akışında şimdiye kadar girdiği bilgiler:</p>
            <div className="space-y-1.5">
              {flowEntries.map(({ label, value }) => (
                <div key={label} className="flex justify-between gap-2 text-xs">
                  <span className="text-zinc-400 shrink-0">{label}</span>
                  <span className="text-zinc-700 font-medium text-right truncate">{String(value)}</span>
                </div>
              ))}
            </div>
          </SideCard>
        )}

        {/* Bookings */}
        <SideCard title={`Randevular (${profile?.bookings.length ?? 0})`}>
          {(profile?.bookings.length ?? 0) === 0 ? (
            <p className="text-xs text-zinc-300">Bu kullanıcının henüz randevusu yok.</p>
          ) : (
            <div className="space-y-2">
              {confirmedBookings.length > 0 && confirmedBookings.map((b) => (
                <BookingCard
                  key={b.id}
                  booking={b}
                  onCancel={(id) => void handleCancelBooking(id)}
                  cancelling={cancellingId === b.id}
                />
              ))}
              {cancelledBookings.length > 0 && (
                <details className="text-xs">
                  <summary className="text-zinc-300 cursor-pointer select-none hover:text-zinc-500 transition-colors">
                    {cancelledBookings.length} iptal edilmiş randevu
                  </summary>
                  <div className="space-y-2 mt-2">
                    {cancelledBookings.map((b) => (
                      <BookingCard
                        key={b.id}
                        booking={b}
                        onCancel={(id) => void handleCancelBooking(id)}
                        cancelling={cancellingId === b.id}
                      />
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}
        </SideCard>
      </aside>

      {/* ── Right panel: messages ───────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 gap-3">

        {/* Takeover banner */}
        {takeover && (
          <div className="bg-orange-50 border border-orange-200 rounded-xl px-4 py-2.5 flex items-center gap-2">
            <BotOff size={14} className="text-orange-500 shrink-0" />
            <div>
              <span className="text-sm font-medium text-orange-800">Bot duraklatıldı</span>
              <span className="text-xs text-orange-600 ml-2">
                Müşteriye otomatik yanıt gönderilmiyor. Aşağıdan mesaj yazabilirsiniz.
              </span>
            </div>
          </div>
        )}

        {/* Message thread */}
        <div className="flex-1 overflow-y-auto bg-white border border-zinc-200 rounded-xl p-4 flex flex-col gap-2.5 min-h-0">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-sm text-zinc-300">
              Henüz mesaj kaydı yok.
            </div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className={['flex flex-col', m.direction === 'out' ? 'items-end' : 'items-start'].join(' ')}>
                <div className={[
                  'max-w-[72%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap',
                  m.direction === 'out'
                    ? 'bg-zinc-900 text-white rounded-br-sm'
                    : 'bg-zinc-100 text-zinc-800 rounded-bl-sm',
                ].join(' ')}>
                  {m.content}
                </div>
                <span className="text-[10px] text-zinc-300 mt-1 px-1">
                  {m.direction === 'out' ? 'Siz · ' : `${customerName ?? 'Müşteri'} · `}
                  {fmtTime(m.created_at)}
                </span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="bg-white border border-zinc-200 rounded-xl p-3 flex items-end gap-2">
          <div className="flex-1">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={takeover ? 'Müşteriye mesaj yazın... (Enter ile gönder, Shift+Enter yeni satır)' : 'Mesaj göndermek için önce "Devral" butonuna tıklayın'}
              rows={2}
              disabled={!takeover}
              className="w-full resize-none border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent disabled:bg-zinc-50 disabled:text-zinc-300 transition"
            />
          </div>
          <button
            onClick={() => void handleSend()}
            disabled={!text.trim() || sending || !takeover}
            className="flex items-center gap-1.5 bg-zinc-900 hover:bg-zinc-700 disabled:opacity-30 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {sending ? <Loader2 className="animate-spin" size={14} /> : <Send size={14} />}
            Gönder
          </button>
        </div>
      </div>
    </div>
  )
}
