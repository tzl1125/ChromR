<!-- components/Hardware.vue -->
<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import axios from 'axios'

const ServerUrl = import.meta.env.VITE_APP_ServerUrl
const videoUrl = import.meta.env.VITE_APP_VideoUrl
let HardwareUrl = ref('')
let pump_state = ref({})
let valve_state = ref({})
let uv_state = ref({})
let nir_state = ref({})
let eventSource = null

// 状态变量
let experimentId = ref(0)
let currentStage = ref(null)
let equilibriumStatus = ref({
    sensors: { ph: false, orp: false, conductivity: false },
    spectra: { uv: false, nir: false }
})

// 原始参数和修改标记
let originalParams = ref(null)
let modifiedParams = ref({})

// 参数设置表单
let paramsForm = ref({
    sample_span_run: 5,
    sample_span_stop: 600,
    lc_span: 1,
    equilibrium_check_span: 20,
    spectral_threshold: 0.05,
    pca_components: 5,
    sensor_thresholds: {
        ph: { rel: 0.03, abs: 0.02, slope: 0.001 },
        orp: { rel: 0.08, abs: 5, slope: 0.1 },
        conductivity: { rel: 0.05, abs: 1, slope: 0.05 }
    },
    stage_constraints: {
        equilibrate: {
            ph: [5, 7.5],
            conductivity: [0, 1]
        },
        refresh: {
            ph: [6, 7.5],
            conductivity: [1, 1e5]
        }
    }
})


// 计算属性：是否正在实验
const isExperimentRunning = computed(() => {
    return experimentId.value !== 0 && experimentId.value !== null
})

// 计算属性：是否处于平衡阶段
const isEquilibriumStage = computed(() => {
    return currentStage.value === 'equilibrate' || currentStage.value === 'refresh'
})

// 计算属性：传感器是否全部稳定
const allSensorsStable = computed(() => {
    return Object.values(equilibriumStatus.value.sensors).every(val => val)
})

// 计算属性：光谱是否全部稳定
const allSpectraStable = computed(() => {
    return Object.values(equilibriumStatus.value.spectra).every(val => val)
})

// 计算属性：是否达到平衡
const isEquilibriumReached = computed(() => {
    return allSensorsStable.value && allSpectraStable.value
})

const expandedPump = ref(null)
const expandedValve = ref(null)
const expandedSpectrum = ref(null)
const expandedParams = ref(false)  // 参数面板展开状态
let pumpAddress = ref('')
let pumpType = ref('')
let pumpValue = ref('')

let valveAddress = ref('')
let valveType = ref('')
let valveValue = ref('')

let spectrumType = ref('uv')
let spectrumControlType = ref('')
let spectrumControlValue = ref('')

const toggleDetailsPump = (id) => {
    expandedPump.value = expandedPump.value === id ? null : id
}

const toggleDetailsValve = (id) => {
    expandedValve.value = expandedValve.value === id ? null : id
}

const toggleDetailsSpectrum = (name) => {
    expandedSpectrum.value = expandedSpectrum.value === name ? null : name
}

// 切换参数面板
const toggleParamsPanel = () => {
    expandedParams.value = !expandedParams.value
}

// 递归检查所有嵌套属性的变化，生成完整路径
const checkDifferences = (newVal, originalVal, currentPath = '') => {
    // 如果当前值是对象/数组且原始值存在，才递归检查
    if (typeof newVal === 'object' && newVal !== null && originalVal !== undefined) {
        const keys = Object.keys(newVal)
        keys.forEach(key => {
            // 生成当前属性的完整路径（如"sensor_thresholds.ph"）
            const fullPath = currentPath ? `${currentPath}.${key}` : key
            // 递归检查子属性
            checkDifferences(newVal[key], originalVal[key], fullPath)
        })
    } else {
        // 非对象类型，直接比较值（用JSON.stringify确保数组/基本类型都能比较）
        if (currentPath && JSON.stringify(newVal) !== JSON.stringify(originalVal)) {
            modifiedParams.value[currentPath] = true
        } else if (currentPath) {
            delete modifiedParams.value[currentPath]
        }
    }
}

// 监视参数变化并标记修改
watch(paramsForm, (newValue) => {
    if (!originalParams.value) return

    // 清空之前的标记，重新检查所有路径
    modifiedParams.value = {}
    // 从根路径开始递归检查
    checkDifferences(newValue, originalParams.value)
}, { deep: true })

// 检查参数是否被修改
const isParamModified = (path) => {
    return modifiedParams.value[path] || false
}

const resetParams = () => {
    // 重置参数表单为原始值
    paramsForm.value = JSON.parse(JSON.stringify(originalParams.value))
}

// 获取系统参数
async function fetchSystemParams() {
    try {
        const response = await axios.get(`${HardwareUrl.value}/query/params`)
        originalParams.value = JSON.parse(JSON.stringify(response.data))
        paramsForm.value = response.data
    } catch (error) {
        console.error('获取系统参数失败:', error)
        alert('获取系统参数失败，请检查连接')
    }
}

