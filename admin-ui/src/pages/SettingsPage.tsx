import { useEffect, useState, useCallback } from 'react'
import { Check, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import {
  getSettings,
  updateSetting,
  getPromptSections,
  updatePromptSection,
  resetPromptSection,
  type PromptSection,
} from '../api'

// ─── Types ────────────────────────────────────────────────────────────────────

interface FieldState {
  value: string
  saving: boolean
  saved: boolean
}
type SettingsState = Record<string, FieldState>

interface SectionState {
  value: string
  is_default: boolean
  saving: boolean
  savedOk: boolean
  resetting: boolean
  error: string
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SETTING_KEYS = [
  'business_name',
  'business_phone',
  'business_address',
  'working_hours_start',
  'working_hours_end',
  'bot_enabled',
  'welcome_message',
]

const LABELS: Record<string, string> = {
  business_name: 'İşletme Adı',
  business_phone: 'İşletme Telefonu',
  business_address: 'İşletme Adresi',
  working_hours_start: 'Açılış Saati',
  working_hours_end: 'Kapanış Saati',
  bot_enabled: 'Bot Durumu',
  welcome_message: 'Karşılama Mesajı',
}

type Tab = 'genel' | 'prompt'

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>('genel')

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-zinc-900">Ayarlar</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-zinc-200 mb-6">
        {(['genel', 'prompt'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={[
              'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors capitalize',
              tab === t
                ? 'border-zinc-900 text-zinc-900'
                : 'border-transparent text-zinc-400 hover:text-zinc-600',
            ].join(' ')}
          >
            {t === 'genel' ? 'Genel' : 'Prompt'}
          </button>
        ))}
      </div>

      {tab === 'genel' ? <GeneralTab /> : <PromptTab />}
    </div>
  )
}

// ─── General Tab ──────────────────────────────────────────────────────────────

function GeneralTab() {
  const [settings, setSettings] = useState<SettingsState>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const initState = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getSettings()
      const state: SettingsState = {}
      SETTING_KEYS.forEach((key) => {
        state[key] = { value: data[key] ?? '', saving: false, saved: false }
      })
      setSettings(state)
    } catch {
      setError('Ayarlar yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void initState() }, [initState])

  function handleChange(key: string, value: string) {
    setSettings((prev) => ({ ...prev, [key]: { ...prev[key], value, saved: false } }))
  }

  async function handleSave(key: string) {
    setSettings((prev) => ({ ...prev, [key]: { ...prev[key], saving: true } }))
    try {
      await updateSetting(key, settings[key].value)
      setSettings((prev) => ({ ...prev, [key]: { ...prev[key], saving: false, saved: true } }))
      setTimeout(() => setSettings((prev) => ({ ...prev, [key]: { ...prev[key], saved: false } })), 2000)
    } catch {
      setSettings((prev) => ({ ...prev, [key]: { ...prev[key], saving: false } }))
      setError(`"${LABELS[key]}" kaydedilemedi.`)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="animate-spin text-rose-500" size={24} />
      </div>
    )
  }

  function renderField(key: string) {
    const field = settings[key]
    if (!field) return null
    const label = LABELS[key]

    if (key === 'bot_enabled') {
      const enabled = field.value === 'true' || field.value === '1'
      return (
        <div key={key} className="flex items-center justify-between py-2">
          <div>
            <p className="text-sm font-medium text-zinc-700">{label}</p>
            <p className="text-xs text-zinc-400 mt-0.5">Otomatik yanıtlar</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                handleChange(key, enabled ? 'false' : 'true')
                setTimeout(() => void handleSave(key), 0)
              }}
              className={[
                'relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none',
                enabled ? 'bg-rose-500' : 'bg-zinc-200',
              ].join(' ')}
            >
              <span className={[
                'inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform',
                enabled ? 'translate-x-4' : 'translate-x-0.5',
              ].join(' ')} />
            </button>
            {field.saved && (
              <span className="text-xs text-emerald-600 flex items-center gap-1">
                <Check size={11} />Kaydedildi
              </span>
            )}
          </div>
        </div>
      )
    }

    if (key === 'welcome_message') {
      return (
        <div key={key} className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">{label}</label>
          <div className="flex gap-2 items-start">
            <textarea
              value={field.value}
              onChange={(e) => handleChange(key, e.target.value)}
              rows={4}
              className="flex-1 border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent resize-y text-zinc-700"
            />
            <InlineSave saving={field.saving} saved={field.saved} onSave={() => void handleSave(key)} />
          </div>
        </div>
      )
    }

    if (key === 'working_hours_start' || key === 'working_hours_end') {
      return (
        <div key={key} className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">{label} <span className="text-zinc-400 font-normal">(0–23)</span></label>
          <div className="flex gap-2 items-center">
            <input
              type="number" min={0} max={23}
              value={field.value}
              onChange={(e) => handleChange(key, e.target.value)}
              className="w-20 border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent text-zinc-700"
            />
            <InlineSave saving={field.saving} saved={field.saved} onSave={() => void handleSave(key)} />
          </div>
        </div>
      )
    }

    return (
      <div key={key} className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-zinc-700">{label}</label>
        <div className="flex gap-2 items-center">
          <input
            type="text"
            value={field.value}
            onChange={(e) => handleChange(key, e.target.value)}
            className="flex-1 border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent text-zinc-700"
          />
          <InlineSave saving={field.saving} saved={field.saved} onSave={() => void handleSave(key)} />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-red-500">{error}</p>}

      <SettingsSection title="İşletme Bilgileri">
        {['business_name', 'business_phone', 'business_address'].map(renderField)}
      </SettingsSection>

      <SettingsSection title="Çalışma Saatleri">
        <div className="flex flex-wrap gap-6">
          {['working_hours_start', 'working_hours_end'].map(renderField)}
        </div>
      </SettingsSection>

      <SettingsSection title="Bot Durumu">
        {renderField('bot_enabled')}
      </SettingsSection>

      <SettingsSection title="Karşılama Mesajı">
        {renderField('welcome_message')}
      </SettingsSection>
    </div>
  )
}

