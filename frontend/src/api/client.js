const BASE = import.meta.env.VITE_API_URL ?? '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let message = `API ${res.status}: ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.error) message = body.error
    } catch {
      // non-JSON error body - keep the default message
    }
    throw new Error(message)
  }
  return res.json()
}

function formRequest(path, formData) {
  return request(path, { method: 'POST', headers: {}, body: formData })
}

function audioUrl(sessionId, answerId) {
  return `${BASE}/sessions/${sessionId}/answers/${answerId}/audio`
}

export const api = {
  getHealth: () => request('/health'),
  parseResume: (file) => {
    const form = new FormData()
    form.append('file', file)
    return formRequest('/resume/parse', form)
  },
  getLanguages: () => request('/languages'),
  getRoles: () => request('/roles'),
  getChallenges: (language, difficulty) =>
    request(`/challenges?language=${encodeURIComponent(language)}&difficulty=${encodeURIComponent(difficulty)}`),
  runChallenge: (payload) => request('/challenges/run', { method: 'POST', body: JSON.stringify(payload) }),
  generateQuestions: (payload) => request('/questions/generate', { method: 'POST', body: JSON.stringify(payload) }),
  evaluateAnswer: (payload) => request('/feedback/evaluate', { method: 'POST', body: JSON.stringify(payload) }),
  analyzeSpeech: (payload) => request('/speech/analyze', { method: 'POST', body: JSON.stringify(payload) }),
  createSession: (payload) => request('/sessions', { method: 'POST', body: JSON.stringify(payload) }),
  listSessions: () => request('/sessions'),
  getSession: (sessionId) => request(`/sessions/${sessionId}`),
  deleteSession: (sessionId) =>
    request(`/sessions/${sessionId}`, { method: 'DELETE' }),
  submitAnswer: (sessionId, payload) =>
    request(`/sessions/${sessionId}/answers`, { method: 'POST', body: JSON.stringify(payload) }),
  submitCoding: (sessionId, payload) =>
    request(`/sessions/${sessionId}/coding`, { method: 'POST', body: JSON.stringify(payload) }),
  completeSession: (sessionId) =>
    request(`/sessions/${sessionId}/complete`, { method: 'POST', body: JSON.stringify({}) }),
  uploadAnswerAudio: (sessionId, answerId, blob, mimeType = 'audio/webm') => {
    const form = new FormData()
    form.append('audio', new Blob([blob], { type: mimeType }), `answer-${answerId}.webm`)
    return formRequest(`/sessions/${sessionId}/answers/${answerId}/audio`, form)
  },
  answerAudioUrl: audioUrl,
}