// 发送参数设置
async function sendParams() {
    // 处理modifiedParams的嵌套路径，提取顶层类型（去重）
    const modifiedPaths = Object.keys(modifiedParams.value);
    if (modifiedPaths.length === 0) {
        alert('没有修改任何参数');
        return;
    }

    // 提取顶层类型（如从"sensor_thresholds.ph.rel"中提取"sensor_thresholds"）
    const modifiedTypes = [...new Set(
        modifiedPaths.map(path => path.split('.')[0])
    )];

    // 辅助函数：根据参数类型转换值的类型（确保数字类型正确）
    const convertParamValue = (type, value) => {
        switch (type) {
            // 基础数字类型参数
            case 'sample_span_run':
            case 'sample_span_stop':
            case 'lc_span':
            case 'equilibrium_check_span':
            case 'spectral_threshold':
                return parseFloat(value);
            // 整数类型参数
            case 'pca_components':
                return parseInt(value, 10);
            // 嵌套对象：传感器阈值
            case 'sensor_thresholds':
                return {
                    ph: {
                        rel: parseFloat(value.ph.rel),
                        abs: parseFloat(value.ph.abs),
                        slope: parseFloat(value.ph.slope)
                    },
                    orp: {
                        rel: parseFloat(value.orp.rel),
                        abs: parseFloat(value.orp.abs),
                        slope: parseFloat(value.orp.slope)
                    },
                    conductivity: {
                        rel: parseFloat(value.conductivity.rel),
                        abs: parseFloat(value.conductivity.abs),
                        slope: parseFloat(value.conductivity.slope)
                    }
                };
            // 嵌套对象：阶段约束
            case 'stage_constraints':
                return {
                    equilibrate: {
                        ph: [
                            parseFloat(value.equilibrate.ph[0]),
                            parseFloat(value.equilibrate.ph[1])
                        ],
                        conductivity: [
                            parseFloat(value.equilibrate.conductivity[0]),
                            parseFloat(value.equilibrate.conductivity[1])
                        ]
                    },
                    refresh: {
                        ph: [
                            parseFloat(value.refresh.ph[0]),
                            parseFloat(value.refresh.ph[1])
                        ],
                        conductivity: [
                            parseFloat(value.refresh.conductivity[0]),
                            parseFloat(value.refresh.conductivity[1])
                        ]
                    }
                };
            default:
                return value;
        }
    };

    try {
        // 为每个顶层类型发送完整对象
        const requests = modifiedTypes.map(type => {
            // 获取该类型的完整对象并转换
            const convertedValue = convertParamValue(type, paramsForm.value[type]);
            console.log(`发送参数 - type: ${type}, value:`, convertedValue);

            // 发送请求：使用顶层类型作为type，发送完整转换后的对象
            return axios.post(`${HardwareUrl.value}/control/params`, {
                type: type,
                value: convertedValue
            });
        });

        // 等待所有请求完成
        await Promise.all(requests);
        alert('所有参数更新成功');

        // 更新原始参数快照并清空修改标记
        originalParams.value = JSON.parse(JSON.stringify(paramsForm.value));
        modifiedParams.value = {};
    } catch (error) {
        console.error('参数更新失败详情:', error.response?.data?.detail);
        alert(`参数更新失败: ${error.response?.data?.detail?.[0]?.msg || '数据格式错误'}`);
    }
}


// 跳过当前阶段
async function skipCurrentStage() {
    try {
        const response = await axios.post(`${HardwareUrl.value}/control/skip_stage`)
        alert(response.data.result)
    } catch (error) {
        alert('跳过阶段失败')
        console.error(error)
    }
}


async function sendPumpCommand() {
    // 原有的泵控制逻辑
    const addressInput = pumpAddress.value
    const type = pumpType.value
    const valueInput = pumpValue.value

    let addresses = []

    // 处理地址部分
    if (addressInput === 'all') {
        addresses = 'all'
    } else {
        try {
            addresses = addressInput.split(',')
                .map(s => parseInt(s.trim(), 10))
                .filter(n => !isNaN(n))
            if (addresses.length === 0) {
                alert('请输入合法的地址或填写 "all"')
                return
            }
        } catch (e) {
            alert('地址格式错误')
            return
        }
    }

    // 处理控制值
    let value = null

    if (type === 'speed') {
        // 转速必须为大于0的浮点数
        const num = parseFloat(valueInput)
        if (isNaN(num) || num < 0 || num > 400) {
            alert('转速必须是 0 到 400 之间的数字')
            return
        }
        value = num
    } else if (type === 'alias') {
        // 别名可以是任意字符串
        if (valueInput.trim() === '') {
            alert('别名不能为空')
            return
        }
        value = valueInput.trim()
    } else {
        // 其他类型都为布尔值
        if (valueInput.toLowerCase() === 'true' || valueInput === '1') {
            value = true
        } else if (valueInput.toLowerCase() === 'false' || valueInput === '0') {
            value = false
        } else {
            alert('布尔值请输入 true/false 或 1/0')
            return
        }
    }

    // 构造请求体
    const payload = {
        type,
        value,
        pump_ids: addresses
    }

    // 发送请求
    try {
        const response = await axios.post(`${HardwareUrl.value}/control/pump`, payload)
        alert(response.data.result)
    } catch (error) {
        alert('操作失败，请查看日志')
        console.error(error)
    }
}

async function sendValveCommand() {
    // 原有的阀门控制逻辑
    const addressInput = valveAddress.value.trim()
    const type = valveType.value
    const valueInput = type === 'alias' ? valveValue.value : parseFloat(valveValue.value);
    let addresses = []

    // 校验地址部分
    if (addressInput === 'all') {
        addresses = 'all'
    } else {
        try {
            addresses = addressInput.split(',')
                .map(s => parseInt(s.trim(), 10))
                .filter(n => !isNaN(n))
            if (addresses.length === 0) {
                alert('请输入合法的地址或填写 "all"')
                return
            }
        } catch (e) {
            alert('地址格式错误')
            return
        }
    }
    if (type === "opening" && (isNaN(valueInput) || valueInput < 0 || valueInput > 100)) {
        alert('开度必须是 0 到 100 之间的数字')
        return
    } else if (type === "alias" && valueInput.trim() === '') {
        alert('别名不能为空')
        return
    }


    // 构造请求体
    const payload = {
        type,
        value: valueInput,
        valve_ids: addresses
    }

    // 发送请求
    try {
        const response = await axios.post(`${HardwareUrl.value}/control/valve`, payload)
        alert(response.data.result)
    } catch (error) {
        alert('操作失败，请查看日志')
        console.error(error)
    }
}

