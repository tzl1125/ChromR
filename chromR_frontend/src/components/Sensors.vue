<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const ServerUrl = import.meta.env.VITE_APP_ServerUrl

// 数据存储
const uvData = ref([])
const nirData = ref([])
const loading = ref(false)
const error = ref(null)
const experimentId = ref(0)
const expIdInput = ref(0)
const uvWavelengths = ref([])
const nirWavelengths = ref([])
const uvInput = ref('256')
const nirInput = ref('950')
let polling = false; // 防止重复启动轮询
let changing = false; // 标记是否正在更改实验 ID
const sensor_lastTimestamp = ref(null);
const uv_lastTimestamp = ref(null);
const nir_lastTimestamp = ref(null);

const sensorData = ref({
  timestamp: [],
  ph: [],
  ph_temperature: [],
  orp: [],
  orp_temperature: [],
  conductivity: [],
  conductivity_temperature: [],
  level: []
})

// 计算选中的波长（根据输入值匹配最接近的可用波长）
const selectedUvWavelengths = computed(() => {
  return parseWavelengthInput(uvInput.value, uvWavelengths.value)
})

const selectedNirWavelengths = computed(() => {
  return parseWavelengthInput(nirInput.value, nirWavelengths.value)
})

// 解析波长输入值，找到最接近的可用波长
function parseWavelengthInput(input, availableWavelengths) {
  if (!input || !availableWavelengths.length) return []

  const inputValues = input.split(',')
    .map(str => parseFloat(str.trim()))
    .filter(val => !isNaN(val))

  if (!inputValues.length) return []

  // 将可用波长转换为浮点数并排序
  const availableFloats = availableWavelengths
    .map(w => parseFloat(w))
    .sort((a, b) => a - b)

  const result = []

  for (const inputVal of inputValues) {
    let closest = null
    let minDiff = Infinity

    for (const num of availableFloats) {
      const diff = Math.abs(num - inputVal)
      if (diff < minDiff) {
        minDiff = diff
        closest = num
      }
    }

    // 只添加在容差范围内的波长
    if (closest !== null ) {
      // 找到原始格式的波长键
      const originalKey = availableWavelengths.find(
        w => Math.abs(parseFloat(w) - closest) < 0.01
      )

      if (originalKey) {
        result.push(originalKey)
      }
    }
  }

  return [...new Set(result)] // 去重
}


