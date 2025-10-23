<!-- components/Monitor.vue -->
<script setup>
import { ref} from 'vue'
import { useSSE } from '../composables/useSSE'
import DeleteModal from './DeleteModal.vue'

const { logs, records, expDesigns } = useSSE()
const ServerUrl = import.meta.env.VITE_APP_ServerUrl
const expandedRecord = ref(null)
const expandedDesign = ref(null)
const showDeleteModal = ref(false)
const currentRecordId = ref(null)

const toggleDetails = (expId) => {
    expandedRecord.value = expandedRecord.value === expId ? null : expId
}

const toggleDesignDetails = (designId) => {
    expandedDesign.value = expandedDesign.value === designId ? null : designId
}

const handleDelete = (recordId) => {
    currentRecordId.value = recordId
    showDeleteModal.value = true
}

const confirmDelete = () => {
    if (currentRecordId.value) {
        deleteRecord(currentRecordId.value)
        showDeleteModal.value = false
    }
}

const deleteRecord = async (recordId) => {
    try {
        await fetch(`${ServerUrl}/delete_record/${recordId}`, {
            method: 'DELETE'
        })
    } catch (error) {
        alert('删除记录失败，请稍后再试')
        console.error('删除记录失败:', error)
    }
}
</script>

<template>
    <div class="monitor-container">
        <!-- 日志展示区域 -->
        <div class="record-box">
            <h3 class="record-title">📋 日志</h3>
            <div class="log-content">
                <ul>
                    <li v-for="(log, index) in logs" :key="index" class="log-item">
                        <span class="log-time">{{ log.time }}</span>
                        <span class="log-experiment">[实验ID: {{ log.experiment_id }}]</span>
                        <span class="log-text">{{ log.content }}</span>
                    </li>
                </ul>
            </div>
        </div>

        <!-- 实验记录展示区域 -->
        <div class="record-box">
            <h3 class="record-title">📋 实验记录</h3>
            <div class="record-content">
                <table class="record-table">
                    <thead>
                        <tr>
                            <th style="width: 15%">实验ID</th>
                            <th style="width: 30%">开始时间</th>
                            <th style="width: 30%">结束时间</th>
                            <th style="width: 25%">操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template v-for="record in records" :key="record.id">
                            <tr v-show="record.id !== 0" @click="toggleDetails(record.id)">
                                <td>{{ record.id }}</td>
                                <td>{{ record.start_time }}</td>
                                <td>{{ record.end_time }}</td>
                                <td>
                                    <button class="delete-btn" @click.stop="handleDelete(record.id)">删除</button>
                                </td>
                            </tr>
                            <tr v-show="expandedRecord === record.id" class="record-detail">
                                <td colspan="4" style="text-align: left; padding: 15px;">
                                    <!-- 实验条件区块 -->
                                    <div class="condition-block">
                                        <p>
                                            上样液批号: {{ record.feed_number || '无' }}；
                                            洗涤液: {{ record.phase_wash || '无' }}；
                                            洗脱液: {{ record.phase_elute || '无' }}；
                                            再生液: {{ record.phase_refresh || '无' }}；
                                            平衡液: {{ record.phase_equilibrate || '无' }}；
                                            液面高度: {{ record.liquid_height || '无' }} cm；
                                            树脂: {{ record.resin || '无' }}；
                                            柱高: {{ record.column_height || '无' }} cm；
                                            柱内径: {{ record.column_inner_diameter || '无' }} cm；
                                            床层高: {{ record.bed_height || '无' }} cm
                                        </p>
                                    </div>

                                    <!-- 控制指令区块 -->
                                    <div class="command-block">
                                        <p>控制指令(流量单位BV/h，时间单位h): {{ record.control_command || '无' }}</p>
                                    </div>

                                    <!-- 实验结果区块 -->
                                    <div class="result-block">
                                        <p>
                                            产品质量: {{ record.product_quality != null ? record.product_quality : '未完成实验'}}；
                                            产品收率: {{ record.product_yield != null ? record.product_yield : '未完成实验' }}；
                                            产品产率: {{ record.product_productivity != null ? record.product_productivity : '未完成实验' }}；
                                        </p>
                                    </div>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 实验设计展示区域 -->
        <div class="record-box">
            <h3 class="record-title">📋 实验设计记录</h3>
            <div class="record-content">
                <table class="record-table">
                    <thead>
                        <tr>
                            <th style="width: 20%">实验设计ID</th>
                            <th style="width: 80%">描述</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template v-for="design in expDesigns" :key="design.id">
                            <tr @click="toggleDesignDetails(design.id)">
                                <td>{{ design.id }}</td>
                                <td style="text-align: left;">
                                    <p>{{ design.description.split('\n')[0] }}</p>
                                    <p>{{ design.description.split('\n').slice(1).join('\n') }}</p>
                                </td>
                            </tr>
                            <tr v-show="expandedDesign === design.id" class="record-detail">
                                <td colspan="2" style="text-align: left;">
                                    <table class="design-table">
                                        <thead>
                                            <tr>
                                                <th>实验编号</th>
                                                <th v-for="(value, key) in getFirstExperiment(design.design_table)"
                                                    :key="key">{{ key }}</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr v-for="(experiment, expNumber) in design.design_table" :key="expNumber">
                                                <td>{{ expNumber }}</td>
                                                <td v-for="(value, key) in experiment" :key="key">{{ value }}</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>
        </div>

        <DeleteModal :show="showDeleteModal" @confirm="confirmDelete" @cancel="showDeleteModal = false" />
    </div>