async function sendSpectrumCommand() {
    const type = spectrumControlType.value
    const valueInput = spectrumControlValue.value

    let value = null

    if (type === "lamp") {
        if (valueInput.toLowerCase() === 'true' || valueInput === '1') {
            value = true
        } else if (valueInput.toLowerCase() === 'false' || valueInput === '0') {
            value = false
        } else {
            alert('布尔值请输入 true/false 或 1/0')
            return
        }
    } else if (type === "average_times" || type === "integration_time") {
        const num = parseInt(valueInput)
        if (isNaN(num) || num < 0) {
            alert('请输入有效的正整数')
            return
        }
        value = num
    }

    const payload = {
        type,
        value
    }

    try {
        let url = ''
        if (spectrumType.value === 'uv') {
            url = `${HardwareUrl.value}/control/uv`
        } else if (spectrumType.value === 'nir') {
            url = `${HardwareUrl.value}/control/nir`
        }
        const response = await axios.post(url, payload)
        alert(response.data.result)
    } catch (error) {
        alert('操作失败，请查看日志')
        console.error(error)
    }
}

// 从后端API获取HardwareUrl
const getHardwareUrl = async () => {
    try {
        // 使用 axios 发送 GET 请求
        const response = await axios.get(`${ServerUrl}/hardware-ip`)
        return response.data.result
    } catch (error) {
        console.error('获取硬件URL失败:', error.response?.data || error.message)
        return null
    }
}

onMounted(async () => {
    let hardware_ip = await getHardwareUrl()
    HardwareUrl.value = `http://${hardware_ip}:8100`
    console.log('获取到的硬件URL:', HardwareUrl.value)
    // 获取系统参数
    await fetchSystemParams()

    if (HardwareUrl.value) {
        eventSource = new EventSource(`${HardwareUrl.value}/sse`)

        eventSource.onmessage = (e) => {
            const data = JSON.parse(e.data)
            pump_state.value = data.pump
            valve_state.value = data.valve
            uv_state.value = data.uv
            nir_state.value = data.nir

            // 更新实验状态
            experimentId.value = data.experiment_id
            currentStage.value = data.current_stage

            // 更新平衡状态
            if (data.equilibrium_status) {
                equilibriumStatus.value = data.equilibrium_status
            }
        }
    } else {
        console.error('无法创建EventSource，硬件URL获取失败')
    }
})

onBeforeUnmount(() => {
    eventSource?.close()
})

// 添加计算速度百分比的方法
function calculateSpeedPercentage(speed) {
    // 最大转速为400 RPM
    const maxSpeed = 400;
    return Math.min(100, Math.max(0, (speed / maxSpeed) * 100));
}