// 获取数据并更新图表函数
async function fetchData() {
  let response;
  try {
    // 构建请求 URL，包含 查询 参数
    let url = `${ServerUrl}/data/${experimentId.value}`;
    if (sensor_lastTimestamp.value) {
      url += `?sensor_last_timestamp=${sensor_lastTimestamp.value}`;
    }
    if (uv_lastTimestamp.value) {
      url += `&uv_last_timestamp=${uv_lastTimestamp.value}`;
    }
    if (nir_lastTimestamp.value) {
      url += `&nir_last_timestamp=${nir_lastTimestamp.value}`;
    }
    response = await axios.get(url);
    if (changing) {
      return; // 如果正在更改实验 ID，则不处理数据
    }
    error.value = null;
  } catch (e) {
    if (e.response?.status === 404) {
      error.value = `实验 ID ${experimentId.value} 不存在`;
    } else {
      error.value = '数据加载失败，请稍后再试';
    }
    return;
  } finally {
    changing = false; // 重置更改状态
  }

  const sensors = response.data.sensors || [];
  const uv = response.data.uv || [];
  const nir = response.data.nir || [];

  if (sensors.length === 0 && uv.length === 0 && nir.length === 0) {
    loading.value = false;
    return;
  }
  if (sensors.length > 0) {
    // 更新 sensor_lastTimestamp 为最新数据的时间
    sensor_lastTimestamp.value = sensors[sensors.length - 1].time;
  }
  if (uv.length > 0) {
    // 更新 uv_lastTimestamp 为最新数据的时间
    uv_lastTimestamp.value = uv[uv.length - 1].time;
  }
  if (nir.length > 0) {
    // 更新 nir_lastTimestamp 为最新数据的时间
    nir_lastTimestamp.value = nir[nir.length - 1].time;
  }

  // 提取传感器数据
  const newTimestamps = sensors.map(item => item.time);
  const newPh = sensors.map(item => item.data?.ph?.value ?? null);
  const newPhTemperature = sensors.map(item => item.data?.ph?.temperature ?? null);
  const newOrp = sensors.map(item => item.data?.orp?.value ?? null);
  const newOrpTemperature = sensors.map(item => item.data?.orp?.temperature ?? null);
  const newConductivity = sensors.map(item => item.data?.conductivity?.value ?? null);
  const newConductivityTemperature = sensors.map(item => item.data?.conductivity?.temperature ?? null);
  const newLevel = sensors.map(item => item.data?.level?.value ?? null);

  // 根据实验 ID 是否为 0 决定是否截取最新的 100 条传感器数据
  if (experimentId.value === 0) {
    sensorData.value.timestamp = [...sensorData.value.timestamp, ...newTimestamps].slice(-100);
    sensorData.value.ph = [...sensorData.value.ph, ...newPh].slice(-100);
    sensorData.value.ph_temperature = [...sensorData.value.ph_temperature, ...newPhTemperature].slice(-100);
    sensorData.value.orp = [...sensorData.value.orp, ...newOrp].slice(-100);
    sensorData.value.orp_temperature = [...sensorData.value.orp_temperature, ...newOrpTemperature].slice(-100);
    sensorData.value.conductivity = [...sensorData.value.conductivity, ...newConductivity].slice(-100);
    sensorData.value.conductivity_temperature = [...sensorData.value.conductivity_temperature, ...newConductivityTemperature].slice(-100);
    sensorData.value.level = [...sensorData.value.level, ...newLevel].slice(-100);
  } else {
    sensorData.value.timestamp = [...sensorData.value.timestamp, ...newTimestamps];
    sensorData.value.ph = [...sensorData.value.ph, ...newPh];
    sensorData.value.ph_temperature = [...sensorData.value.ph_temperature, ...newPhTemperature];
    sensorData.value.orp = [...sensorData.value.orp, ...newOrp];
    sensorData.value.orp_temperature = [...sensorData.value.orp_temperature, ...newOrpTemperature];
    sensorData.value.conductivity = [...sensorData.value.conductivity, ...newConductivity];
    sensorData.value.conductivity_temperature = [...sensorData.value.conductivity_temperature, ...newConductivityTemperature];
    sensorData.value.level = [...sensorData.value.level, ...newLevel];
  }

  // 处理光谱数据 - 确保数据格式正确
  const newUvData = uv.map(item => ({
    time: item.time,
    data: typeof item.data === 'string' ? JSON.parse(item.data) : item.data
  }));
  const newNirData = nir.map(item => ({
    time: item.time,
    data: typeof item.data === 'string' ? JSON.parse(item.data) : item.data
  }));

  // 根据实验 ID 是否为 0 决定是否截取最新的 100 条光谱数据
  if (experimentId.value === 0) {
    uvData.value = [...uvData.value, ...newUvData].slice(-100);
    nirData.value = [...nirData.value, ...newNirData].slice(-100);
  } else {
    uvData.value = [...uvData.value, ...newUvData];
    nirData.value = [...nirData.value, ...newNirData];
  }

  if (uvWavelengths.value.length === 0) {
    if (uvData.value.length > 0 && uvData.value[0].data) {
      // 保留原始格式的波长键
      uvWavelengths.value = Object.keys(uvData.value[0].data)
    }
  }
  if (nirWavelengths.value.length === 0) {
    if (nirData.value.length > 0 && nirData.value[0].data) {
      // 保留原始格式的波长键
      nirWavelengths.value = Object.keys(nirData.value[0].data)
    }
  }
  updateCharts();
  loading.value = false;
}

