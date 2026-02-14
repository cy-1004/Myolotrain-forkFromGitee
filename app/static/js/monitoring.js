/**
 * 系统监控页面JavaScript功能
 */

class Monitoring {
    constructor() {
        // 全局变量
        this.monitoringChart = null;
        this.pollingInterval = null;
        this.currentDataRange = '1h'; // 默认显示最近1小时的数据
        this.gpuDisplayMode = 'list'; // 默认显示模式：逐行显示
        this.currentGpuData = []; // 存储当前GPU数据
        this.historyDataCache = {}; // 缓存历史数据，键为时间范围
        
        // 页面加载完成后初始化
        document.addEventListener('DOMContentLoaded', () => {
            // 加载GPU显示模式设置
            this.loadGpuDisplayMode();
            
            // 绑定事件监听器
            this.bindEventListeners();
        });
    }

    /**
     * 初始化监控页面
     */
    initMonitoringPage() {
        console.log('初始化系统监控页面');
        
        // 检查是否存在监控页面元素
        const gpuContainer = document.getElementById('gpu-container');
        const monitoringChart = document.getElementById('monitoring-chart');
        
        if (!gpuContainer && !monitoringChart) {
            console.log('Not on monitoring page, skipping monitoring initialization');
            return;
        }
        
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
        
        // GPU显示模式切换事件
        const gpuDisplayBtns = document.querySelectorAll('.gpu-display-btn');
        gpuDisplayBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mode = e.target.closest('.gpu-display-btn').dataset.mode;
                this.saveGpuDisplayMode(mode);
                this.updateGpuDisplayButtons();
                // 直接重新渲染GPU显示，不需要重新获取整个系统资源数据
                this.renderGPUDisplay();
            });
        });
        
        // 初始化GPU显示模式按钮状态
        this.updateGpuDisplayButtons();
        
        // 初始化监控服务状态
        this.initMonitoringStatus();
    }
    
    /**
     * 从localStorage加载GPU显示模式设置
     */
    loadGpuDisplayMode() {
        const savedMode = localStorage.getItem('gpuDisplayMode');
        if (savedMode && (savedMode === 'list' || savedMode === 'grid')) {
            this.gpuDisplayMode = savedMode;
        }
    }
    
    /**
     * 保存GPU显示模式设置到localStorage
     */
    saveGpuDisplayMode(mode) {
        this.gpuDisplayMode = mode;
        localStorage.setItem('gpuDisplayMode', mode);
        console.log('已保存GPU显示模式:', mode);
    }
    
    /**
     * 更新GPU显示模式按钮的激活状态
     */
    updateGpuDisplayButtons() {
        const gpuDisplayBtns = document.querySelectorAll('.gpu-display-btn');
        gpuDisplayBtns.forEach(btn => {
            if (btn.dataset.mode === this.gpuDisplayMode) {
                btn.classList.remove('btn-outline-primary');
                btn.classList.add('btn-primary');
            } else {
                btn.classList.remove('btn-primary');
                btn.classList.add('btn-outline-primary');
            }
        });
    }

    /**
     * 加载当前系统资源信息
     */
    loadCurrentSystemResources() {
        // 检查是否在监控页面
        const gpuContainer = document.getElementById('gpu-container');
        const monitoringChart = document.getElementById('monitoring-chart');
        if (!gpuContainer && !monitoringChart) {
            return;
        }
        
        fetch('/api/monitoring/system-resources')
            .then(response => {
                // 检查请求是否被中断
                if (!response.ok) {
                    throw new Error('网络请求失败');
                }
                return response.json();
            })
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
                // 忽略页面刷新导致的请求中断错误
                if (error.message !== 'Failed to fetch' && error.message !== '网络请求失败') {
                    console.error('获取系统资源信息时出错:', error);
                    this.showErrorMessage('获取系统资源信息时出错: ' + error.message);
                }
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
        const networkTrafficElement = document.getElementById('network-traffic');
        
        if (bytesSentElement) {
            bytesSentElement.textContent = this.formatBytes(networkData.bytes_sent);
        }
        
        if (bytesRecvElement) {
            bytesRecvElement.textContent = this.formatBytes(networkData.bytes_recv);
        }
        
        if (networkTrafficElement) {
            // 计算总网络流量
            const totalTraffic = (networkData.bytes_sent || 0) + (networkData.bytes_recv || 0);
            networkTrafficElement.textContent = this.formatBytes(totalTraffic);
        }
    }

    /**
     * 更新GPU显示
     */
    updateGPUDisplay(gpuData) {
        // 保存当前GPU数据
        this.currentGpuData = gpuData || [];
        // 渲染GPU显示
        this.renderGPUDisplay();
    }
    
    /**
     * 渲染GPU显示
     */
    renderGPUDisplay() {
        const gpuContainer = document.getElementById('gpu-container');
        if (!gpuContainer) return;
        
        // 清空现有内容
        gpuContainer.innerHTML = '';
        
        if (!this.currentGpuData || this.currentGpuData.length === 0) {
            gpuContainer.innerHTML = '<p class="text-muted">未检测到GPU设备</p>';
            return;
        }
        
        // 根据显示模式设置容器类名
        gpuContainer.className = this.gpuDisplayMode === 'list' ? 'row' : 'row';
        
        // 为每个GPU创建显示卡片
        this.currentGpuData.forEach((gpu, index) => {
            const gpuCard = document.createElement('div');
            // 根据显示模式设置卡片类名
            gpuCard.className = this.gpuDisplayMode === 'list' ? 'col-12 mb-3' : 'col-md-6 mb-3';
            // 为GPU信息添加安全检查
            const utilization = gpu.utilization !== undefined ? gpu.utilization : '--';
            const memoryPercent = gpu.memory_percent !== undefined ? gpu.memory_percent.toFixed(1) : '--';
            const memoryUsed = gpu.memory_used !== undefined ? this.formatBytes(gpu.memory_used) : '--';
            const memoryTotal = gpu.memory_total !== undefined ? this.formatBytes(gpu.memory_total) : '--';
            
            if (this.gpuDisplayMode === 'list') {
                // 逐行显示模式：使用表格布局使信息对齐
                gpuCard.innerHTML = `
                    <div class="card">
                        <div class="card-body p-3">
                            <div class="table-responsive">
                                <table class="table table-sm table-borderless mb-0">
                                    <tbody>
                                        <tr>
                                            <td style="width: 30%; font-weight: bold;">GPU ${gpu.index !== undefined ? gpu.index : '--'}: ${gpu.name || 'Unknown'}</td>
                                            <td style="width: 20%; text-align: right;">
                                                <strong>使用率:</strong> <span id="gpu-${index}-utilization">${utilization}</span>%
                                            </td>
                                            <td style="width: 20%; text-align: right;">
                                                <strong>显存使用:</strong> <span id="gpu-${index}-memory-percent">${memoryPercent}</span>%
                                            </td>
                                            <td style="width: 30%; text-align: right;">
                                                <strong>显存:</strong> 
                                                <span style="display: inline-block; width: 100px; text-align: right; font-family: monospace;">
                                                    <span id="gpu-${index}-memory-used">${memoryUsed}</span>
                                                </span>
                                                <span style="display: inline-block; width: 10px; text-align: center;">/</span>
                                                <span style="display: inline-block; width: 60px; text-align: left; font-family: monospace;">
                                                    <span id="gpu-${index}-memory-total">${memoryTotal}</span>
                                                </span>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                // 井格显示模式：两列布局，信息分两行显示
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
            }
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
        
        // 销毁旧图表（如果存在）
        if (this.monitoringChart) {
            this.monitoringChart.destroy();
            this.monitoringChart = null;
        }
        
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
                        yAxisID: 'y',
                        tension: 0.1, // 减少曲线平滑度，提高渲染速度
                        pointRadius: 0, // 隐藏数据点，提高渲染速度
                        pointHoverRadius: 3 // 鼠标悬停时显示数据点
                    },
                    {
                        label: '内存使用率 (%)',
                        data: [],
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        yAxisID: 'y',
                        tension: 0.1,
                        pointRadius: 0,
                        pointHoverRadius: 3
                    },
                    {
                        label: '磁盘使用率 (%)',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        yAxisID: 'y',
                        tension: 0.1,
                        pointRadius: 0,
                        pointHoverRadius: 3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 0 // 禁用动画，提高渲染速度
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: '时间'
                        },
                        ticks: {
                            maxRotation: 0, // 减少标签旋转，提高渲染速度
                            autoSkip: true, // 自动跳过标签，避免重叠
                            maxTicksLimit: 10 // 限制最大标签数量
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
                },
                plugins: {
                    legend: {
                        display: true
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
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
        // 检查是否在监控页面，避免在页面切换时发起请求
        const chartElement = document.getElementById('monitoring-chart');
        if (!chartElement) {
            return;
        }
        
        // 检查缓存中是否有数据
        if (this.historyDataCache[timeRange]) {
            // 使用缓存数据，提高加载速度
            this.updateChart(this.historyDataCache[timeRange]);
            return;
        }
        
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
        
        // 进一步减少数据点数量，提高加载速度
        let points = 50;
        if (minutes > 720) { // 12小时以上
            points = 80;
        } else if (minutes > 360) { // 6-12小时
            points = 60;
        }
        
        // 显示加载指示器
        this.showLoadingIndicator();
        
        fetch(`/api/monitoring/system-resources/history?minutes=${minutes}&points=${points}`)
            .then(response => {
                // 检查请求是否被中断
                if (!response.ok) {
                    throw new Error('网络请求失败');
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    console.error('获取历史数据失败:', data.error);
                    return;
                }
                
                // 缓存数据，提高后续加载速度
                this.historyDataCache[timeRange] = data.data;
                
                // 更新图表
                this.updateChart(data.data);
            })
            .catch(error => {
                // 忽略页面刷新导致的请求中断错误
                // 这种错误是浏览器默认行为，无法完全阻止控制台显示
                // 但我们可以确保它不会影响应用功能
                if (error.message !== 'Failed to fetch' && error.message !== '网络请求失败' && !error.message.includes('net::ERR_ABORTED')) {
                    console.error('获取历史数据时出错:', error);
                }
            })
            .finally(() => {
                // 隐藏加载指示器
                this.hideLoadingIndicator();
            });
    }
    
    /**
     * 显示加载指示器
     */
    showLoadingIndicator() {
        const chartContainer = document.querySelector('.chart-container');
        if (chartContainer) {
            // 检查是否已存在加载指示器
            let loadingIndicator = chartContainer.querySelector('.loading-indicator');
            if (!loadingIndicator) {
                loadingIndicator = document.createElement('div');
                loadingIndicator.className = 'loading-indicator';
                loadingIndicator.style.cssText = `
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(255, 255, 255, 0.7);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    z-index: 10;
                    border-radius: 0.25rem;
                `;
                loadingIndicator.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="sr-only">加载中...</span></div>';
                chartContainer.style.position = 'relative';
                chartContainer.appendChild(loadingIndicator);
            }
            loadingIndicator.style.display = 'flex';
        }
    }
    
    /**
     * 隐藏加载指示器
     */
    hideLoadingIndicator() {
        const chartContainer = document.querySelector('.chart-container');
        if (chartContainer) {
            const loadingIndicator = chartContainer.querySelector('.loading-indicator');
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
        }
    }

    /**
     * 更新图表
     */
    updateChart(historyData) {
        if (!this.monitoringChart) return;
        
        // 快速检查数据是否为空
        if (!historyData || historyData.length === 0) {
            return;
        }
        
        // 准备图表数据，使用后端已经采样的数据
        const labels = [];
        const cpuData = [];
        const memoryData = [];
        const diskData = [];
        
        // 批量处理数据，减少循环次数
        const len = historyData.length;
        for (let i = 0; i < len; i++) {
            const item = historyData[i];
            labels.push(new Date(item.timestamp).toLocaleTimeString());
            cpuData.push(item.cpu_percent);
            memoryData.push(item.memory_percent);
            diskData.push(item.disk_percent);
        }
        
        // 批量更新图表数据，减少DOM操作
        const chartData = this.monitoringChart.data;
        chartData.labels = labels;
        chartData.datasets[0].data = cpuData;
        chartData.datasets[1].data = memoryData;
        chartData.datasets[2].data = diskData;
        
        // 使用静默更新模式，进一步提高渲染速度
        this.monitoringChart.update('none');
    }
    
    /**
     * 数据采样，减少数据点数量
     */
    sampleData(data, maxPoints) {
        if (!data || data.length <= maxPoints) {
            return data;
        }
        
        const result = [];
        const step = data.length / maxPoints;
        
        for (let i = 0; i < data.length; i += step) {
            result.push(data[Math.floor(i)]);
        }
        
        // 确保包含最后一个数据点
        if (result[result.length - 1] !== data[data.length - 1]) {
            result[result.length - 1] = data[data.length - 1];
        }
        
        return result;
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
        // 检查是否在监控页面
        const statusText = document.getElementById('monitoring-status-text');
        if (statusText) {
            this.updateMonitoringStatusText();
        }
    }

    /**
     * 更新监控状态文本
     */
    updateMonitoringStatusText() {
        // 检查是否在监控页面
        const statusText = document.getElementById('monitoring-status-text');
        if (!statusText) {
            return;
        }
        
        fetch('/api/monitoring/system-resources/control/status')
            .then(response => {
                if (!response.ok) {
                    throw new Error('获取状态失败: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
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