</script>
<template>
    <div>
        <h2>💻 硬件控制系统</h2>
        <!-- 实验状态显示面板 -->
        <div class="status-panel">
            <div class="experiment-status">
                <span class="status-label">实验状态:</span>
                <span v-if="isExperimentRunning" class="status-value running">
                    <span class="status-icon">🔴</span> 进行中 (ID: {{ experimentId }})
                </span>
                <span v-else class="status-value stopped">
                    <span class="status-icon">🟢</span> 未运行
                </span>

                <span v-if="isExperimentRunning" class="stage-info">
                    | 当前阶段: <span class="stage-value">{{ currentStage }}</span>
                </span>

                <button v-if="isExperimentRunning" class="skip-btn" @click="skipCurrentStage">
                    ⏭️ 跳过当前阶段
                </button>
            </div>

            <!-- 平衡状态监测部分 -->
            <div v-if="isExperimentRunning && isEquilibriumStage" class="equilibrium-status">
                <h3 class="equilibrium-title">平衡状态监测</h3>
                <div class="equilibrium-container">
                    <!-- 传感器平衡状态 -->
                    <div class="equilibrium-card">
                        <div class="card-header">
                            <span class="card-icon">📊</span>
                            <h4 class="card-title">传感器状态</h4>
                        </div>
                        <div class="card-content">
                            <div class="status-item" v-for="(stable, sensor) in equilibriumStatus.sensors"
                                :key="sensor">
                                <span class="status-label">{{ sensor }}:</span>
                                <span :class="['status-value', stable ? 'stable' : 'unstable']">
                                    {{ stable ? '稳定 ✅' : '不稳定 ❌' }}
                                </span>
                            </div>
                            <div class="status-summary">
                                <span class="summary-label">整体:</span>
                                <span :class="['summary-value', allSensorsStable ? 'stable' : 'unstable']">
                                    {{ allSensorsStable ? '稳定 ✅' : '不稳定 ❌' }}
                                </span>
                            </div>
                        </div>
                    </div>

                    <!-- 光谱平衡状态 -->
                    <div class="equilibrium-card">
                        <div class="card-header">
                            <span class="card-icon">🌈</span>
                            <h4 class="card-title">光谱状态</h4>
                        </div>
                        <div class="card-content">
                            <div class="status-item">
                                <span class="status-label">UV:</span>
                                <span :class="['status-value', equilibriumStatus.spectra.uv ? 'stable' : 'unstable']">
                                    {{ equilibriumStatus.spectra.uv ? '稳定 ✅' : '不稳定 ❌' }}
                                </span>
                            </div>
                            <div class="status-item">
                                <span class="status-label">NIR:</span>
                                <span :class="['status-value', equilibriumStatus.spectra.nir ? 'stable' : 'unstable']">
                                    {{ equilibriumStatus.spectra.nir ? '稳定 ✅' : '不稳定 ❌' }}
                                </span>
                            </div>
                            <div class="status-summary">
                                <span class="summary-label">整体:</span>
                                <span :class="['summary-value', allSpectraStable ? 'stable' : 'unstable']">
                                    {{ allSpectraStable ? '稳定 ✅' : '不稳定 ❌' }}
                                </span>
                            </div>
                        </div>
                    </div>

                    <!-- 平衡状态总结 -->
                    <div class="equilibrium-card summary-card">
                        <div class="card-header">
                            <span class="card-icon">⚖️</span>
                            <h4 class="card-title">平衡总状态</h4>
                        </div>
                        <div class="card-content summary-content">
                            <div :class="['final-status', isEquilibriumReached ? 'reached' : 'not-reached']">
                                {{ isEquilibriumReached ? '已平衡 ✅' : '未平衡 ❌' }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 参数设置面板 -->
        <div class="params-panel">
            <div class="params-header" @click="toggleParamsPanel">
                <h3>⚙️ 系统参数设置</h3>
                <span class="toggle-icon">{{ expandedParams ? '收起 ▼' : '展开 ▲' }}</span>
            </div>

            <transition name="slide-down">
                <div v-show="expandedParams" class="params-content">
                    <div class="params-grid">
                        <!-- 系统运行参数 -->
                        <div class="param-section">
                            <h4 class="section-title">🔄 系统运行参数</h4>
                            <div class="param-row">
                                <div class="param-group">
                                    <label>实验时采样间隔 (秒):</label>
                                    <input type="number" v-model="paramsForm.sample_span_run" min="1" step="0.5"
                                        :class="{ 'modified': isParamModified('sample_span_run') }">
                                </div>

                                <div class="param-group">
                                    <label>非实验时采样间隔 (秒):</label>
                                    <input type="number" v-model="paramsForm.sample_span_stop" min="10" step="10"
                                        :class="{ 'modified': isParamModified('sample_span_stop') }">
                                </div>
                            </div>

                            <div class="param-row">
                                <div class="param-group">
                                    <label>液位控制间隔 (秒):</label>
                                    <input type="number" v-model="paramsForm.lc_span" min="0.1" step="0.1"
                                        :class="{ 'modified': isParamModified('lc_span') }">
                                </div>
                            </div>
                        </div>

                        <!-- 平衡检查参数 -->
                        <div class="param-section">
                            <h4 class="section-title">⚖️ 平衡检查参数</h4>

                            <!-- 平衡时间窗口 -->
                            <div class="sub-section">
                                <h5 class="sub-title">⏱️ 平衡时间窗口</h5>
                                <div class="param-row">
                                    <div class="param-group">
                                        <label>平衡检查窗口 (分钟):</label>
                                        <input type="number" v-model="paramsForm.equilibrium_check_span" min="1"
                                            step="1" :class="{ 'modified': isParamModified('equilibrium_check_span') }">
                                    </div>
                                </div>
                            </div>
                            <!-- 光谱稳定性参数 -->
                            <div class="sub-section">
                                <h5 class="sub-title">🌈 光谱稳定性参数设置</h5>
                                <div class="param-row">
                                    <div class="param-group">
                                        <label>光谱稳定性阈值:</label>
                                        <input type="number" v-model="paramsForm.spectral_threshold" min="0.01"
                                            step="0.01" :class="{ 'modified': isParamModified('spectral_threshold') }">
                                    </div>

                                    <div class="param-group">
                                        <label>光谱稳定性PCA主成分数量:</label>
                                        <input type="number" v-model="paramsForm.pca_components" min="1" max="20"
                                            step="1" :class="{ 'modified': isParamModified('pca_components') }">
                                    </div>
                                </div>
                            </div>

                            <!-- 传感器阈值设置 -->
                            <div class="sub-section">
                                <h5 class="sub-title">📊 传感器阈值设置</h5>
                                <div class="threshold-grid">
                                    <div class="threshold-header">传感器</div>
                                    <div class="threshold-header">相对阈值</div>
                                    <div class="threshold-header">绝对阈值</div>
                                    <div class="threshold-header">斜率阈值</div>

                                    <!-- pH -->
                                    <div>pH</div>
                                    <input type="number" v-model="paramsForm.sensor_thresholds.ph.rel" min="0"
                                        step="0.01"
                                        :class="{ 'modified': isParamModified('sensor_thresholds.ph.rel') }">
                                    <input type="number" v-model="paramsForm.sensor_thresholds.ph.abs" min="0"
                                        step="0.01"
                                        :class="{ 'modified': isParamModified('sensor_thresholds.ph.abs') }">
                                    <input type="number" v-model="paramsForm.sensor_thresholds.ph.slope" min="0"
                                        step="0.0001"
                                        :class="{ 'modified': isParamModified('sensor_thresholds.ph.slope') }">

                                    <!-- ORP -->
                                    <div>ORP</div>
                                    <input type="number" v-model="paramsForm.sensor_thresholds.orp.rel" min="0"
                                        step="0.01"
                                        :class="{ 'modified': isParamModified('sensor_thresholds.orp.rel') }">
                                    <input type="number" v-model="paramsForm.sensor_thresholds.orp.abs" min="0"
                                        step="0.1"
                                        :class="{ 'modified': isParamModified('sensor_thresholds.orp.abs') }">
                                    <input type="number" v-model="paramsForm.sensor_thresholds.orp.slope" min="0"
                                        step="0.01"
                                        :class="{ 'modified': isParamModified('sensor_thresholds.orp.slope') }">

                                    <!-- 电导率 -->
                                    <div>电导率</div>
                                    <input type="number" v-model="paramsForm.sensor_thresholds.conductivity.rel" min="0"
                                        step="0.01"
                                        :class="{ 'modified': isParamModified('sensor_thresholds.conductivity.rel') }">
                                    <input type="number" v-model="paramsForm.sensor_thresholds.conductivity.abs" min="0"
                                        step="0.1"
                                        :class="{ 'modified': isParamModified('sensor_thresholds.conductivity.abs') }">
                                    <input type="number" v-model="paramsForm.sensor_thresholds.conductivity.slope"
                                        min="0" step="0.01"
                                        :class="{ 'modified': isParamModified('sensor_thresholds.conductivity.slope') }">
                                </div>
                            </div>

                            <!-- 阶段约束设置 -->
                            <div class="sub-section">
                                <h5 class="sub-title">📌 阶段约束设置</h5>
                                <div class="constraints-grid">
                                    <div class="constraints-header">阶段</div>
                                    <div class="constraints-header">传感器</div>
                                    <div class="constraints-header">最小值</div>
                                    <div class="constraints-header">最大值</div>

                                    <!-- 平衡阶段 - pH -->
                                    <div rowspan="2">平衡</div>
                                    <div>pH</div>
                                    <input type="number" v-model="paramsForm.stage_constraints.equilibrate.ph[0]"
                                        step="0.1"
                                        :class="{ 'modified': isParamModified('stage_constraints.equilibrate.ph.0') }">
                                    <input type="number" v-model="paramsForm.stage_constraints.equilibrate.ph[1]"
                                        step="0.1"
                                        :class="{ 'modified': isParamModified('stage_constraints.equilibrate.ph.1') }">

                                    <!-- 平衡阶段 - 电导率 -->
                                    <div>电导率</div>
                                    <input type="number"
                                        v-model="paramsForm.stage_constraints.equilibrate.conductivity[0]" step="0.1"
                                        :class="{ 'modified': isParamModified('stage_constraints.equilibrate.conductivity.0') }">
                                    <input type="number"
                                        v-model="paramsForm.stage_constraints.equilibrate.conductivity[1]" step="0.1"
                                        :class="{ 'modified': isParamModified('stage_constraints.equilibrate.conductivity.1') }">

                                    <!-- 再生阶段 - pH -->
                                    <div rowspan="2">再生</div>
                                    <div>pH</div>
                                    <input type="number" v-model="paramsForm.stage_constraints.refresh.ph[0]" step="0.1"
                                        :class="{ 'modified': isParamModified('stage_constraints.refresh.ph.0') }">
                                    <input type="number" v-model="paramsForm.stage_constraints.refresh.ph[1]" step="0.1"
                                        :class="{ 'modified': isParamModified('stage_constraints.refresh.ph.1') }">

                                    <!-- 再生阶段 - 电导率 -->
                                    <div>电导率</div>
                                    <input type="number" v-model="paramsForm.stage_constraints.refresh.conductivity[0]"
                                        step="1"
                                        :class="{ 'modified': isParamModified('stage_constraints.refresh.conductivity.0') }">
                                    <input type="number" v-model="paramsForm.stage_constraints.refresh.conductivity[1]"
                                        step="1"
                                        :class="{ 'modified': isParamModified('stage_constraints.refresh.conductivity.1') }">
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="params-btn-group">
                        <button class="save-params-btn" @click="sendParams">💾 保存参数设置</button>
                        <button class="reset-params-btn" @click="resetParams">🔄 重置参数设置</button>
                    </div>
                </div>
            </transition>
        </div>

        <div class="dashboard-container">
            <!-- 泵控制区 -->
            <div class="control-card">
                <div class="device-panel">
                    <h3 class="panel-title">⌨️​ 泵状态监控</h3>
                    <div class="scroll-container">
                        <ul class="component-list">
                            <li v-for="(state, pump_id) in pump_state" :key="state.id" class="component-item" :class="[state.start_stop ? 'active' : 'inactive',
                            expandedPump === pump_id && 'expanded']" @click="toggleDetailsPump(pump_id)">
                                <div class="component-header">
                                    <span class="device-icon">🔧</span>
                                    <div class="device-meta">
                                        <span class="device-id">#{{ pump_id }}</span>
                                        <span class="device-name">{{ state.name }}</span>
                                    </div>
                                    <div class="status-indicator" :class="state.start_stop ? 'active' : 'inactive'">
                                    </div>
                                </div>

                                <transition name="slide-down">
                                    <div v-show="expandedPump === pump_id" class="component-details">
                                        <div class="detail-item">
                                            <label>状态：</label>
                                            <span class="status-badge"
                                                :class="state.start_stop ? 'active' : 'inactive'">
                                                {{ state.start_stop ? '运行中' : '已停止' }}
                                            </span>
                                        </div>
                                        <div class="detail-item">
                                            <label>转速：</label>
                                            <div class="progress-bar">
                                                <div class="progress-fill"
                                                    :style="{ width: calculateSpeedPercentage(state.speed) + '%' }">
                                                </div>
                                                <span class="progress-text">{{ state.speed.toFixed(1) }} RPM</span>
                                            </div>
                                        </div>
                                        <div class="detail-item">
                                            <label>方向：</label>
                                            <span :class="state.direction ? 'text-success' : 'text-warning'">
                                                {{ state.direction ? '正转 ↗' : '反转 ↘' }}
                                            </span>
                                        </div>
                                        <div class="detail-item">
                                            <label>排空：</label>
                                            <span class="toggle-indicator" :class="state.drain ? 'active' : 'inactive'">
                                                {{ state.drain ? '是' : '否' }}
                                            </span>
                                        </div>
                                    </div>
                                </transition>
                            </li>
                        </ul>
                    </div>
                </div>

                <div class="control-panel">
                    <h3>🎮 泵控制台</h3>
                    <div class="control-form">
                        <div class="form-group">
                            <label class="form-label">控制地址：</label>
                            <input type="text" v-model="pumpAddress" class="form-control" placeholder="示例：1,3 或 all">
                        </div>

                        <div class="form-group">
                            <label class="form-label">控制类型：</label>
                            <select v-model="pumpType" class="form-control">
                                <option value="start_stop">开关控制</option>
                                <option value="speed">转速调节</option>
                                <option value="direction">转向设置</option>
                                <option value="drain">排空操作</option>
                                <option value="alias">别名设置</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label class="form-label">控制值：</label>
                            <input type="text" v-model="pumpValue" class="form-control"
                                :placeholder="pumpType === 'speed' ? '输入转速 (RPM)' : pumpType === 'alias' ? '输入别名' : 'true/false 或 1/0'">
                        </div>

                        <button class="control-btn primary" @click="sendPumpCommand">
                            🚀 发送指令
                        </button>
                    </div>
                </div>
            </div>

            <!-- 阀门控制区 -->
            <div class="control-card">
                <div class="device-panel">
                    <h3 class="panel-title">🚰 阀门状态监控</h3>
                    <div class="scroll-container">
                        <ul class="component-list">
                            <li v-for="(state, valve_id) in valve_state" :key="state.id" class="component-item" :class="[state.opening > 0 ? 'active' : 'inactive',
                            expandedValve === valve_id && 'expanded']" @click="toggleDetailsValve(valve_id)">
                                <div class="component-header">
                                    <span class="device-icon">🔧</span>
                                    <div class="device-meta">
                                        <span class="device-id">#{{ valve_id }}</span>
                                        <span class="device-name">{{ state.name }}</span>
                                    </div>
                                    <div class="status-indicator" :class="state.opening > 0 ? 'active' : 'inactive'">
                                    </div>
                                </div>

                                <transition name="slide-down">
                                    <div v-show="expandedValve === valve_id" class="component-details">
                                        <div class="detail-item">
                                            <label>开度：</label>
                                            <div class="progress-bar">
                                                <div class="progress-fill" :style="{ width: state.opening + '%' }">
                                                </div>
                                                <span class="progress-text">{{ state.opening }}%</span>
                                            </div>
                                        </div>
                                    </div>
                                </transition>
                            </li>
                        </ul>
                    </div>
                </div>

                <div class="control-panel">
                    <h3>🎮 阀门控制台</h3>
                    <div class="control-form">
                        <div class="form-group">
                            <label class="form-label">控制地址：</label>
                            <input type="text" v-model="valveAddress" class="form-control" placeholder="示例：1,3 或 all">
                        </div>

                        <div class="form-group">
                            <label class="form-label">控制类型：</label>
                            <select v-model="valveType" class="form-control">
                                <option value="opening">开度控制</option>
                                <option value="alias">别名设置</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label class="form-label">控制值：</label>
                            <input v-if="valveType !== 'alias'" type="number" v-model="valveValue" class="form-control"
                                placeholder="输入控制值 (0-100)" min="0" max="100" step="0.01">
                            <input v-else type="text" v-model="valveValue" class="form-control" placeholder="输入别名">
                        </div>

                        <button class="control-btn primary" @click="sendValveCommand">
                            🚀 发送指令
                        </button>
                    </div>
                </div>
            </div>

            <!-- 光谱控制区 -->
            <div class="control-card">
                <div class="device-panel">
                    <h3 class="panel-title">🌈 光谱状态监控</h3>
                    <div class="scroll-container">
                        <ul class="component-list">
                            <!-- 紫外状态 -->
                            <li class="component-item"
                                :class="[uv_state.lamp ? 'active' : 'inactive', expandedSpectrum === 'uv' && 'expanded']"
                                @click="toggleDetailsSpectrum('uv')">
                                <div class="component-header">
                                    <span class="device-icon">🔧</span>
                                    <div class="device-meta">
                                        <span class="device-id">紫外光谱仪</span>
                                    </div>
                                    <div class="status-indicator" :class="uv_state.lamp ? 'active' : 'inactive'">
                                    </div>
                                </div>
                                <div v-show="expandedSpectrum === 'uv'" class="component-details">
                                    <div class="detail-item">
                                        <label>氙灯状态：</label>
                                        <span class="status-badge" :class="uv_state.lamp ? 'active' : 'inactive'">
                                            {{ uv_state.lamp ? '开启' : '关闭' }}
                                        </span>
                                    </div>
                                    <div class="detail-item">
                                        <label>平均次数：</label>
                                        <span>{{ uv_state.avg_times }}</span>
                                    </div>
                                    <div class="detail-item">
                                        <label>积分时间：</label>
                                        <span>{{ uv_state.integration_time }}ms</span>
                                    </div>
                                </div>
                            </li>
                            <!-- 近红外状态 -->
                            <li class="component-item" :class="['active', expandedSpectrum === 'nir' && 'expanded']"
                                @click="toggleDetailsSpectrum('nir')">
                                <div class="component-header">
                                    <span class="device-icon">🔧</span>
                                    <div class="device-meta">
                                        <span class="device-id">近红外光谱仪</span>
                                    </div>
                                    <div class="status-indicator" :class="['active']">
                                    </div>
                                </div>
                                <div v-show="expandedSpectrum === 'nir'" class="component-details">
                                    <div class="detail-item">
                                        <label>平均次数：</label>
                                        <span>{{ nir_state.avg_times }}</span>
                                    </div>
                                </div>
                            </li>
                        </ul>
                    </div>
                </div>
                <div class="control-panel">
                    <h3>🎮 光谱控制台</h3>
                    <div class="control-form">
                        <div class="form-group">
                            <label class="form-label">选择光谱类型：</label>
                            <select v-model="spectrumType" class="form-control">
                                <option value="uv">紫外</option>
                                <option value="nir">近红外</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">控制类型：</label>
                            <select v-model="spectrumControlType" class="form-control">
                                <template v-if="spectrumType === 'uv'">
                                    <option value="lamp">氙灯开关</option>
                                    <option value="average_times">平均次数设置</option>
                                    <option value="integration_time">积分时间设置</option>
                                    <option value="set_background">暗背景设置</option>
                                    <option value="set_reference">参比设置</option>
                                </template>
                                <template v-else>
                                    <option value="average_times">平均次数设置</option>
                                    <option value="set_background">暗背景设置</option>
                                    <option value="set_reference">参比设置</option>
                                </template>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">控制值：</label>
                            <input v-if="spectrumControlType === 'lamp'" type="text" v-model="spectrumControlValue"
                                class="form-control" placeholder="true/false 或 1/0">
                            <input v-else-if="spectrumControlType === 'average_times'" type="number"
                                v-model="spectrumControlValue" class="form-control" placeholder="输入正整数">
                            <input v-else-if="spectrumControlType === 'integration_time'" type="number"
                                v-model="spectrumControlValue" class="form-control" placeholder="输入16的倍数 (ms)">
                            <input v-else type="hidden" v-model="spectrumControlValue">
                        </div>
                        <button class="control-btn primary" @click="sendSpectrumCommand">
                            🚀 发送指令
                        </button>
                    </div>
                </div>
            </div>

            <!--监控区域-->
            <div class="monitor-card">
                <h2>📺 监控</h2>

                <!-- 视频播放区域 -->
                <iframe :src="videoUrl" allowfullscreen class="video"></iframe>
            </div>
        </div>
    </div>
