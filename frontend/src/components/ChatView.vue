<template>
  <div class="app-container">
    <!-- サイドバー -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <button class="new-chat-btn" @click="createNewChat" :disabled="loading">
          ➕ 新しいチャット
        </button>
        <button class="sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed" aria-label="サイドバー切替">
          {{ sidebarCollapsed ? '☰' : '✕' }}
        </button>
      </div>
      <div v-if="!sidebarCollapsed" class="session-list">
        <div
          v-for="session in sessions"
          :key="session.session_id"
          :class="['session-item', { active: session.session_id === sessionId }]"
          @click="switchSession(session.session_id)"
        >
          <div class="session-preview">{{ session.last_message }}</div>
          <div class="session-meta">{{ session.message_count }}件 • {{ formatDate(session.created_at) }}</div>
          <button
            class="delete-session-btn"
            @click.stop="deleteSession(session.session_id)"
            aria-label="削除"
          >
            🗑️
          </button>
        </div>
        <div v-if="sessions.length === 0" class="empty-sessions">
          セッションがありません
        </div>
      </div>
    </aside>

    <!-- メインチャットエリア -->
    <div class="chat-container">
      <header class="chat-header">
        <h1>FAQ チャットボット</h1>
        <button class="upload-toggle" @click="showUpload = !showUpload" aria-label="データ管理">
          {{ showUpload ? '✕ 閉じる' : '📁 データ登録' }}
        </button>
      </header>
      <div v-if="showUpload" class="upload-panel">
        <p class="upload-desc">Excel (.xlsx) または画像 (.png, .jpg) をアップロードしてナレッジベースに登録</p>
        <div class="upload-area">
          <input
            type="file"
            ref="fileInput"
            accept=".xlsx,.png,.jpg,.jpeg"
            @change="onFileSelected"
            aria-label="ファイル選択"
          />
          <button
            @click="uploadFile"
            :disabled="!selectedFile || uploading"
            class="upload-btn"
          >
            {{ uploading ? 'アップロード中...' : 'アップロード＆登録' }}
          </button>
        </div>
        <div v-if="uploadResult" :class="['upload-result', uploadResult.success ? 'success' : 'error']">
          {{ uploadResult.message }}
        </div>
      </div>
      <main class="chat-messages" ref="messagesContainer">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message', msg.role]"
        >
          <div class="message-content">{{ msg.content }}</div>
          <div v-if="msg.sources && msg.sources.length" class="message-sources">
            <details>
              <summary>参照元 ({{ msg.sources.length }}件)</summary>
              <ul>
                <li v-for="(src, i) in msg.sources" :key="i">
                  <span v-if="src.content_type === 'image' && src.image_path">
                    <img
                      :src="'/data/images/' + src.image_path.split('/').pop()"
                      :alt="src.content"
                      class="source-thumbnail"
                    />
                  </span>
                  <span>{{ src.source_file }} (スコア: {{ src.score.toFixed(2) }})</span>
                </li>
              </ul>
            </details>
          </div>
        </div>
        <div v-if="loading" class="message assistant">
          <div class="message-content loading-dots">回答を生成中...</div>
        </div>
      </main>
      <footer class="chat-input">
        <input
          v-model="inputText"
          type="text"
          placeholder="質問を入力してください..."
          @keydown.enter.exact="onEnter"
          :disabled="loading"
          aria-label="質問入力欄"
        />
        <button @click="sendMessage" :disabled="loading || !inputText.trim()" aria-label="送信">
          送信
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'

const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const sessionId = ref('')
const messagesContainer = ref(null)
const showUpload = ref(false)
const selectedFile = ref(null)
const uploading = ref(false)
const uploadResult = ref(null)
const fileInput = ref(null)
const sessions = ref([])
const sidebarCollapsed = ref(false)

// セッションIDをlocalStorageに保存
watch(sessionId, (newId) => {
  if (newId) {
    localStorage.setItem('currentSessionId', newId)
  }
})

function onEnter(e) {
  if (e.isComposing) return
  sendMessage()
}

function onFileSelected(event) {
  selectedFile.value = event.target.files[0] || null
  uploadResult.value = null
}