// 更新所有图表
function updateCharts() {
  updateSensorCharts()
  updateSpectraCharts()
}

// 更新传感器图表
function updateSensorCharts() {
  const timestamps = sensorData.value.timestamp || []

  // pH 值图表
  updateChart('phChart', {
    title: 'pH 值',
    series: [
      { name: 'pH值', data: sensorData.value.ph || [] }
    ],
    timestamps,
    color: '#5470C6',
    unit: ''
  })

  // ORP 值图表
  updateChart('orpChart', {
    title: 'ORP 值',
    series: [
      { name: 'ORP值mV', data: sensorData.value.orp || [] }
    ],
    timestamps,
    color: '#91CC75',
    unit: 'mV'
  })

  // 电导率图表
  updateChart('conductivityChart', {
    title: '电导率',
    series: [
      { name: '电导率ms/cm', data: sensorData.value.conductivity || [] }
    ],
    timestamps,
    color: '#FAC858',
    unit: 'ms/cm'
  })

  // 液位图表
  updateChart('levelChart', {
    title: '液位',
    series: [
      { name: '液位mm', data: sensorData.value.level || [] }
    ],
    timestamps,
    color: '#EE6666',
    unit: 'mm'
  })

  // 温度图表（合并所有温度）
  updateChart('temperatureChart', {
    title: '温度',
    series: [
      { name: 'pH温度℃', data: sensorData.value.ph_temperature || [] },
      { name: 'ORP温度℃', data: sensorData.value.orp_temperature || [] },
      { name: '电导率温度℃', data: sensorData.value.conductivity_temperature || [] }
    ],
    timestamps,
    color: '#EE6666',
    unit: '℃'
  })
}

// 更新光谱图表
function updateSpectraCharts() {
  // UV 光谱图表
  updateSpectrumChart('uvChart', {
    title: '紫外光谱数据',
    data: uvData.value,
    wavelengths: selectedUvWavelengths.value,
    color: '#5470C6'
  })

  // NIR 光谱图表
  updateSpectrumChart('nirChart', {
    title: '近红外光谱数据',
    data: nirData.value,
    wavelengths: selectedNirWavelengths.value,
    color: '#91CC75'
  })
}

// 通用图表更新函数
function updateChart(chartId, config) {
  const container = document.getElementById(chartId)
  if (!container) return

  let chartInstance = echarts.getInstanceByDom(container)
  if (!chartInstance) {
    chartInstance = echarts.init(container)
  }

  const option = {
    title: {
      text: config.title,
      left: 'center',
      textStyle: {
        fontSize: 14
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: config.series.map(s => s.name),
      top: 20
    },
    grid: {
      top: '20%',
      bottom: '10%',
      left: '5%',
      right: '5%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: config.timestamps.map(t => formatTime(t)),
      boundaryGap: false,
      axisLabel: {
        rotate: 45,
        formatter: function (value) {
          return value.split(' ')[1]; // 只显示时间部分 (HH:mm:ss)
        }
      }
    },
    yAxis: {
      type: 'value',
      name: config.unit,
      scale: true
    },
    dataZoom: [{
      type: 'inside',
      start: 0,
      end: 100
    }, {
      type: 'slider',
      start: 0,
      end: 100,
      height: 20,
      bottom: 0
    }],
    series: config.series.map((item, index) => ({
      name: item.name,
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2 },
      color: config.color ? [config.color, '#73C0DE', '#FAC858'][index % 3] : null,
      data: item.data
    }))
  }

  chartInstance.setOption(option, true)
  window.addEventListener('resize', () => chartInstance.resize())
}