</template>

<style scoped lang="scss">
.status-panel {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    padding: 1.5rem;
    margin-top: 1.5rem;
    margin-right: 1.5rem;
    margin-left: 1.5rem;
}

.experiment-status {
    display: flex;
    align-items: center;
    gap: 2rem;
    margin-bottom: 1rem;

    .status-label {
        font-weight: 600;
        color: #4b5563;
        font-size: 1.2rem;
        white-space: nowrap;
        /* 防止文本换行 */
    }

    .status-value {
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 500;

        &.running {
            background-color: #fee2e2;
            color: #dc2626;
        }

        &.stopped {
            background-color: #dcfce7;
            color: #16a34a;
        }

        .status-icon {
            margin-right: 0.5rem;
        }
    }

    .stage-info {
        margin-left: auto;
        color: #4b5563;

        .stage-value {
            font-weight: 600;
            color: #3b82f6;
        }
    }

    .skip-btn {
        background: #fef3c7;
        color: #d97706;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        cursor: pointer;
        transition: all 0.2s;
        font-weight: 500;

        &:hover {
            background: #fde68a;
        }
    }
}

.equilibrium-status {
    margin: 15px 0;
    padding: 15px;
    background-color: #f8f9fa;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.equilibrium-title {
    margin: 0 0 15px 0;
    font-size: 18px;
    color: #333;
    display: flex;
    align-items: center;
}

