<!-- components/DeleteModal.vue -->
<script setup>
defineProps({
  show: Boolean
})

const emit = defineEmits(['confirm', 'cancel'])
</script>

<template>
  <div v-show="show" class="modal">
    <div class="modal-content">
      <p>确定要删除吗？</p>
      <div class="modal-buttons">
        <button @click="emit('confirm')">确定</button>
        <button @click="emit('cancel')">取消</button>
      </div>
    </div>
  </div>
</template>

<!-- components/DeleteModal.vue -->
<style scoped>
.modal {
    position: fixed;
    z-index: 1;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.4);
}

.modal-content {
    background-color: #fefefe;
    margin: 15% auto;
    padding: 10px;
    border: 1px solid #888;
    width: 250px;
    border-radius: 8px;
    text-align: center;
}

.modal-buttons {
    margin-top: 20px;
    display: flex;
    justify-content: center;
    gap: 80px;
}

button {
    background-color: var(--status-alert);
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s;
}

button:hover {
    background-color: #c0392b;
}

.modal-buttons button:last-child {
    background-color: var(--secondary-color);
}

.modal-buttons button:last-child:hover {
    background-color: #2980b9;
}
</style>