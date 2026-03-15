import axios from 'axios'
import { clearToken, getToken } from './auth'

export interface DashboardData {
  today_bookings: number
  total_confirmed: number
  total_cancelled: number
  active_sessions: number
  takeover_active: number
  total_users: number
  recent_bookings: Booking[]
}

export interface Booking {
  id: number
  customer_name: string
  customer_phone: string
  service: string
  appointment_date: string
  appointment_time: string
  staff_name: string
  location_type: string
  branch_id: string
  visit_address: string | null
  guest_count: number
  total_price_tl: number
  status: string
  whatsapp_id: string
  created_at: string
}

export interface Conversation {
  whatsapp_id: string
  customer_name: string | null
  last_message: string
  last_message_at: string
  message_count: number
  state: string
  takeover: boolean
}

export interface Message {
  id: number
  direction: 'in' | 'out'
  content: string
  message_type: string
  created_at: string
}

export interface AppointmentParams {
  date?: string
  status?: string
  staff?: string
  branch?: string
  limit?: number
  offset?: number
}

export interface AppointmentsResponse {
  total: number
  items: Booking[]
}

const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const api = axios.create({ baseURL })

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearToken()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export async function login(password: string): Promise<{ token: string }> {
  const res = await api.post<{ token: string }>('/admin/auth', { password })
  return res.data
}

export async function getDashboard(): Promise<DashboardData> {
  const res = await api.get<DashboardData>('/admin/dashboard')
  return res.data
}

export async function getAppointments(params: AppointmentParams = {}): Promise<AppointmentsResponse> {
  const res = await api.get<AppointmentsResponse>('/admin/appointments', { params })
  return res.data
}

export async function updateAppointment(id: number, status: string): Promise<Booking> {
  const res = await api.patch<Booking>(`/admin/appointments/${id}`, { status })
  return res.data
}

export async function getConversations(): Promise<Conversation[]> {
  const res = await api.get<Conversation[]>('/admin/conversations')
  return res.data
}

export async function getMessages(whatsappId: string): Promise<Message[]> {
  const res = await api.get<Message[]>(`/admin/conversations/${whatsappId}`)
  return res.data
}

export async function sendMessage(whatsappId: string, message: string): Promise<{ status: string }> {
  const res = await api.post<{ status: string }>(`/admin/conversations/${whatsappId}/send`, { message })
  return res.data
}

export async function setTakeover(whatsappId: string, active: boolean): Promise<{ takeover: boolean }> {
  const res = await api.post<{ takeover: boolean }>(`/admin/takeover/${whatsappId}`, { active })
  return res.data
}

export interface UserSession {
  state: string
  flow_step: string
  flow_data: Record<string, unknown>
  takeover: boolean
  last_activity: string | null
}

export interface UserProfile {
  whatsapp_id: string
  booking_phone: string | null
  created_at: string
  last_seen: string
  message_count: number
  session: UserSession
  bookings: Booking[]
}

export async function getUserProfile(whatsappId: string): Promise<UserProfile> {
  const res = await api.get<UserProfile>(`/admin/users/${whatsappId}`)
  return res.data
}

export async function resetSession(whatsappId: string): Promise<{ status: string }> {
  const res = await api.post<{ status: string }>(`/admin/sessions/${whatsappId}/reset`)
  return res.data
}

export async function getSettings(): Promise<Record<string, string>> {
  const res = await api.get<Record<string, string>>('/admin/settings')
  return res.data
}

export async function updateSetting(key: string, value: string): Promise<{ key: string; value: string }> {
  const res = await api.put<{ key: string; value: string }>(`/admin/settings/${key}`, { value })
  return res.data
}

export interface PromptSection {
  key: string
  label: string
  description: string
  value: string
  is_default: boolean
  default_value: string
}

export interface PromptData {
  sections: PromptSection[]
  assembled: string
}

export async function getPromptSections(): Promise<PromptData> {
  const res = await api.get<PromptData>('/admin/prompt')
  return res.data
}

export async function updatePromptSection(key: string, value: string): Promise<{ key: string; value: string }> {
  const res = await api.put<{ key: string; value: string }>(`/admin/prompt/${key}`, { value })
  return res.data
}

export async function resetPromptSection(key: string): Promise<{ key: string; value: string; is_default: boolean }> {
  const res = await api.delete<{ key: string; value: string; is_default: boolean }>(`/admin/prompt/${key}`)
  return res.data
}