.equilibrium-title::before {
    content: "⚖️";
    margin-right: 8px;
}

.equilibrium-container {
    display: flex;
    gap: 15px;
    width: 100%;
    box-sizing: border-box;
}

.equilibrium-card {
    flex: 1;
    background: white;
    border-radius: 6px;
    padding: 12px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    min-width: 0;
    /* 防止内容溢出 */
}

.card-header {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid #eee;
}

.card-icon {
    margin-right: 8px;
    font-size: 18px;
}

.card-title {
    margin: 0;
    font-size: 16px;
    color: #555;
    flex: 1;
}

.card-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.status-item {
    display: flex;
    justify-content: space-between;
    font-size: 16px;
    padding: 4px 0;
}

.status-label {
    color: #666;
    flex: 0 0 60px;
}

.status-value {
    font-weight: 500;
}

.status-summary {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px dashed #eee;
    font-weight: 500;
}

.summary-label {
    color: #666;
}

.summary-card {
    display: flex;
    flex-direction: column;
    
    .card-header {
        flex-shrink: 0; /* 防止标题栏被压缩 */
    }
    
    .summary-content {
        flex: 1; /* 占据剩余空间 */
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 80px; /* 保持最小高度 */
    }
}

.final-status {
    font-size: 3rem;
    font-weight: 600;
    padding: 1.5rem 2rem;
    border-radius: 8px;
    text-align: center;
    width: 80%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* 状态颜色样式 */
.stable {
    color: #28a745;
}

.unstable {
    color: #dc3545;
}

.reached {
    background-color: #f0fff4;
    color: #28a745;
}

.not-reached {
    background-color: #fff5f5;
    color: #dc3545;
}

/* 响应式调整 */
@media (max-width: 768px) {
    .equilibrium-container {
        flex-direction: column;
    }

    .summary-card {
        flex: none;
    }
}

/* 参数面板样式更新 */
/* 添加修改标识样式 */
.modified {
    border: 2px solid #ff9800 !important;
    background-color: #fff8e1 !important;
}

.params-panel {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    margin: 1.5rem;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    transition: all 0.3s ease;

    &:hover {
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
    }

    .params-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.25rem 1.5rem;
        background: linear-gradient(to right, #f8fafc, #f1f5f9);
        cursor: pointer;
        border-bottom: 1px solid #e2e8f0;

        h3 {
            margin: 0;
            color: #1e293b;
            font-size: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .toggle-icon {
            color: #64748b;
            font-weight: 500;
            transition: all 0.3s;
        }

        &:hover {
            background: linear-gradient(to right, #f1f5f9, #e2e8f0);

            .toggle-icon {
                color: #3b82f6;
            }
        }
    }
}

.params-content {
    padding: 1.5rem;
    background: #f9fafb;
}

.params-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 2rem;
}

.param-section {
    background: white;
    border-radius: 10px;
    padding: 1.5rem;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
    border: 1px solid #edf2f7;
}

.section-title {
    margin-top: 0;
    margin-bottom: 1.5rem;
    padding-bottom: 0.75rem;
    border-bottom: 2px solid #e2e8f0;
    color: #334155;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 1.1rem;
}

.sub-section {
    margin-bottom: 1.5rem;
    padding: 1.25rem;
    background: #f8fafc;
    border-radius: 8px;
    border-left: 3px solid #c7d2fe;

    &:last-child {
        margin-bottom: 0;
    }
}

.sub-title {
    margin-top: 0;
    margin-bottom: 1rem;
    color: #475569;
    font-size: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.param-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
    margin-bottom: 1rem;

    &:last-child {
        margin-bottom: 0;
    }
}

.param-group {
    display: flex;
    flex-direction: column;

    label {
        margin-bottom: 0.5rem;
        font-weight: 500;
        color: #475569;
        font-size: 0.9rem;
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }

    input {
        padding: 0.75rem;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        transition: all 0.2s;
        background: white;
        font-size: 0.95rem;

        &:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
        }
    }
}


.threshold-grid,
.constraints-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
    align-items: center;
    margin-top: 0.75rem;

    .threshold-header,
    .constraints-header {
        font-weight: 600;
        background-color: #4a5568; // 深灰色背景
        color: white; // 白色文字
        padding: 0.75rem;
        border-radius: 6px;
        text-align: center;
        font-size: 0.9rem;
    }

    div {
        padding: 0.75rem;
        text-align: center;
    }

    input {
        padding: 0.65rem;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        width: 91%;
        background: white;
        font-size: 0.9rem;

        &:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
        }
    }
}

