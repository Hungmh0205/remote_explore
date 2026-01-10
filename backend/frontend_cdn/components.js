// Vue Component for Recursive Tree Item
const TreeItem = {
    name: 'TreeItem',
    template: `
      <li class="tree-node">
        <div class="tree-content" 
             :class="{ active: isCurrent }"
             @click="select"
             @dblclick="toggle"
             @contextmenu.prevent="$emit('ctx', $event, model)"
             draggable="true"
             @dragstart="onDragStart"
             @dragover.prevent="onDragOver"
             @dragleave="onDragLeave"
             @drop="onDrop">
          <span class="tree-toggle" @click.stop="toggle">
            {{ isFolder ? (isOpen ? '▼' : '▶') : ' ' }}
          </span>
          <span class="tree-icon">{{ isOpen ? '📂' : '📁' }}</span>
          <span class="tree-label">{{ model.name }}</span>
        </div>
        <ul v-if="isFolder && isOpen" class="tree-children">
            <div v-if="loading" style="padding-left:20px; color:#999; font-size:11px">Loading...</div>
            <tree-item
              v-else
              v-for="(child, index) in children"
              :key="index"
              :model="child"
              :current-path="currentPath"
              @navigate="$emit('navigate', $event)"
              @ctx="(e, m) => $emit('ctx', e, m)"
              @moved="$emit('moved')"
            ></tree-item>
        </ul>
      </li>
    `,
    props: {
      model: Object, // { name, path, is_dir }
      currentPath: String
    },
    emits: ['navigate', 'ctx', 'moved'],
    data() {
      return {
        isOpen: false,
        children: [],
        loading: false,
        loadedOnce: false
      }
    },
    computed: {
      isFolder() {
        return this.model.is_dir
      },
      isCurrent() {
        // Simple string comparison for active state highlighting
        return this.currentPath && 
               this.currentPath.toLowerCase() === this.model.path.toLowerCase()
      }
    },
    methods: {
      async toggle() {
        if (!this.isFolder) return
        this.isOpen = !this.isOpen
        if (this.isOpen && !this.loadedOnce) {
            await this.loadChildren()
        }
      },
      async loadChildren() {
          this.loading = true
          try {
              // Fetch only directories for the tree
              const res = await axios.get('/api/list', { 
                  params: { path: this.model.path, only_dirs: true } 
              })
              this.children = res.data
              this.loadedOnce = true
          } catch (e) {
              console.error(e)
              this.children = []
          } finally {
              this.loading = false
          }
      },
      select() {
          this.$emit('navigate', this.model.path)
      },
      onDragStart(ev) {
          // Pass data for drag (handled by root logic mostly)
          // We attach raw path
          ev.dataTransfer.effectAllowed = 'move'
          ev.dataTransfer.setData('text/plain', this.model.path)
          // Custom json for internal app usage
          ev.dataTransfer.setData('application/json', JSON.stringify({ path: this.model.path, is_dir: true }))
      },
      onDragOver(ev) {
          if(!this.isFolder) return
          ev.currentTarget.classList.add('dragover')
      },
      onDragLeave(ev) {
          ev.currentTarget.classList.remove('dragover')
      },
      async onDrop(ev) {
          ev.currentTarget.classList.remove('dragover')
          if(!this.isFolder) return
          ev.stopPropagation() // Don't bubble to parent folder
          
          const destination = this.model.path
          
          // Check if dragging files from the main list or from another tree node
          // The main list uses 'dragging.items' global state in main app, 
          // but here we can only access what's in dataTransfer easily or we emit event.
          
          // Let's assume the main app handles the actual move logic via an event
          // We just tell the parent "Something was dropped onto ME (destination)"
          
          // However, accessing the 'source' from dataTransfer is tricky if it's internal JS object.
          // Simplest way: Emit event "drop-on-me" and let Root handle it.
          // But dataTransfer text/plain might be available.
          
          // Let's rely on standard html5 dnd for string paths if possible, 
          // OR better: Emit an event to Root index.html which has access to `dragging.items`
          
          this.$emit('moved', { destination }) 
      }
    }
  }
