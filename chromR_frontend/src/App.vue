<!-- App.vue -->
<script setup>
import { ref } from 'vue'
import ChatBot from './components/ChatBot.vue'
import TaskPanel from './components/TaskPanel.vue'
import HardwareMonitor from './components/HardwareMonitor.vue'
import DeleteModal from './components/DeleteModal.vue'
import { useSSE } from './composables/useSSE'
import Sensors from './components/Sensors.vue';

const { tasks, deleteTask } = useSSE()
const showDeleteModal = ref(false)
const currentTaskId = ref(null)

const handleDelete = (taskId) => {
  currentTaskId.value = taskId
  showDeleteModal.value = true
}

const confirmDelete = () => {
  if (currentTaskId.value) {
    deleteTask(currentTaskId.value)
    showDeleteModal.value = false
  }
}
</script>

<template>
  <div class="container">
    <div class="grid-container">
      <div class="panel">
        <ChatBot />
      </div>
      <div class="panel">
        <TaskPanel :tasks="tasks" @delete="handleDelete" />
      </div>
    </div>

    <div class="panel">
      <HardwareMonitor />
    </div>

    <div class="panel">
      <Sensors />
    </div>

    <DeleteModal :show="showDeleteModal" @confirm="confirmDelete" @cancel="showDeleteModal = false" />

    <div class="footer">
      <p>版权所有 &copy; 2025 Chrom Robot Tech. 保留所有权利。</p>
      <p>Design by TZL.</p>
    </div>
  </div>
</template>

<style scoped>
.container {
  padding: 10px;
  box-sizing: border-box;
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 10px;
  height: 800px;
}

.footer {
  text-align: center;
}

.panel {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
}

/* 移动端适配 */
@media (max-width: 600px) {
  .grid-container {
    grid-template-columns: 1fr;
  }
}
</style>