.constraints-grid {
    div[rowspan="2"] {
        grid-row: span 2;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #e4ebf3;
        border-radius: 6px;
        font-weight: 500;
        padding: 0.75rem;
    }
}

.save-params-btn {
    background: linear-gradient(to right, #3b82f6, #2563eb);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.85rem 1.75rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: inline-block;
    margin: 2rem 0.5rem 0;
    width: fit-content;
    font-size: 1rem;
    box-shadow: 0 2px 6px rgba(59, 130, 246, 0.3);

    &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
        background: linear-gradient(to right, #4f94fc, #3b82f6);
    }

    &:active {
        transform: translateY(0);
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
    }
}

.reset-params-btn {
    background: #f3f4f6;
    /* 浅灰背景，替代黄色系 */
    color: #4b5563;
    /* 深灰文字，提升可读性 */
    border: 1px solid #d1d5db;
    /* 浅灰边框，增强轮廓 */
    border-radius: 8px;
    padding: 0.85rem 1.75rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: inline-block;
    /* 保持水平排列特性 */
    margin: 2rem 0.5rem 0;
    width: fit-content;
    font-size: 1rem;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
    /* 淡灰色阴影，更自然 */

    &:hover {
        transform: translateY(-2px);
        background: #e5e7eb;
        /*  hover时加深背景色 */
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        /* 增强阴影 */
        border-color: #9ca3af;
        /* 边框略加深 */
    }

    &:active {
        transform: translateY(0);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        /* 点击后阴影收缩 */
        background: #d1d5db;
        /* 点击时背景色再加深 */
    }
}

/* 按钮组容器 */
.params-btn-group {
    justify-content: center;
    display: flex;
    gap: 10rem;
    /* 按钮间距 */
}

/* 动画效果 */
.slide-down-enter-active {
    transition: all 0.3s ease-out;
}

.slide-down-leave-active {
    transition: all 0.2s ease-in;
}

.slide-down-enter-from,
.slide-down-leave-to {
    opacity: 0;
    transform: translateY(-10px);
}

/* 基础布局 */
.dashboard-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
    gap: 1.5rem;
    padding: 1.5rem;
    margin-top: 1.5rem;
}