async function uploadFile() {
  if (!selectedFile.value || uploading.value) return
  uploading.value = true
  uploadResult.value = null

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const res = await fetch('/api/upload', { method: 'POST', body: formData })
    const data = await res.json()

    if (res.ok) {
      const r = data.ingest_result
      uploadResult.value = {
        success: true,
        message: `${data.filename} を登録しました（${r.total_processed}件処理, ${r.error_count}件エラー）`,
      }
    } else {
      uploadResult.value = {
        success: false,
        message: data.detail || 'アップロードに失敗しました',
      }
    }
  } catch (e) {
    uploadResult.value = { success: false, message: '通信エラーが発生しました' }
  } finally {
    uploading.value = false
    selectedFile.value = null
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function loadSessions() {
  try {
    const res = await fetch('/api/sessions')
    const data = await res.json()
    sessions.value = data.sessions
  } catch (e) {
    console.error('セッション一覧の取得に失敗しました:', e)
  }
}

async function createNewChat() {
  try {
    const res = await fetch('/api/session', { method: 'POST' })
    const data = await res.json()
    sessionId.value = data.session_id
    messages.value = []
    await loadSessions()
  } catch (e) {
    console.error('セッション作成に失敗しました:', e)
  }
}

async function switchSession(newSessionId) {
  if (newSessionId === sessionId.value) return
  
  try {
    const res = await fetch(`/api/sessions/${newSessionId}`)
    const data = await res.json()
    sessionId.value = newSessionId
    
    // メッセージ履歴を復元
    messages.value = []
    for (const msg of data.messages) {
      messages.value.push({ role: 'user', content: msg.question })
      messages.value.push({
        role: 'assistant',
        content: msg.answer,
        sources: msg.sources || [],
      })
    }
    
    await scrollToBottom()
  } catch (e) {
    console.error('セッション切り替えに失敗しました:', e)
  }
}

async function deleteSession(sessionIdToDelete) {
  if (!confirm('このセッションを削除しますか？')) return
  
  try {
    const res = await fetch(`/api/sessions/${sessionIdToDelete}`, { method: 'DELETE' })
    if (res.ok) {
      await loadSessions()
      
      // 削除したセッションが現在のセッションの場合、クリア
      if (sessionIdToDelete === sessionId.value) {
        sessionId.value = ''
        messages.value = []
        localStorage.removeItem('currentSessionId')
      }
    }
  } catch (e) {
    console.error('セッション削除に失敗しました:', e)
  }
}

async function initSession() {
  // セッション一覧を読み込み
  await loadSessions()
  
  // localStorageから前回のセッションIDを取得
  const savedSessionId = localStorage.getItem('currentSessionId')
  
  if (savedSessionId) {
    // 保存されたセッションが存在するか確認
    const sessionExists = sessions.value.some(s => s.session_id === savedSessionId)
    
    if (sessionExists) {
      // セッションが存在する場合は復元
      await switchSession(savedSessionId)
    } else {
      // セッションが削除されている場合はクリア
      localStorage.removeItem('currentSessionId')
    }
  }
  
  // セッションIDが設定されていない場合は空の状態で待機
  // （最初のメッセージ送信時に新規セッション作成）
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  // セッションが未作成の場合は新規作成
  if (!sessionId.value) {
    await createNewChat()
  }

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  loading.value = true
  await scrollToBottom()

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: text, session_id: sessionId.value }),
    })
    const data = await res.json()
    messages.value.push({
      role: 'assistant',
      content: data.answer,
      sources: data.sources || [],
    })
    
    // セッション一覧を更新
    await loadSessions()
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: '通信エラーが発生しました。再度お試しください。',
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function formatDate(isoString) {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffMins < 1) return '今'
  if (diffMins < 60) return `${diffMins}分前`
  if (diffHours < 24) return `${diffHours}時間前`
  if (diffDays < 7) return `${diffDays}日前`
  
  return date.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' })
}

onMounted(() => {
  initSession()
})
</script>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  width: 100%;
  background: #fff;
}

