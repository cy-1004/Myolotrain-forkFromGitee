/**
 * 系统监控页面JavaScript功能
 */

class Monitoring {
    constructor() {
        // 全局变量
        this.monitoringChart = null;
        this.pollingInterval = null;
        this.currentDataRange = '1h'; // 默认显示最近1小时的数据
        
        // 页面加载完成后初始化
        document.addEventListener('DOMContentLoaded', () => {
            // 初始化监控页面
            this.initMonitoringPage();
            
            // 绑定事件监听器
            this.bindEventListeners();
        });
    }

    /**
     * 初始化监控页面
     */
    initMonitoringPage() {
        console.log('初始化系统监控页面');
        
        // 加载初始数据
        this.loadCurrentSystemResources();
        
        // 开始轮询获取实时数据
        this.startPolling();
        
        // 初始化图表
        this.initCharts();
    }

    /**
     * 绑定事件监听器
     */
    bindEventListeners() {
        // 时间范围选择器
        const timeRangeSelector = document.getElementById('time-range-selector');
        if (timeRangeSelector) {
            timeRangeSelector.addEventListener('change', (event) => {
                this.currentDataRange = event.target.value;
                this.loadHistoricalData(this.currentDataRange);
            });
        }
        
        // 刷新按钮
        const refreshBtn = document.getElementById('refresh-monitoring-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadCurrentSystemResources();
                this.loadHistoricalData(this.currentDataRange);
            });
        }
        
        // 监控服务控制按钮
        const toggleBtn = document.getElementById('toggle-monitoring-btn');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                this.toggleMonitoringService();
            });
        }
        
        // 初始化监控服务状态
        this.initMonitoringStatus();
    }

    /**
     * 加载当前系统资源信息
     */
    loadCurrentSystemResources() {
        fetch('/api/monitoring/system-resources')
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('获取系统资源信息失败:', data.error);
                    this.showErrorMessage('获取系统资源信息失败: ' + data.error);
                    return;
                }
                
                // 更新UI显示
                this.updateSystemResourceDisplay(data);
            })
            .catch(error => {
                console.error('获取系统资源信息时出错:', error);
                this.showErrorMessage('获取系统资源信息时出错: ' + error.message);
            });
    }

    /**
     * 更新系统资源显示
     */
    updateSystemResourceDisplay(data) {
        // 更新CPU信息
        this.updateCPUDisplay(data.cpu);
        
        // 更新内存信息
        this.updateMemoryDisplay(data.memory);
        
        // 更新磁盘信息
        this.updateDiskDisplay(data.disk);
        
        // 更新网络信息
        this.updateNetworkDisplay(data.network);
        
        // 更新GPU信息（如果有）
        this.updateGPUDisplay(data.gpu);
        
        // 更新最后更新时间
        const lastUpdateElement = document.getElementById('last-update-time');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = new Date(data.timestamp).toLocaleString();
        }
    }

    /**
     * 更新CPU显示
     */
    updateCPUDisplay(cpuData) {
        const cpuPercentElement = document.getElementById('cpu-percent');
        const cpuCountElement = document.getElementById('cpu-count');
        
        if (cpuPercentElement) {
            cpuPercentElement.textContent = cpuData.percent.toFixed(1);
            // 根据使用率设置颜色
            const cpuCard = cpuPercentElement.closest('.metric-card');
            if (cpuCard) {
                cpuCard.className = cpuCard.className.replace(/alert-\w+/, '');
                if (cpuData.percent > 80) {
                    cpuCard.classList.add('alert-critical');
                } else if (cpuData.percent > 60) {
                    cpuCard.classList.add('alert-warning');
                } else {
                    cpuCard.classList.add('alert-success');
                }
            }
        }
        
        if (cpuCountElement) {
            cpuCountElement.textContent = cpuData.count;
        }
    }

    /**
     * 更新内存显示
     */
    updateMemoryDisplay(memoryData) {
        const memoryPercentElement = document.getElementById('memory-percent');
        const memoryUsedElement = document.getElementById('memory-used');
        const memoryTotalElement = document.getElementById('memory-total');
        
        if (memoryPercentElement) {
            memoryPercentElement.textContent = memoryData.percent.toFixed(1);
            // 根据使用率设置颜色
            const memoryCard = memoryPercentElement.closest('.metric-card');
            if (memoryCard) {
                memoryCard.className = memoryCard.className.replace(/alert-\w+/, '');
                if (memoryData.percent > 90) {
                    memoryCard.classList.add('alert-critical');
                } else if (memoryData.percent > 75) {
                    memoryCard.classList.add('alert-warning');
                } else {
                    memoryCard.classList.add('alert-success');
                }
            }
        }
        
        if (memoryUsedElement) {
            memoryUsedElement.textContent = this.formatBytes(memoryData.used);
        }
        
        if (memoryTotalElement) {
            memoryTotalElement.textContent = this.formatBytes(memoryData.total);
        }
    }

    /**
     * 更新磁盘显示
     */
    updateDiskDisplay(diskData) {
        const diskPercentElement = document.getElementById('disk-percent');
        const diskUsedElement = document.getElementById('disk-used');
        const diskTotalElement = document.getElementById('disk-total');
        
        if (diskPercentElement) {
            diskPercentElement.textContent = diskData.percent.toFixed(1);
            // 根据使用率设置颜色
            const diskCard = diskPercentElement.closest('.metric-card');
            if (diskCard) {
                diskCard.className = diskCard.className.replace(/alert-\w+/, '');
                if (diskData.percent > 95) {
                    diskCard.classList.add('alert-critical');
                } else if (diskData.percent > 85) {
                    diskCard.classList.add('alert-warning');
                } else {
                    diskCard.classList.add('alert-success');
                }
            }
        }
        
        if (diskUsedElement) {
            diskUsedElement.textContent = this.formatBytes(diskData.used);
        }
        
        if (diskTotalElement) {
            diskTotalElement.textContent = this.formatBytes(diskData.total);
        }
    }

    /**
     * 更新网络显示
     */
    updateNetworkDisplay(networkData) {
        const bytesSentElement = document.getElementById('bytes-sent');
        const bytesRecvElement = document.getElementById('bytes-recv');
        
        if (bytesSentElement) {
            bytesSentElement.textContent = this.formatBytes(networkData.bytes_sent);
        }
        
        if (bytesRecvElement) {
            bytesRecvElement.textContent = this.formatBytes(networkData.bytes_recv);
        }
    }

    /**
     * 更新GPU显示
     */
    updateGPUDisplay(gpuData) {
        const gpuContainer = document.getElementById('gpu-container');
        if (!gpuContainer) return;
        
        // 清空现有内容
        gpuContainer.innerHTML = '';
        
        if (!gpuData || gpuData.length === 0) {
            gpuContainer.innerHTML = '<p class="text-muted">未检测到GPU设备</p>';
            return;
        }
        
        // 为每个GPU创建显示卡片
        gpuData.forEach((gpu, index) => {
            const gpuCard = document.createElement('div');
            gpuCard.className = 'col-md-6 mb-3';
            // 为GPU信息添加安全检查
            const utilization = gpu.utilization !== undefined ? gpu.utilization : '--';
            const memoryPercent = gpu.memory_percent !== undefined ? gpu.memory_percent.toFixed(1) : '--';
            const memoryUsed = gpu.memory_used !== undefined ? this.formatBytes(gpu.memory_used) : '--';
            const memoryTotal = gpu.memory_total !== undefined ? this.formatBytes(gpu.memory_total) : '--';
            
            gpuCard.innerHTML = `
                <div class="card">
                    <div class="card-header">
                        <h5>GPU ${gpu.index !== undefined ? gpu.index : '--'}: ${gpu.name || 'Unknown'}</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-6">
                                <p><strong>使用率:</strong> <span id="gpu-${index}-utilization">${utilization}</span>%</p>
                                <p><strong>显存使用:</strong> <span id="gpu-${index}-memory-percent">${memoryPercent}</span>%</p>
                            </div>
                            <div class="col-6">
                                <p><strong>显存已用:</strong> <span id="gpu-${index}-memory-used">${memoryUsed}</span></p>
                                <p><strong>显存总量:</strong> <span id="gpu-${index}-memory-total">${memoryTotal}</span></p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            gpuContainer.appendChild(gpuCard);
        });
    }

    /**
     * 格式化字节数
     */
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 初始化图表
     */
    initCharts() {
        const ctx = document.getElementById('monitoring-chart');
        if (!ctx) return;
        
        this.monitoringChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'CPU使用率 (%)',
                        data: [],
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        yAxisID: 'y'
                    },
                    {
                        label: '内存使用率 (%)',
                        data: [],
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        yAxisID: 'y'
                    },
                    {
                        label: '磁盘使用率 (%)',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        yAxisID: 'y'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: '时间'
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: '使用率 (%)'
                        },
                        min: 0,
                        max: 100
                    }
                }
            }
        });
        
        // 加载历史数据
        this.loadHistoricalData(this.currentDataRange);
    }

    /**
     * 加载历史数据
     */
    loadHistoricalData(timeRange) {
        // 将时间范围转换为分钟
        let minutes = 60; // 默认1小时
        switch (timeRange) {
            case '30m':
                minutes = 30;
                break;
            case '1h':
                minutes = 60;
                break;
            case '6h':
                minutes = 360;
                break;
            case '12h':
                minutes = 720;
                break;
            case '24h':
                minutes = 1440;
                break;
        }
        
        fetch(`/api/monitoring/system-resources/history?minutes=${minutes}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('获取历史数据失败:', data.error);
                    return;
                }
                
                // 更新图表
                this.updateChart(data.data);
            })
            .catch(error => {
                console.error('获取历史数据时出错:', error);
            });
    }

    /**
     * 更新图表
     */
    updateChart(historyData) {
        if (!this.monitoringChart) return;
        
        // 准备图表数据
        const labels = [];
        const cpuData = [];
        const memoryData = [];
        const diskData = [];
        
        historyData.forEach(item => {
            labels.push(new Date(item.timestamp).toLocaleTimeString());
            cpuData.push(item.cpu_percent);
            memoryData.push(item.memory_percent);
            diskData.push(item.disk_percent);
        });
        
        // 更新图表数据
        this.monitoringChart.data.labels = labels;
        this.monitoringChart.data.datasets[0].data = cpuData;
        this.monitoringChart.data.datasets[1].data = memoryData;
        this.monitoringChart.data.datasets[2].data = diskData;
        
        // 更新图表
        this.monitoringChart.update();
    }

    /**
     * 开始轮询
     */
    startPolling() {
        // 清除现有的轮询（如果有的话）
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
        
        // 每5秒获取一次数据
        this.pollingInterval = setInterval(() => {
            this.loadCurrentSystemResources();
        }, 5000);
    }

    /**
     * 停止轮询
     */
    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    /**
     * 显示错误消息
     */
    showErrorMessage(message) {
        const errorContainer = document.getElementById('monitoring-error-message');
        if (errorContainer) {
            errorContainer.textContent = message;
            errorContainer.style.display = 'block';
            
            // 3秒后隐藏错误消息
            setTimeout(() => {
                errorContainer.style.display = 'none';
            }, 3000);
        }
    }

    /**
     * 切换监控服务状态
     */
    toggleMonitoringService() {
        console.log('切换监控服务状态');
        // 获取当前状态
        fetch('/api/monitoring/system-resources/control/status')
            .then(response => {
                if (!response.ok) {
                    throw new Error('获取状态失败: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                console.log('当前状态:', data);
                const newAction = data.enabled ? 'disable' : 'enable';
                console.log('将执行操作:', newAction);
                
                // 发送切换请求
                return fetch('/api/monitoring/system-resources/control?action=' + newAction, {
                    method: 'POST'
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('控制操作失败: ' + response.status);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('操作结果:', data.message);
                    // 更新按钮文本
                    this.updateMonitoringStatusText();
                    // 根据操作结果控制轮询
                    if (newAction === 'disable') {
                        console.log('停止轮询');
                        this.stopPolling();
                    } else {
                        console.log('开始轮询');
                        this.startPolling();
                    }
                    // 显示消息
                    this.showErrorMessage(data.message);
                });
            })
            .catch(error => {
                console.error('切换监控服务状态时出错:', error);
                this.showErrorMessage('切换监控服务状态时出错: ' + error.message);
            });
    }

    /**
     * 初始化监控服务状态
     */
    initMonitoringStatus() {
        this.updateMonitoringStatusText();
    }

    /**
     * 更新监控状态文本
     */
    updateMonitoringStatusText() {
        fetch('/api/monitoring/system-resources/control/status')
            .then(response => {
                if (!response.ok) {
                    throw new Error('获取状态失败: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                const statusText = document.getElementById('monitoring-status-text');
                if (statusText) {
                    statusText.textContent = data.enabled ? '关闭监控' : '开启监控';
                    
                    // 更新按钮样式
                    const toggleBtn = document.getElementById('toggle-monitoring-btn');
                    if (toggleBtn) {
                        if (data.enabled) {
                            toggleBtn.classList.remove('btn-success');
                            toggleBtn.classList.add('btn-secondary');
                            // 监控已启用，开始轮询
                            this.startPolling();
                        } else {
                            toggleBtn.classList.remove('btn-secondary');
                            toggleBtn.classList.add('btn-success');
                            // 监控已禁用，停止轮询
                            this.stopPolling();
                        }
                    }
                }
            })
            .catch(error => {
                console.error('获取监控服务状态时出错:', error);
            });
    }
}

// 页面卸载时清理资源
window.addEventListener('beforeunload', function() {
    if (window.monitoring) {
        window.monitoring.stopPolling();
    }
});

// 创建全局实例
window.monitoring = new Monitoring();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Monitoring;
}