/* 卡片式设计 - 新增左右分栏 */
.control-card {
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    overflow: hidden;
    display: grid;
    grid-template-columns: 1fr 1fr;
    height: 450px;
}

.monitor-card {
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
}

/* 监控列样式 */
.video {
    width: 100%;
    height: 100%;
    border: none;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    margin-bottom: 20px;
}

.device-panel {
    max-height: 450px;
    display: flex;
    flex-direction: column;
    border-right: 1px solid #e2e8f0;
}

/* 滚动容器 */
.scroll-container {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
    height: 300px;
}

/* 控制列样式 */
.control-panel {
    display: flex;
    flex-direction: column;
    background: #f8fafc;
    padding: 1.5rem;
}

/* 响应式处理 */
@media (max-width: 768px) {
    .control-card {
        grid-template-columns: 1fr;
        height: auto;
    }

    .device-panel {
        border-right: none;
        border-bottom: 1px solid #e2e8f0;
    }
}

/* 自定义滚动条 */
.scroll-container::-webkit-scrollbar {
    width: 8px;
    background: #f1f5f9;
}

.scroll-container::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 4px;
}

.scroll-container::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
}

/* 状态指示器样式 */
.status-indicator {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-left: 10px;
}

.status-indicator.active {
    background-color: #10b981;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.5);
}

.status-indicator.inactive {
    background-color: #ef4444;
}

/* 进度条样式 */
.progress-bar {
    width: 70%;
    height: 20px;
    background: #e2e8f0;
    border-radius: 10px;
    overflow: hidden;
    position: relative;
    margin-top: 5px;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #3b82f6, #60a5fa);
    border-radius: 10px;
    transition: width 0.5s ease;
}

.progress-text {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 12px;
    font-weight: bold;
    color: #1e293b;
    text-shadow: 0 0 2px white;
}

/* 开关指示器样式 */
.toggle-indicator {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.85em;
}

.toggle-indicator.active {
    background-color: #dcfce7;
    color: #16a34a;
}

.toggle-indicator.inactive {
    background-color: #fee2e2;
    color: #dc2626;
}

/* 设备列表样式 */
.component-list {
    padding: 0.5rem;
    margin: 0;
}

.component-item {
    padding: 1rem;
    margin: 0.5rem;
    border-radius: 8px;
    transition: all 0.2s ease;
    cursor: pointer;
    border: 1px solid #e2e8f0;

    &:hover {
        transform: translateY(-2px);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }

    &.active {
        border-left: 4px solid #10b981;
        background: #f0fdf4;
    }

    &.inactive {
        border-left: 4px solid #ef4444;
        background: #fef2f2;
    }
}

.component-header {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.device-meta {
    flex: 1;

    .device-id {
        font-weight: 600;
        color: #1e293b;
    }

    .device-name {
        color: #64748b;
        margin-left: 0.5rem;
        font-size: 0.9em;
    }
}

/* 详细信息面板 */
.component-details {
    padding: 1rem 0 0;
    margin-top: 1rem;
    border-top: 1px dashed #e2e8f0;
}

.detail-item {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem 0;

    label {
        color: #64748b;
        font-weight: 500;
    }
}

/* 状态徽章 */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.85em;

    &.active {
        background: #dcfce7;
        color: #16a34a;
    }

    &.inactive {
        background: #fee2e2;
        color: #dc2626;
    }
}

/* 文字颜色 */
.text-success {
    color: #16a34a;
}

.text-warning {
    color: #ea580c;
}

/* 面板标题 */
.panel-title {
    font-size: 1.25rem;
    color: #1e293b;
    padding: 1rem;
    margin: 0;
    background: #f1f5f9;
    border-bottom: 1px solid #e2e8f0;
}

/* 控制表单 */
.control-form {
    padding: 1rem;
}

.form-group {
    margin-bottom: 1rem;
}

.form-label {
    display: block;
    color: #475569;
    margin-bottom: 0.5rem;
    font-weight: 500;
}

.form-control {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    transition: border-color 0.2s;

    &:focus {
        outline: none;
        border-color: #3b82f6;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
    }
}

.control-btn {
    width: 100%;
    padding: 0.75rem;
    border: none;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    transition: transform 0.1s;

    &.primary {
        background: #3b82f6;
        color: white;

        &:hover {
            background: #2563eb;
        }
    }

    &:active {
        transform: scale(0.98);
    }
}

/* 动画效果 */
.slide-down-enter-active {
    transition: all 0.3s ease-out;
}

.slide-down-leave-active {
    transition: all 0.2s ease-in;
}

.slide-down-enter-from,
.slide-down-leave-to {
    opacity: 0;
    transform: translateY(-10px);
}
</style>