<!-- components/HardwareMonitor.vue -->
<script setup>
import Monitor from './Monitor.vue'
import Hardware from './Hardware.vue'

</script>

<template>
  <div class="hardware-monitor">
    <Monitor />
    <Hardware />
  </div>
</template>


<style scoped>
.hardware-monitor {
  width: 100%;
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 10px;
  padding: 10px;
  min-height: 1000px;
}
</style>
