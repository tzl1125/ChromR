<!-- components/TaskPanel.vue -->
<script setup>
import { ref } from 'vue'

const props = defineProps({
  tasks: Array
})

const emit = defineEmits(['delete'])
const expandedTask = ref(null)
const ServerUrl = import.meta.env.VITE_APP_ServerUrl

const toggleDetails = (taskId) => {
  expandedTask.value = expandedTask.value === taskId ? null : taskId
}
function downloadFile(result) {
    const url = new URL(`${ServerUrl}/download`);
    url.searchParams.append('file_name', result); 
    
    const newWindow = window.open(url.toString(), '_blank');

    if (newWindow) {
        const checkInterval = setInterval(() => {
            if (newWindow.closed) {
                clearInterval(checkInterval);
            } else if (newWindow.document.readyState === 'complete') {
                // 有些浏览器可能不允许自动关闭窗口，需要用户手动关闭
                try {
                    newWindow.close();
                } catch (e) {
                    console.log('无法自动关闭窗口，请手动关闭');
                }
                clearInterval(checkInterval);
            }
        }, 1000);
    }
}
</script>

<template>
  <div class="panel-section">
    <h2>任务运行情况</h2>
    <div class="scroll-container">
      <table>
        <thead>
          <tr>
            <th style="width: 15%">任务序号</th>
            <th style="width: 20%">任务提交时间</th>
            <th style="width: 30%">任务名称</th>
            <th style="width: 15%">状态</th>
            <th style="width: 15%">操作</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(task, index) in tasks" :key="task.id">
            <tr class="task-row" @click="toggleDetails(index + 1)">
              <td>{{ index + 1 }}</td>
              <td>{{ task.time }}</td>
              <td>{{ task.name }}</td>
              <td>
                <span :class="`task-status-${task.status === '已完成' ? 'completed' :
                  task.status === '失败' ? 'failed' : 'running'}`">
                  {{ task.status }}
                </span>
              </td>
              <td>
                <button @click.stop="emit('delete', task.id)" class="delete-btn">删除</button>
              </td>
            </tr>
            <tr v-show="expandedTask === index + 1" class="task-detail">
              <td colspan="5" style="text-align: left;">
                <p><strong>任务ID:</strong> {{ task.id }}</p>
                <p><strong>描述:</strong> {{ task.description }}</p>
                <p><strong>结果:</strong>
                  <span v-if="task.status === '已完成'">
                    <a @click.prevent="downloadFile(task.result)" href="#">点击下载</a>
                  </span>
                  <span v-else-if="task.status === '失败'">{{ task.result }}</span>
                </p>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<!-- components/TaskPanel.vue -->
<style scoped>
h2 {
  margin: 0 0 15px 0;
  color: var(--primary-color);
  text-align: center;
  margin-top: 10px;
}

.panel-section {
  background: white;
  border-radius: 8px;
  padding: 10px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
}

th {
  background: var(--primary-color);
  color: var(--text-light);
  padding: 12px;
  position: sticky;
  top: 0;
}

tr:nth-child(even) {
  background-color: #f8f9fa;
}

td {
  padding: 12px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  text-align: center;
}

.task-status-running {
  background: var(--status-running);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
}

.task-status-failed {
  background: var(--status-alert);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
}

.task-status-completed {
  background: var(--status-completed);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
}

.task-detail {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 6px;
  animation: fadeIn 0.3s ease-out;
}

tr:hover td {
  background: #e9ecef;
}

/* 删除按钮样式 */
.delete-btn {
  padding: 6px 12px;
  font-size: 14px;
  color: white;
  background-color: #e74c3c;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s ease;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 5px;
  padding-left: 5px;
}

.scroll-container::-webkit-scrollbar {
  width: 8px;
}

.scroll-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.scroll-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.delete-btn:hover {
  background-color: #c0392b;
}
</style>