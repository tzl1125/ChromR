// composables/useSSE.js
import { ref, onMounted, onBeforeUnmount } from 'vue'

const server_ip = import.meta.env.VITE_APP_ServerUrl

export function useSSE() {
  const tasks = ref([])
  const logs = ref([])
  const records = ref([])
  const expDesigns = ref([])
  let eventSource = null

  const deleteTask = async (taskId) => {
    try {
      await fetch(`${server_ip}/delete_task/${taskId}`, { method: 'DELETE' })
    } catch (error) {
      alert('删除失败')
      console.error('删除失败:', error)
    }
  }

  onMounted(() => {
    eventSource = new EventSource(`${server_ip}/sse`)

    eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'tasks') tasks.value = data.payload
      if (data.type === 'logs') logs.value = data.payload
      if (data.type === 'records') records.value = data.payload
      if (data.type === 'exp_design') expDesigns.value = data.payload
    }
  })

  onBeforeUnmount(() => {
    eventSource?.close()
  })

  return { tasks, logs, records, expDesigns, deleteTask }
}