/* サイドバー */
.sidebar {
  width: 280px;
  background: #f7f7f8;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
}

.sidebar.collapsed {
  width: 60px;
}

.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  gap: 8px;
  align-items: center;
}

.new-chat-btn {
  flex: 1;
  padding: 10px 16px;
  background: #1976d2;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  cursor: pointer;
  white-space: nowrap;
}

.new-chat-btn:hover {
  background: #1565c0;
}

.new-chat-btn:disabled {
  background: #aaa;
  cursor: not-allowed;
}

.sidebar.collapsed .new-chat-btn {
  display: none;
}

.sidebar-toggle {
  padding: 8px;
  background: transparent;
  border: 1px solid #ccc;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1.2rem;
}

.sidebar-toggle:hover {
  background: #e0e0e0;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.sidebar.collapsed .session-list {
  display: none;
}

.session-item {
  padding: 12px;
  margin-bottom: 8px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  cursor: pointer;
  position: relative;
  transition: background 0.2s;
}

.session-item:hover {
  background: #f0f0f0;
}

.session-item.active {
  background: #e3f2fd;
  border-color: #1976d2;
}

.session-preview {
  font-size: 0.9rem;
  color: #333;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  font-size: 0.75rem;
  color: #666;
}

.delete-session-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .delete-session-btn {
  opacity: 1;
}

.delete-session-btn:hover {
  transform: scale(1.2);
}

.empty-sessions {
  text-align: center;
  color: #999;
  padding: 20px;
  font-size: 0.9rem;
}

/* チャットコンテナ */
.chat-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100vh;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
}

.chat-header {
  padding: 16px;
  background: #1976d2;
  color: #fff;
  text-align: center;
  position: relative;
}

.chat-header h1 {
  font-size: 1.2rem;
  font-weight: 600;
}

.upload-toggle {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 0.85rem;
  cursor: pointer;
}

.upload-toggle:hover {
  background: rgba(255, 255, 255, 0.3);
}

.upload-panel {
  padding: 12px 16px;
  background: #e3f2fd;
  border-bottom: 1px solid #bbdefb;
}

.upload-desc {
  font-size: 0.85rem;
  color: #555;
  margin-bottom: 8px;
}

.upload-area {
  display: flex;
  gap: 8px;
  align-items: center;
}

.upload-area input[type="file"] {
  flex: 1;
  font-size: 0.9rem;
}

.upload-btn {
  padding: 8px 16px;
  background: #1976d2;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 0.9rem;
  cursor: pointer;
  white-space: nowrap;
}

.upload-btn:disabled {
  background: #aaa;
  cursor: not-allowed;
}

.upload-result {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
}

.upload-result.success {
  background: #c8e6c9;
  color: #2e7d32;
}

.upload-result.error {
  background: #ffcdd2;
  color: #c62828;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.5;
  word-break: break-word;
}

.message.user {
  align-self: flex-end;
  background: #1976d2;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message.assistant {
  align-self: flex-start;
  background: #e8e8e8;
  color: #333;
  border-bottom-left-radius: 4px;
}

.message-sources {
  margin-top: 8px;
  font-size: 0.85rem;
  color: #666;
}

.message-sources summary {
  cursor: pointer;
  color: #1976d2;
}

.message-sources ul {
  list-style: none;
  padding-left: 8px;
  margin-top: 4px;
}

.message-sources li {
  margin-bottom: 4px;
}

.source-thumbnail {
  width: 60px;
  height: 60px;
  object-fit: cover;
  border-radius: 4px;
  vertical-align: middle;
  margin-right: 8px;
}

.loading-dots {
  opacity: 0.7;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 0.3; }
}

.chat-input {
  display: flex;
  padding: 12px 16px;
  border-top: 1px solid #ddd;
  gap: 8px;
}

.chat-input input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #ccc;
  border-radius: 8px;
  font-size: 1rem;
  outline: none;
}

.chat-input input:focus {
  border-color: #1976d2;
}

.chat-input button {
  padding: 10px 20px;
  background: #1976d2;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
}

.chat-input button:disabled {
  background: #aaa;
  cursor: not-allowed;
}
</style>