// ─── Prompt Tab ───────────────────────────────────────────────────────────────

function PromptTab() {
  const [sections, setSections] = useState<PromptSection[]>([])
  const [assembled, setAssembled] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [sectionStates, setSectionStates] = useState<Record<string, SectionState>>({})

  useEffect(() => {
    setLoading(true)
    getPromptSections()
      .then((data) => {
        setSections(data.sections)
        setAssembled(data.assembled)
        const states: Record<string, SectionState> = {}
        for (const s of data.sections) {
          states[s.key] = { value: s.value, is_default: s.is_default, saving: false, savedOk: false, resetting: false, error: '' }
        }
        setSectionStates(states)
      })
      .catch(() => setLoadError('Prompt bölümleri yüklenemedi.'))
      .finally(() => setLoading(false))
  }, [])

  function patch(key: string, update: Partial<SectionState>) {
    setSectionStates((prev) => ({ ...prev, [key]: { ...prev[key], ...update } }))
  }

  async function handleSave(key: string) {
    patch(key, { saving: true, error: '', savedOk: false })
    try {
      await updatePromptSection(key, sectionStates[key].value)
      patch(key, { saving: false, savedOk: true, is_default: false })
      setTimeout(() => patch(key, { savedOk: false }), 2000)
      getPromptSections().then((d) => setAssembled(d.assembled)).catch(() => {})
    } catch {
      patch(key, { saving: false, error: 'Kaydedilemedi.' })
    }
  }

  async function handleReset(key: string) {
    patch(key, { resetting: true, error: '' })
    try {
      const result = await resetPromptSection(key)
      patch(key, { resetting: false, value: result.value, is_default: result.is_default })
      getPromptSections().then((d) => setAssembled(d.assembled)).catch(() => {})
    } catch {
      patch(key, { resetting: false, error: 'Sıfırlanamadı.' })
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="animate-spin text-rose-500" size={24} />
      </div>
    )
  }

  if (loadError) {
    return <p className="text-sm text-red-500">{loadError}</p>
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400">
        Bot talimatlarını bölüm bölüm düzenleyin. Tüm bölümler birleştirilerek tek bir sistem prompt'u oluşturulur.
      </p>

      {sections.map((section) => {
        const state = sectionStates[section.key]
        if (!state) return null
        return (
          <div key={section.key} className="bg-white border border-zinc-200 rounded-xl p-5">
            <div className="flex items-start justify-between mb-3 gap-4">
              <div>
                <h3 className="text-sm font-semibold text-zinc-900">{section.label}</h3>
                <p className="text-xs text-zinc-400 mt-0.5">{section.description}</p>
              </div>
              <span className={[
                'shrink-0 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium',
                state.is_default ? 'bg-zinc-100 text-zinc-400' : 'bg-rose-50 text-rose-600',
              ].join(' ')}>
                {state.is_default ? 'Varsayılan' : 'Özelleştirilmiş'}
              </span>
            </div>

            <textarea
              rows={10}
              className="w-full font-mono text-xs border border-zinc-200 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent resize-y text-zinc-700"
              value={state.value}
              onChange={(e) => setSectionStates((prev) => ({
                ...prev,
                [section.key]: { ...prev[section.key], value: e.target.value, savedOk: false },
              }))}
              disabled={state.saving || state.resetting}
            />

            <div className="flex items-center gap-2 mt-3">
              <button
                onClick={() => void handleSave(section.key)}
                disabled={state.saving || state.resetting}
                className="bg-zinc-900 hover:bg-zinc-700 text-white text-xs px-3.5 py-2 rounded-lg font-medium disabled:opacity-50 transition-colors flex items-center gap-1.5"
              >
                {state.saving && <Loader2 className="animate-spin" size={11} />}
                {state.savedOk ? '✓ Kaydedildi' : 'Kaydet'}
              </button>
              <button
                onClick={() => void handleReset(section.key)}
                disabled={state.is_default || state.saving || state.resetting}
                className="border border-zinc-200 text-zinc-500 hover:bg-zinc-50 text-xs px-3.5 py-2 rounded-lg disabled:opacity-30 transition-colors"
              >
                {state.resetting ? 'Sıfırlanıyor...' : 'Varsayılana Sıfırla'}
              </button>
              {state.error && <span className="text-xs text-red-500">{state.error}</span>}
            </div>
          </div>
        )
      })}

      {/* Assembled preview */}
      <div className="bg-white border border-zinc-200 rounded-xl p-5">
        <button
          onClick={() => setPreviewOpen((v) => !v)}
          className="flex items-center justify-between w-full text-left"
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-zinc-900">Birleştirilmiş Prompt</span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-zinc-100 text-zinc-400">
              {assembled.length} kr
            </span>
          </div>
          {previewOpen ? <ChevronUp size={16} className="text-zinc-300" /> : <ChevronDown size={16} className="text-zinc-300" />}
        </button>

        {previewOpen && (
          <div className="mt-3 bg-zinc-50 border border-zinc-200 rounded-lg p-3 font-mono text-xs text-zinc-600 whitespace-pre-wrap overflow-auto max-h-[400px]">
            {assembled}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function SettingsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-xl p-5 space-y-4">
      <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider pb-2 border-b border-zinc-100">
        {title}
      </h2>
      {children}
    </div>
  )
}

function InlineSave({ saving, saved, onSave }: { saving: boolean; saved: boolean; onSave: () => void }) {
  if (saved) {
    return (
      <span className="flex items-center gap-1 text-xs text-emerald-600 min-w-[80px]">
        <Check size={12} />Kaydedildi
      </span>
    )
  }
  return (
    <button
      onClick={onSave}
      disabled={saving}
      className="flex items-center gap-1 px-3 py-2 bg-zinc-900 hover:bg-zinc-700 disabled:opacity-50 text-white text-xs rounded-lg transition-colors"
    >
      {saving && <Loader2 className="animate-spin" size={11} />}
      Kaydet
    </button>
  )
}
