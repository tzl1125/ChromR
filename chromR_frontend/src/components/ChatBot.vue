<!-- components/ChatBot.vue -->
<script setup>
const chatbotUrl = import.meta.env.VITE_APP_ChatUrl;
</script>

<template>
  <div class="chatbot-container">
    <h2>柱层析机器人对话框</h2>
    <iframe :src="chatbotUrl"></iframe>
  </div>
</template>

<!-- components/ChatBot.vue -->
<style scoped>
h2 {
  margin: 0 0 15px 0;
  color: var(--primary-color);
  text-align: center;
  margin-top: 10px;
}

.chatbot-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  height: 100%;
  padding: 10px;
  box-sizing: border-box;
}

iframe {
  width: 100%;
  border: none;
  padding: 10px;
  border: none;
  height: 100%;
  padding: 10px;
}
</style>