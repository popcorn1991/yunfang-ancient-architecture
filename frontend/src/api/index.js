import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 15000
})

api.interceptors.response.use(
  response => response.data,
  error => {
    console.error('接口请求失败：', error)
    return Promise.reject(error)
  }
)

export const getHealth = () => api.get('/api/health')
export const getStats = () => api.get('/api/stats')
export const getFilters = () => api.get('/api/filters')

export const searchBuildings = params =>
  api.get('/api/buildings', { params })

export const getBuildingDetail = recordId =>
  api.get(`/api/buildings/${recordId}`)

export const getBuildingGraph = (recordId, params = {}) =>
  api.get(`/api/graph/${recordId}`, { params })

export const getRecommendations = (recordId, limit = 10) =>
  api.get(`/api/recommendations/${recordId}`, {
    params: { limit }
  })

export const getPeriodAnalysis = province =>
  api.get('/api/analysis/periods', {
    params: province ? { province } : {}
  })

export const getOverviewAnalysis = () => api.get('/api/analysis/overview')

export const askQuestion = question =>
  api.post('/api/qa', { question })

export default api