// 光谱图表更新函数
function updateSpectrumChart(chartId, config) {
  const container = document.getElementById(chartId)
  if (!container) return

  let chartInstance = echarts.getInstanceByDom(container)
  if (!chartInstance) {
    chartInstance = echarts.init(container)
  }

  // 提取时间戳
  const timestamps = config.data.map(item => formatTime(item.time))

  // 为每个选中的波长创建系列
  const series = config.wavelengths.map(wavelength => ({
    name: `${wavelength}nm`,
    type: 'line',
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 2 },
    data: config.data.map(item => {
      // 确保数据存在且是对象
      if (item.data && typeof item.data === 'object') {
        return item.data[wavelength] !== undefined ? item.data[wavelength] : null;
      }
      return null
    })
  }))

  const option = {
    title: {
      text: config.title,
      left: 'center',
      textStyle: {
        fontSize: 14
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: series.map(s => s.name),
      top: 20
    },
    grid: {
      top: '15%',
      bottom: '10%',
      left: '5%',
      right: '5%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: timestamps,
      boundaryGap: false,
      axisLabel: {
        rotate: 45,
        formatter: function (value) {
          return value.split(' ')[1]; // 只显示时间部分 (HH:mm:ss)
        }
      }
    },
    yAxis: {
      type: 'value',
      name: '吸光度(mAU)',
      scale: true
    },
    dataZoom: [{
      type: 'inside',
      start: 0,
      end: 100
    }, {
      type: 'slider',
      start: 0,
      end: 100,
      height: 20,
      bottom: 0
    }],
    series: series
  }

  chartInstance.setOption(option, true)
  window.addEventListener('resize', () => chartInstance.resize())
}