</template>

<script>
const getFirstExperiment = (designTable) => {
    const firstKey = Object.keys(designTable)[0];
    return firstKey ? designTable[firstKey] : {};
};
export default {
    setup() {
        return {
            getFirstExperiment
        };
    }
};
</script>

<style scoped>
.monitor-container {
    padding: 10px;
    height: 100%;
}


.record-box {
    margin-bottom: 25px;
    background-color: #fff;
    border-radius: 8px;
    padding: 5px 15px;
    height: 400px;
    box-shadow: 4px 4px 12px rgba(0, 0, 0, 0.05);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.record-box:hover {
    transform: translateY(-2px);
    box-shadow: 4px 4px 18px rgba(0, 0, 0, 0.1);
}

.log-content {
    height: 300px;
    overflow-y: auto;
    margin-top: 10px;
    padding: 10px;
    background-color: #fafafa;
    border: 1px solid #eee;
    border-radius: 6px;
}

.record-content {
    height:  300px;
    overflow-y: auto;
    margin-top: 10px;
    padding: 5px;
}

.log-item {
    padding: 6px 0;
    border-bottom: 1px solid #eee;
    font-size: 14px;
    line-height: 1.5;
}

.log-item:last-child {
    border-bottom: none;
}

.log-time {
    color: #666;
    margin-right: 10px;
    min-width: 130px;
    display: inline-block;
}

.log-experiment {
    color: #2c3e50;
    font-weight: bold;
    margin-right: 10px;
}

.log-text {
    color: #333;
}

/* 标题样式 */
.record-title {
    font-size: 18px;
    color: #2c3e50;
    font-weight: bold;
    margin-bottom: 10px;
    padding-left: 8px;
    border-left: 4px solid #3498db;
    /* 左边装饰线 */
}

/* 表格美化 */
.record-table {
    width: 100%;
    border-collapse: collapse;
    background-color: #fff;
    font-size: 14px;
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.record-table thead tr {
    background-color: #f1f1f1;
    color: #333;
    text-align: center;
}

.record-table th,
.record-table td {
    padding: 12px 15px;
    border-bottom: 1px solid #eee;
    text-align: center;
}

.record-table tbody tr:hover {
    background-color: #f9f9f9;
    transition: background-color 0.2s ease;
}

.record-table tbody tr:nth-child(even) {
    background-color: #fbfbfb;
}

/* 删除按钮样式 */
.delete-btn {
    padding: 6px 12px;
    font-size: 12px;
    color: white;
    background-color: #e74c3c;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.3s ease;
}

.delete-btn:hover {
    background-color: #c0392b;
}

/* 展开详情行动画 */
.record-detail {
    background-color: #f8f9fa;
    transition: all 0.3s ease-in-out;
}

.design-table {
    width: 100%;
    border-collapse: collapse;
    background-color: #fff;
    font-size: 14px;
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.design-table thead tr {
    background-color: #f1f1f1;
    color: #333;
    text-align: left;
}

.design-table th,
.design-table td {
    padding: 12px 15px;
    border-bottom: 1px solid #eee;
}

.design-table tbody tr:hover {
    background-color: #f9f9f9;
    transition: background-color 0.2s ease;
}

.design-table tbody tr:nth-child(even) {
    background-color: #fbfbfb;
}
/* 实验记录区块样式 */
.condition-block {
  background-color: #f0f7ff;
  border-left: 4px solid #4a90e2;
  padding: 12px 15px;
  margin-bottom: 10px;
  border-radius: 0 6px 6px 0;
}

.command-block {
  background-color: #fff8e1;
  border-left: 4px solid #ffc107;
  padding: 12px 15px;
  margin-bottom: 10px;
  border-radius: 0 6px 6px 0;
}

.result-block {
  background-color: #e8f5e9;
  border-left: 4px solid #4caf50;
  padding: 12px 15px;
  border-radius: 0 6px 6px 0;
}
</style>