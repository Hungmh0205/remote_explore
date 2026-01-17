
    const { createApp, ref, onMounted, reactive, computed, nextTick, watch } = Vue
    require.config({ paths: { 'vs': 'https://unpkg.com/monaco-editor@0.44.0/min/vs' } });
    require(['vs/editor/editor.main'], function () {
      createApp({
        setup() {
          const currentPath = ref('C:\\')
          const entries = ref([])
          const menu = reactive({ visible: false, x: 0, y: 0, item: null })
          const clipboard = reactive({ item: null, mode: null })
          const editor = reactive({ visible: false, path: '', name: '', content: '', editable: false, type: '', url: '' })
          const propsModal = reactive({ visible: false, item: null, data: null, readonly: false, modified: null })
          const selected = reactive(new Set())
          let lastClickedIndex = -1
          const dragging = reactive({ active: false, items: [] })
          const undoToken = ref('')
          const pins = ref([])
          const drives = ref([])
          const share = reactive({ visible: false, item: null, access: 'readonly', allowDownload: true, noExpiry: true, expiresHours: 24, url: '', generating: false, expiresAt: null })
          const sidebarEl = ref(null)
          const filterText = ref('')
          const page = ref(1)
          const pageSize = ref(100)
          const theme = ref('light')

          // New States
          const viewMode = ref('list')
          const deepSearch = ref('false')
          const uploading = reactive({ active: false, currentFile: '', percent: 0 })
          const stats = reactive({ cpu: 0, mem_used: 0, mem_total: 0, mem_pct: 0, disk_free: 0, disk_pct: 0 })
          const wsStatus = ref(false)
          let ws = null

          // Input Modal Logic
          const newMenu = reactive({ visible: false })
          const inputModal = reactive({ visible: false, title: '', value: '', resolve: null })
          function showInput(title, defaultValue = '') {
            return new Promise(resolve => {
              inputModal.title = title
              inputModal.value = defaultValue
              inputModal.visible = true
              inputModal.resolve = resolve
              nextTick(() => document.getElementById('modal-input-field')?.focus())
            })
          }
          function resolveInput(val) {
            inputModal.visible = false
            if (inputModal.resolve) inputModal.resolve(val)
            inputModal.resolve = null
          }

          // Toast Logic
          const toasts = ref([]) // { id, msg, type }
          let toastId = 0
          function showToast(msg, type = 'info', duration = 3000) {
            const id = toastId++
            toasts.value.push({ id, msg, type })
            if (duration > 0) {
              setTimeout(() => removeToast(id), duration)
            }
          }
          function removeToast(id) {
            const idx = toasts.value.findIndex(t => t.id === id)
            if (idx !== -1) toasts.value.splice(idx, 1)
          }

          // Monaco Logic
          let monacoEditor = null

          function initMonaco() {
            return new Promise((resolve) => {
              if (window.monaco) return resolve()
              require.config({ paths: { 'vs': 'https://unpkg.com/monaco-editor@0.44.0/min/vs' } });
              require(['vs/editor/editor.main'], function () {
                resolve()
              });
            })
          }

          async function createMonaco(content, readOnly, language) {
            await initMonaco()
            const host = document.getElementById('cm-host') // reuse same ID for container
            if (!host) return

            // Dispose old if exists
            if (monacoEditor) {
              monacoEditor.dispose()
              monacoEditor = null
            }
            host.innerHTML = '' // clear any debris

            monacoEditor = monaco.editor.create(host, {
              value: content,
              language: language || 'plaintext',
              theme: 'vs-dark', // Force Dark Theme for IDE look
              readOnly: readOnly,
              automaticLayout: true,
              minimap: { enabled: true },
              scrollBeyondLastLine: false,
              fontSize: 14,
              padding: { top: 10, bottom: 10 }
            })
          }

          function getMonacoLanguage(filename) {
            const ext = filename.split('.').pop().toLowerCase()
            const map = {
              'js': 'javascript', 'ts': 'typescript', 'py': 'python', 'html': 'html', 'css': 'css',
              'json': 'json', 'md': 'markdown', 'xml': 'xml', 'sql': 'sql', 'sh': 'shell',
              'bat': 'bat', 'java': 'java', 'c': 'c', 'cpp': 'cpp', 'go': 'go', 'rs': 'rust',
              'php': 'php', 'rb': 'ruby', 'yml': 'yaml', 'yaml': 'yaml', 'ini': 'ini'
            }
            return map[ext] || 'plaintext'
          }

          async function load(path) {
            try {
              const res = await axios.get('/api/list', { params: { path } })
              entries.value = res.data
              currentPath.value = path
              try { localStorage.setItem('rfe:lastPath', path) } catch { }
              page.value = 1
              updateWatcher(path)
            } catch (err) {
              const msg = err?.response?.data?.detail || err?.message || 'Unknown error'
              showToast('Không thể truy cập thư mục này: ' + msg, 'error')
            }
          }

          async function performSearch() {
            if (deepSearch.value && filterText.value.trim().length > 0) {
              try {
                entries.value = [] // Clear for visual feedback
                const res = await axios.post('/api/search', { path: currentPath.value, query: filterText.value })
                entries.value = res.data
                page.value = 1
              } catch (err) {
                showToast('Search failed: ' + err.message, 'error')
              }
            }
            // Normal filter handled by computed prop 'filteredEntries' if deepSearch is false
          }

          // Watcher Logic
          function initWatcher() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/ws/watcher`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
              wsStatus.value = true
              if (currentPath.value) updateWatcher(currentPath.value)
            };
            ws.onmessage = (ev) => {
              if (ev.data === 'change') {
                // Reload current path silently
                load(currentPath.value)
              }
            };
            ws.onclose = () => { wsStatus.value = false; setTimeout(initWatcher, 3000) };
            ws.onerror = () => { ws.close() };
          }

          function updateWatcher(path) {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ action: 'watch', path }))
            }
          }

          // Monitoring Logic
          async function fetchStats() {
            try {
              const res = await axios.get('/api/monitor/stats', { params: { path: currentPath.value } })
              const d = res.data
              stats.cpu = d.cpu_percent
              stats.mem_pct = d.memory_percent
              stats.mem_used = formatSize(d.memory_used)
              stats.mem_total = formatSize(d.memory_total)
              stats.disk_free = formatSize(d.disk_free)
              stats.disk_pct = d.disk_percent
            } catch { }
          }

          function displayName(p) { return p }
          async function fetchPins() {
            try {
              const res = await axios.get('/api/pins')
              if (Array.isArray(res.data)) pins.value = res.data
            } catch (err) {
              showToast('Không thể tải danh sách pin: ' + (err.response?.data?.detail || err.message), 'error')
            }
          }
          async function pin(path) {
            try {
              await axios.post('/api/pins', { path })
              await fetchPins()
            } catch (err) {
              showToast('Không thể pin: ' + (err.response?.data?.detail || err.message), 'error')
            }
          }
          async function unpin(path) {
            try {
              await axios.delete('/api/pins', { params: { path } })
              await fetchPins()
            } catch (err) {
              showToast('Không thể bỏ pin: ' + (err.response?.data?.detail || err.message), 'error')
            }
          }
          function onSidebarDragOver(ev) { ev.currentTarget.classList.add('dragover') }
          function onSidebarDragLeave(ev) { ev.currentTarget.classList.remove('dragover') }
          async function onSidebarDrop(ev) {
            ev.currentTarget.classList.remove('dragover')
            // Prefer first selected folder; fallback to currentPath
            const folder = entries.value.find(e => selected.has(e.path) && e.is_dir)
            if (folder) await pin(folder.path)
          }
          function navigate(path) { load(path) }
          function goUp() {
            const p = currentPath.value.replace(/\\+$/, '')
            const idx = p.lastIndexOf('\\')
            if (idx > 2) load(p.slice(0, idx)); else load(p.slice(0, 3))
          }
          function openDir(e) { if (e.is_dir) load(e.path) }
          function getFileTypeByName(name) {
            const lower = name.toLowerCase(); const ext = lower.split('.').pop()
            const text = ['txt', 'md', 'log', 'json', 'xml', 'csv', 'ini', 'conf', 'yaml', 'yml', 'py', 'js', 'ts', 'java', 'c', 'cpp', 'cs', 'go', 'rb', 'php', 'bat', 'ps1', 'html', 'css', 'sql', 'sh']
            if (text.includes(ext)) return 'text'
            const img = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico']
            if (img.includes(ext)) return 'image'
            if (ext === 'pdf') return 'pdf'
            const aud = ['mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac']
            if (aud.includes(ext)) return 'audio'
            const vid = ['mp4', 'webm', 'ogv', 'mkv', 'mov']
            if (vid.includes(ext)) return 'video'
            return 'other'
          }
          function isImage(name) { return getFileTypeByName(name) === 'image' }

          async function downloadFile(e) {
            const url = `/api/file?path=${encodeURIComponent(e.path)}`
            const a = document.createElement('a')
            a.href = url; a.download = e.name; a.click()
          }
          async function downloadSelected() {
            if (selected.size === 0) return
            const selectedItems = Array.from(selected).map(path => entries.value.find(e => e.path === path)).filter(Boolean)
            if (selectedItems.length === 0) return

            // If only one item selected, download directly
            if (selectedItems.length === 1) {
              const item = selectedItems[0]
              if (item.is_dir) {
                // Download folder as ZIP
                const url = `/api/zip?path=${encodeURIComponent(item.path)}`
                const a = document.createElement('a')
                a.href = url; a.download = `${item.name}.zip`; a.click()
              } else {
                // Download single file
                downloadFile(item)
              }
              return
            }

            // Multiple items selected - create a temporary ZIP
            try {
              const paths = selectedItems.map(item => item.path)
              const response = await axios.post('/api/zip/multiple', { paths }, { responseType: 'blob' })
              const url = window.URL.createObjectURL(new Blob([response.data]))
              const a = document.createElement('a')
              a.href = url; a.download = 'selected_files.zip'; a.click()
              window.URL.revokeObjectURL(url)
            } catch (err) {
              showToast('Failed to download selected files: ' + (err.response?.data?.detail || err.message), 'error')
            }
          }
          async function onUpload(ev) {
            const input = ev.target
            if (!input.files || input.files.length === 0) return

            uploading.active = true
            try {
              for (let i = 0; i < input.files.length; i++) {
                const file = input.files[i]
                uploading.currentFile = file.name
                uploading.percent = 0
                const form = new FormData()
                form.append('file', file)
                // Append relative path if available (for webkitdirectory)
                // file.webkitRelativePath is usually "Folder/Sub/File.txt"
                // We need to send this to backend.
                if (file.webkitRelativePath) {
                  form.append('rel_path', file.webkitRelativePath)
                }

                await axios.post('/api/upload', form, {
                  params: { dest: currentPath.value },
                  onUploadProgress: (progressEvent) => {
                    const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                    uploading.percent = percent;
                  }
                })
              }
              await load(currentPath.value)
            } catch (err) {
              showToast('Upload failed: ' + err.message, 'error')
            } finally {
              uploading.active = false
              input.value = ''
            }
          }

          // Remove promptNew, replaced by dropdown

          async function promptRename(e) {
            const newName = await showInput('Rename', e.name)
            if (!newName || newName === e.name) return
            try {
              await axios.post('/api/rename', { path: e.path, new_name: newName })
              await load(currentPath.value)
            } catch (err) {
              showToast('Rename failed: ' + err.message, 'error')
            }
          }
          async function deletePath(e) {
            if (!window.confirm(`Delete ${e.name}?`)) return
            try {
              await axios.post('/api/delete', { path: e.path })
              await load(currentPath.value)
            } catch (err) { showToast('Delete failed: ' + err.message, 'error') }
          }
          function isSelected(e) { return selected.has(e.path) }
          function clearSelection() { selected.clear(); lastClickedIndex = -1 }
          function onRowClick(ev, e, idx) {
            const isCtrl = ev.ctrlKey || ev.metaKey
            const isShift = ev.shiftKey
            if (isShift && lastClickedIndex >= 0) {
              const [a, b] = idx > lastClickedIndex ? [lastClickedIndex, idx] : [idx, lastClickedIndex]
              selected.clear()
              for (let i = a; i <= b; i++) selected.add(entries.value[i].path)
            } else if (isCtrl) {
              if (selected.has(e.path)) selected.delete(e.path); else selected.add(e.path)
              lastClickedIndex = idx
            } else {
              selected.clear(); selected.add(e.path); lastClickedIndex = idx
            }
          }
          function onDragStart(ev, e) {
            // if the dragged item isn't selected, select it first
            if (!selected.has(e.path)) { selected.clear(); selected.add(e.path) }
            dragging.active = true
            dragging.items = Array.from(selected)
            ev.dataTransfer.effectAllowed = 'move'
          }
          function onDragEnd() { dragging.active = false; dragging.items = [] }
          function onDragOver(ev) { ev.currentTarget.classList.add('drop-target') }
          function onDragLeave(ev) { ev.currentTarget.classList.remove('drop-target') }
          async function onDrop(ev, folder) {
            ev.currentTarget.classList.remove('drop-target')
            if (!folder || !folder.is_dir) return
            const destination = folder.path
            for (const src of dragging.items) {
              if (samePath(src, destination) || isChildOf(destination, src)) continue
              const res = await axios.post('/api/move', { source: src, destination })
              if (res.data?.undo_token) undoToken.value = res.data.undo_token
            }
            await load(currentPath.value)
          }
          async function undo() {
            if (!undoToken.value) return
            await axios.post('/api/undo', { token: undoToken.value })
            undoToken.value = ''
            await load(currentPath.value)
          }
          function samePath(a, b) { return normalize(a) === normalize(b) }
          function isChildOf(child, parent) { const A = normalize(child); const B = normalize(parent); return A.startsWith(B + '\\') }
          function normalize(p) { return p.replace(/\\+/g, '\\').replace(/\\$/, '').toLowerCase() }
          function openContextMenu(ev, item) {
            menu.visible = true; menu.x = ev.pageX; menu.y = ev.pageY; menu.item = item
            document.addEventListener('click', () => { menu.visible = false }, { once: true })
          }
          function openBlankMenu(ev) {
            // Only trigger when clicking whitespace, not on row (row handler stops propagation)
            if (ev.target.closest('tr') || ev.target.closest('.grid-item')) return
            menu.visible = true; menu.x = ev.pageX; menu.y = ev.pageY; menu.item = null
            document.addEventListener('click', () => { menu.visible = false }, { once: true })
          }
          function isTextFile(item) {
            if (!item || item.is_dir) return false
            const exts = ['.txt', '.md', '.log', '.json', '.xml', '.csv', '.ini', '.conf', '.cfg', '.yaml', '.yml', '.toml', '.properties', '.reg', '.vbs', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.cs', '.go', '.rb', '.php', '.bat', '.cmd', '.ps1', '.html', '.css', '.sql', '.sh']
            const name = item.name.toLowerCase()
            return exts.some(e => name.endsWith(e))
          }
          function cmOpen(item) {
            if (!item) return
            if (!item.is_dir) {
              window.open(`/api/open?path=${encodeURIComponent(item.path)}`, '_blank')
            } else {
              openDir(item)
            }
          }
          async function cmEdit(item) {
            if (!item || item.is_dir) return
            const res = await axios.get('/api/read', { params: { path: item.path }, responseType: 'text' })
            editor.visible = true; editor.path = item.path; editor.name = item.name; editor.type = 'text'; editor.content = res.data; editor.editable = false
            await nextTick()
            await createMonaco(editor.content, false, getMonacoLanguage(item.name))
          }

          async function preview(item) {
            if (!item || item.is_dir) return
            const ftype = getFileTypeByName(item.name)
            editor.visible = true; editor.path = item.path; editor.name = item.name; editor.type = ftype; editor.editable = false

            if (ftype === 'text') {
              const res = await axios.get('/api/read', { params: { path: item.path }, responseType: 'text' })
              editor.content = res.data
              await nextTick()
              await createMonaco(editor.content, true, getMonacoLanguage(item.name))
            } else if (ftype === 'image' || ftype === 'pdf' || ftype === 'audio' || ftype === 'video') {
              editor.url = `/api/open?path=${encodeURIComponent(item.path)}`
            } else {
              try {
                const res = await axios.get('/api/read', { params: { path: item.path }, responseType: 'text' })
                editor.type = 'text'; editor.content = res.data
                await nextTick()
                await createMonaco(editor.content, true, getMonacoLanguage(item.name))
              } catch (e) {
                showToast('Cannot preview this file.', 'error'); editor.visible = false
              }
            }
          }
          function cmCopy(item) { clipboard.item = item; clipboard.mode = 'copy' }
          function cmCut(item) { clipboard.item = item; clipboard.mode = 'cut' }
          async function pasteHere() {
            if (!clipboard.item || !clipboard.mode) return
            const target = currentPath.value
            try {
              if (clipboard.mode === 'copy') {
                await axios.post('/api/copy', { source: clipboard.item.path, destination: target })
              } else {
                const res = await axios.post('/api/move', { source: clipboard.item.path, destination: target })
                if (res.data?.undo_token) undoToken.value = res.data.undo_token
              }
            } finally {
              clipboard.item = null; clipboard.mode = null
            }
            await load(currentPath.value)
          }
          function cmDownload(item) {
            if (!item || item.is_dir) return
            const a = document.createElement('a')
            a.href = `/api/file?path=${encodeURIComponent(item.path)}`
            a.download = item.name
            a.click()
          }
          function cmZipDownload(item, fast = false) {
            if (!item || !item.is_dir) return
            const a = document.createElement('a')
            a.href = `/api/zip?path=${encodeURIComponent(item.path)}&fast=${fast ? 'true' : 'false'}`
            a.download = item.name + '.zip'
            a.click()
          }
          function openShare(item) { share.visible = true; share.item = item; share.url = ''; share.expiresAt = null }
          function closeShare() { share.visible = false }
          async function createShareLink() {
            if (!share.item) return
            share.generating = true
            try {
              const body = {
                path: share.item.path,
                readonly: share.access === 'readonly',
                allow_edit: share.access === 'edit',
                allow_download: !!share.allowDownload,
                expires_hours: share.noExpiry ? null : (share.expiresHours || null),
              }
              const res = await axios.post('/api/share/create', body)
              share.url = res.data?.url || ''
              share.expiresAt = res.data?.expires_at || null
            } finally {
              share.generating = false
            }
          }
          async function copyShare() {
            try { await navigator.clipboard.writeText(share.url) } catch { }
          }
          async function cmRename(item) { await promptRename(item) }
          async function cmDelete(item) { await deletePath(item) }
          async function createFolder() {
            const name = await showInput('New Folder Name')
            if (!name) return
            try {
              await axios.post('/api/mkdir', { path: join(currentPath.value, name) })
              await load(currentPath.value)
            } catch (err) { showToast('Create folder failed: ' + err.message, 'error') }
          }
          async function createFile() {
            const name = await showInput('New File Name')
            if (!name) return
            try {
              await axios.post('/api/save', { path: join(currentPath.value, name), content: '' })
              await load(currentPath.value)
            } catch (err) { showToast('Create file failed: ' + err.message, 'error') }
          }
          function applyEditorReadonly() {
            if (monacoEditor) monacoEditor.updateOptions({ readOnly: !editor.editable })
          }

          async function saveEditor() {
            if (monacoEditor) editor.content = monacoEditor.getValue()
            await axios.post('/api/save', { path: editor.path, content: editor.content })
            editor.editable = false
            applyEditorReadonly()
          }

          function closeEditor() {
            editor.visible = false
            if (monacoEditor) {
              monacoEditor.dispose()
              monacoEditor = null
            }
          }
          function join(a, b) { return a.endsWith('\\') ? a + b : a + '\\' + b }
          function formatSize(bytes) {
            const thresh = 1024; if (Math.abs(bytes) < thresh) return bytes + ' B'
            const units = ['KB', 'MB', 'GB', 'TB', 'PB']; let u = -1
            do { bytes /= thresh; u++ } while (Math.abs(bytes) >= thresh && u < units.length - 1)
            return bytes.toFixed(1) + ' ' + units[u]
          }
          function formatTime(epoch) { return new Date(epoch * 1000).toLocaleString() }
          function formatExpire(ts) { try { return new Date(ts * 1000).toLocaleString() } catch { return '' } }

          const filteredEntries = computed(() => {
            // If deep search happened, entries already contains filtered result from backend
            if (deepSearch.value && filterText.value.length > 0) return entries.value

            const q = filterText.value.trim().toLowerCase()
            if (!q) return entries.value
            return entries.value.filter(e => e.name.toLowerCase().includes(q))
          })

          const totalPages = computed(() => Math.max(1, Math.ceil(filteredEntries.value.length / pageSize.value)))
          const paginatedEntries = computed(() => {
            const start = (page.value - 1) * pageSize.value
            return filteredEntries.value.slice(start, start + pageSize.value)
          })
          function nextPage() { if (page.value < totalPages.value) page.value++ }
          function prevPage() { if (page.value > 1) page.value-- }
          const pathSegments = computed(() => {
            const p = currentPath.value.replace(/\\+$/, '')
            if (!/^[A-Za-z]:\\/.test(p)) return []
            const parts = p.split('\\').filter(Boolean)
            const segs = []
            let accum = ''
            for (let i = 0; i < parts.length; i++) {
              if (i === 0) {
                accum = parts[0] + '\\'
                segs.push({ label: parts[0] + '\\', path: accum })
              } else {
                accum = accum.endsWith('\\') ? accum + parts[i] : accum + '\\' + parts[i]
                segs.push({ label: parts[i], path: accum })
              }
            }
            return segs
          })
          function toggleTheme() {
            theme.value = theme.value === 'dark' ? 'light' : 'dark'
            try { localStorage.setItem('rfe:theme', theme.value) } catch { }
            document.body.classList.toggle('dark', theme.value === 'dark')
            if (monacoEditor) {
              monaco.editor.setTheme(theme.value === 'dark' ? 'vs-dark' : 'vs')
            }
          }
          function toggleViewMode() {
            viewMode.value = viewMode.value === 'list' ? 'grid' : 'list'
            try { localStorage.setItem('rfe:viewMode', viewMode.value) } catch { }
          }

          function onPreviewError() { showToast('Cannot preview this file. Please download and open locally.', 'error'); editor.visible = false }
          try { Object.defineProperty(window, '__vue_onerror', { value: onPreviewError }) } catch { }
          function toLocalDateTimeInput(ts) {
            try { const d = new Date(ts * 1000); const pad = n => String(n).padStart(2, '0'); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}` } catch { return '' }
          }
          function fromLocalDateTimeInput(val) {
            try { const d = new Date(val); return Math.floor(d.getTime() / 1000) } catch { return null }
          }
          async function openProperties(item) {
            if (!item) return
            propsModal.visible = true; propsModal.item = item; propsModal.data = null
            try {
              const res = await axios.get('/api/stat', { params: { path: item.path } })
              propsModal.data = res.data
              propsModal.readonly = !!res.data?.readonly
              propsModal.modified = res.data?.modified || null
            } catch (err) {
              showToast('Failed to load properties: ' + (err.response?.data?.detail || err.message), 'error')
            }
          }
          function closeProperties() { propsModal.visible = false }
          const propsModifiedLocal = computed(() => propsModal.data ? toLocalDateTimeInput(propsModal.modified || propsModal.data.modified) : '')
          function onPropsModifiedChange(ev) { const v = ev.target.value; const ts = fromLocalDateTimeInput(v); if (ts) propsModal.modified = ts }
          async function saveProperties() {
            if (!propsModal.item) return
            try {
              await axios.post('/api/update_meta', { path: propsModal.item.path, modified: propsModal.modified, readonly: propsModal.readonly })
              await openProperties(propsModal.item)
            } catch (err) {
              showToast('Failed to save properties: ' + (err.response?.data?.detail || err.message), 'error')
            }
          }
          onMounted(async () => {
            let initial = currentPath.value
            try {
              const saved = localStorage.getItem('rfe:lastPath')
              if (saved) initial = saved
            } catch { }

            try {
              const savedView = localStorage.getItem('rfe:viewMode')
              if (savedView) viewMode.value = savedView
            } catch { }

            await load(initial)

            try {
              const res = await axios.get('/api/roots')
              if (Array.isArray(res.data)) drives.value = res.data
            } catch { }
            await fetchPins()
            try {
              const t = localStorage.getItem('rfe:theme')
              if (t === 'dark') { theme.value = 'dark'; document.body.classList.add('dark') }
            } catch { }

            initWatcher()

            // Poll system stats
            fetchStats()
            setInterval(fetchStats, 5000)

            window.addEventListener('keydown', (ev) => {
              const tag = (ev.target && ev.target.tagName) ? ev.target.tagName.toLowerCase() : ''
              const isTyping = tag === 'input' || tag === 'textarea'
              if (ev.key === 'Enter') {
                if (isTyping) return // Let input handle enter (search etc)
                const first = entries.value.find(e => selected.has(e.path))
                if (first) { ev.preventDefault(); first.is_dir ? openDir(first) : cmOpen(first) }
              }
              if (ev.key === 'Backspace' && !isTyping) {
                ev.preventDefault();
                goUp()
              }
              if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'c') {
                const first = entries.value.find(e => selected.has(e.path))
                if (first) { ev.preventDefault(); cmCopy(first) }
              }
              if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'x') {
                const first = entries.value.find(e => selected.has(e.path))
                if (first) { ev.preventDefault(); cmCut(first) }
              }
              if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'v') {
                ev.preventDefault(); pasteHere()
              }
              if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'z') {
                ev.preventDefault();
                undo()
              }
            })
          })
          return { currentPath, entries, navigate, goUp, openDir, downloadFile, downloadSelected, onUpload, deletePath, formatSize, formatTime, openContextMenu, openBlankMenu, menu, cmOpen, cmEdit, cmCopy, cmCut, cmDownload, cmZipDownload, cmRename, cmDelete, clipboard, pasteHere, createFolder, createFile, editor, saveEditor, closeEditor, isTextFile, isSelected, onRowClick, onDragStart, onDragEnd, onDragOver, onDragLeave, onDrop, undoToken, undo, pins, drives, displayName, pin, unpin, onSidebarDragOver, onSidebarDragLeave, onSidebarDrop, share, openShare, closeShare, createShareLink, copyShare, formatExpire, selected, filterText, page, pageSize, paginatedEntries, totalPages, pathSegments, theme, toggleTheme, preview, applyEditorReadonly, propsModal, openProperties, closeProperties, propsModifiedLocal, onPropsModifiedChange, saveProperties, onPreviewError, performSearch, viewMode, toggleViewMode, deepSearch, stats, uploading, wsStatus, isImage, toasts, removeToast, inputModal, resolveInput, newMenu, promptRename }
        }
      }).mount('#app')
    });

  