// 格式化时间显示 (YYYY-MM-DD HH:mm:ss)
function formatTime(fullTime) {
  if (!fullTime) return ''
  const date = new Date(fullTime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).replace(/\//g, '-')
}

async function startPolling() {
  if (polling) return;
  polling = true;

  while (polling) {
    await fetchData(); // 等待本次请求完成
    if (polling) {
      await new Promise(resolve => setTimeout(resolve, 3000)); // 每次请求后等待 3 秒
    }
  }
}

function stopPolling() {
  polling = false;
}

// 切换实验ID时重新加载
function handleExperimentChange() {
  changing = true;
  loading.value = true;
  error.value = null;
  experimentId.value = expIdInput.value;
  sensorData.value = {
    timestamp: [],
    ph: [],
    ph_temperature: [],
    orp: [],
    orp_temperature: [],
    conductivity: [],
    conductivity_temperature: [],
    level: []
  }
  uvData.value = []
  nirData.value = []
  sensor_lastTimestamp.value = null;
  uv_lastTimestamp.value = null;
  nir_lastTimestamp.value = null;
}

// 更新 UV 光谱图表
function updateUvChart() {
  updateSpectrumChart('uvChart', {
    title: '紫外光谱数据',
    data: uvData.value,
    wavelengths: selectedUvWavelengths.value,
    color: '#5470C6'
  })
}

// 更新 NIR 光谱图表
function updateNirChart() {
  updateSpectrumChart('nirChart', {
    title: '近红外光谱数据',
    data: nirData.value,
    wavelengths: selectedNirWavelengths.value,
    color: '#91CC75'
  })
}

// 初始化：组件挂载时启动轮询
onMounted(() => {
  startPolling();
});

// 清除定时器：组件卸载前停止轮询
onBeforeUnmount(() => {
  stopPolling();
});
</script>

<template>
  <div class="dashboard">
    <div class="header">
      <h1>📈​ 传感器和光谱数据</h1>
      <div class="controls">
        <label for="experiment-id">实验 ID：</label>
        <input id="experiment-id" type="number" v-model.number="expIdInput" min="0" placeholder="输入实验 ID" />
        <button @click="handleExperimentChange">查询</button>
      </div>
    </div>

    <div v-show="!error && loading" class="loading">加载中...</div>
    <div v-show="error" class="error">{{ error }}</div>
    <div v-show="!error && !loading">
      <div class="sensor-grid">
        <!-- pH 值 -->
        <div class="chart-container">
          <div id="phChart" class="chart"></div>
        </div>

        <!-- ORP 值 -->
        <div class="chart-container">
          <div id="orpChart" class="chart"></div>
        </div>

        <!-- 电导率 -->
        <div class="chart-container">
          <div id="conductivityChart" class="chart"></div>
        </div>

        <!-- 液位 -->
        <div class="chart-container">
          <div id="levelChart" class="chart"></div>
        </div>

        <!-- 温度 -->
        <div class="chart-container">
          <div id="temperatureChart" class="chart"></div>
        </div>
      </div>


      <!-- 紫外光谱部分 -->
      <div class="chart-container">
        <div class="wavelength-input">
          <h3>紫外光谱波长 (nm)</h3>
          <p class="hint">输入波长值（多个用逗号分隔），将自动匹配最接近的波长</p>
          <div style="display: flex; align-items: left; flex-direction: row;">
            <input type="text" v-model="uvInput" placeholder="190-380, 例如: 200, 300" style="flex: 5;" />
            <button @click="updateUvChart" style="margin-left: 10px; flex: 1;">确认</button>
          </div>
          <div class="available-info" v-if="uvWavelengths.length">
            可用波长范围: {{ uvWavelengths[0] }} - {{ uvWavelengths[uvWavelengths.length - 1] }} nm
          </div>
        </div>
        <div id="uvChart" class="chart"></div>
      </div>

      <!-- 近红外光谱部分 -->
      <div class="chart-container">
        <div class="wavelength-input">
          <h3>近红外光谱波长 (nm)</h3>
          <p class="hint">输入波长值（多个用逗号分隔），将自动匹配最接近的波长</p>
          <div style="display: flex; align-items: left;flex-direction: row;">
            <input type="text" v-model="nirInput" placeholder="900-1700, 例如: 900, 1000" style="flex: 5;" />
            <button @click="updateNirChart" style="margin-left: 10px; flex: 1;">确认</button>
          </div>
          <div class="available-info" v-show="nirWavelengths.length">
            可用波长范围: {{ nirWavelengths[0] }} - {{ nirWavelengths[nirWavelengths.length - 1] }} nm
          </div>
        </div>
        <div id="nirChart" class="chart"></div>
      </div>
    </div>
  </div>

</template>

<style scoped>
.dashboard {
  padding: 20px;
  max-width: 1800px;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #eee;
}

.header h1 {
  margin: 0;
  color: #2c3e50;
  font-size: 24px;
}

.controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.controls input {
  width: 120px;
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  transition: border-color 0.3s;
}

.controls input:focus {
  border-color: #409eff;
  outline: none;
}

.controls button {
  padding: 8px 16px;
  background-color: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
  font-weight: 500;
}

.controls button:hover {
  background-color: #66b1ff;
}

.loading,
.error {
  padding: 20px;
  text-align: center;
  margin: 20px 0;
  border-radius: 4px;
  font-size: 16px;
}

.loading {
  background-color: #f4f4f5;
  color: #909399;
}

.error {
  background-color: #fef0f0;
  color: #f56c6c;
}

.sensor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}



.wavelength-input {
  flex: 1;
}

.wavelength-input h3 {
  margin-top: 0;
  margin-bottom: 8px;
  color: #606266;
  font-size: 20px;
}

.hint {
  color: #909399;
  font-size: 16px;
  margin-top: 0;
  margin-bottom: 8px;
}

.wavelength-input input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  transition: border-color 0.3s;
  font-size: 14px;
}

.wavelength-input input:focus {
  border-color: #409eff;
  outline: none;
}

.wavelength-input button {
  padding: 8px 16px;
  background-color: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
  font-weight: 500;
}

.wavelength-input button:hover {
  background-color: #66b1ff;
}

.available-info {
  width: 100%;
  margin-top: 10px;
  color: #909399;
}

.chart-container {
  background-color: #fff;
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  padding: 15px;
  transition: box-shadow 0.3s;
  display: flex;
  margin-bottom: 20px;
}

.chart-container:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.chart {
  width: 100%;
  height: 300px;
  flex: 4;
}
</style>