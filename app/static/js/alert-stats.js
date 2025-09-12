/**
 * 报警统计分析功能
 * 用于分析和可视化报警数据
 */

// 存储报警记录的数组
let alertRecords = [];

// 图表对象
let distributionChart = null;
let frequencyChart = null;

// 初始化统计分析功能
document.addEventListener('DOMContentLoaded', function() {
    // 监听时间范围选择变化
    const timeRangeSelect = document.getElementById('time-range');
    if (timeRangeSelect) {
        timeRangeSelect.addEventListener('change', function() {
            updateFrequencyChart();
        });
    }

    // 监听导出按钮点击事件
    const exportBtn = document.getElementById('export-alerts-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', exportAlertData);
    }

    // 初始化图表
    initCharts();
});

/**
 * 初始化图表
 */
function initCharts() {
    // 初始化目标类别分布图表
    const distributionCtx = document.getElementById('object-distribution-chart');
    if (distributionCtx) {
        distributionChart = new Chart(distributionCtx, {
            type: 'pie',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.7)',
                        'rgba(54, 162, 235, 0.7)',
                        'rgba(255, 206, 86, 0.7)',
                        'rgba(75, 192, 192, 0.7)',
                        'rgba(153, 102, 255, 0.7)',
                        'rgba(255, 159, 64, 0.7)',
                        'rgba(199, 199, 199, 0.7)',
                        'rgba(83, 102, 255, 0.7)',
                        'rgba(40, 159, 64, 0.7)',
                        'rgba(210, 199, 199, 0.7)'
                    ],
                    borderColor: [
                        'rgba(255, 99, 132, 1)',
                        'rgba(54, 162, 235, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(75, 192, 192, 1)',
                        'rgba(153, 102, 255, 1)',
                        'rgba(255, 159, 64, 1)',
                        'rgba(199, 199, 199, 1)',
                        'rgba(83, 102, 255, 1)',
                        'rgba(40, 159, 64, 1)',
                        'rgba(210, 199, 199, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'right',
                    },
                    title: {
                        display: true,
                        text: '目标类别分布'
                    }
                }
            }
        });
        // 隐藏图表，显示"暂无数据"提示
        distributionCtx.style.display = 'none';
    }

    // 初始化报警频率图表
    const frequencyCtx = document.getElementById('alert-frequency-chart');
    if (frequencyCtx) {
        frequencyChart = new Chart(frequencyCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: '报警次数',
                    data: [],
                    backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: '报警频率统计'
                    }
                }
            }
        });
        // 隐藏图表，显示"暂无数据"提示
        frequencyCtx.style.display = 'none';
    }
}

/**
 * 添加报警记录
 * @param {Object} record 报警记录对象，包含时间、类别和置信度
 */
function addAlertRecord(record) {
    // 添加到记录数组
    alertRecords.push(record);
    
    // 保存到本地存储
    saveAlertRecords();
    
    // 更新统计数据
    updateStatistics();
}

/**
 * 保存报警记录到本地存储
 */
function saveAlertRecords() {
    try {
        localStorage.setItem('alertRecords', JSON.stringify(alertRecords));
    } catch (e) {
        console.error('保存报警记录失败:', e);
        
        // 如果存储空间不足，删除旧记录
        if (e.name === 'QuotaExceededError') {
            // 保留最新的100条记录
            alertRecords = alertRecords.slice(-100);
            try {
                localStorage.setItem('alertRecords', JSON.stringify(alertRecords));
            } catch (e2) {
                console.error('精简后保存报警记录仍然失败:', e2);
            }
        }
    }
}

/**
 * 从本地存储加载报警记录
 */
function loadAlertRecords() {
    try {
        const records = localStorage.getItem('alertRecords');
        if (records) {
            alertRecords = JSON.parse(records);
            
            // 确保时间字段是Date对象
            alertRecords.forEach(record => {
                if (typeof record.time === 'string') {
                    record.time = new Date(record.time);
                }
            });
            
            // 更新统计数据
            updateStatistics();
        }
    } catch (e) {
        console.error('加载报警记录失败:', e);
        alertRecords = [];
    }
}

/**
 * 清空报警记录
 */
function clearAlertRecords() {
    alertRecords = [];
    saveAlertRecords();
    updateStatistics();
}

/**
 * 更新统计数据和图表
 */
function updateStatistics() {
    if (alertRecords.length === 0) {
        // 如果没有记录，显示"暂无数据"提示
        document.getElementById('no-distribution-data').style.display = 'block';
        document.getElementById('no-frequency-data').style.display = 'block';
        document.getElementById('object-distribution-chart').style.display = 'none';
        document.getElementById('alert-frequency-chart').style.display = 'none';
        
        // 更新统计卡片
        document.getElementById('total-alerts-count').textContent = '0';
        document.getElementById('today-alerts-count').textContent = '0';
        document.getElementById('unique-targets-count').textContent = '0';
        document.getElementById('avg-confidence').textContent = '0%';
        
        return;
    }
    
    // 隐藏"暂无数据"提示，显示图表
    document.getElementById('no-distribution-data').style.display = 'none';
    document.getElementById('no-frequency-data').style.display = 'none';
    document.getElementById('object-distribution-chart').style.display = 'block';
    document.getElementById('alert-frequency-chart').style.display = 'block';
    
    // 更新目标类别分布图表
    updateDistributionChart();
    
    // 更新报警频率图表
    updateFrequencyChart();
    
    // 更新统计卡片
    updateStatCards();
}

/**
 * 更新目标类别分布图表
 */
function updateDistributionChart() {
    if (!distributionChart) return;
    
    // 统计各类别的数量
    const categoryCounts = {};
    alertRecords.forEach(record => {
        const category = record.category;
        categoryCounts[category] = (categoryCounts[category] || 0) + 1;
    });
    
    // 准备图表数据
    const labels = Object.keys(categoryCounts);
    const data = Object.values(categoryCounts);
    
    // 更新图表
    distributionChart.data.labels = labels;
    distributionChart.data.datasets[0].data = data;
    distributionChart.update();
}

/**
 * 更新报警频率图表
 */
function updateFrequencyChart() {
    if (!frequencyChart) return;
    
    // 获取选择的时间范围
    const timeRange = document.getElementById('time-range').value;
    
    // 根据时间范围筛选记录
    const now = new Date();
    let filteredRecords = [];
    let labels = [];
    let timeFormat = '';
    
    switch (timeRange) {
        case 'hour':
            // 过去1小时，按5分钟分组
            const hourAgo = new Date(now.getTime() - 60 * 60 * 1000);
            filteredRecords = alertRecords.filter(record => 
                record.time >= hourAgo
            );
            
            // 创建12个5分钟的时间段
            for (let i = 0; i < 12; i++) {
                const time = new Date(hourAgo.getTime() + i * 5 * 60 * 1000);
                labels.push(time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
            }
            
            timeFormat = 'HH:mm';
            break;
            
        case 'today':
            // 今天，按小时分组
            const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            filteredRecords = alertRecords.filter(record => 
                record.time >= startOfDay
            );
            
            // 创建24个小时的时间段
            for (let i = 0; i < 24; i++) {
                labels.push(`${i}:00`);
            }
            
            timeFormat = 'HH:00';
            break;
            
        case 'week':
            // 本周，按天分组
            const startOfWeek = new Date(now);
            startOfWeek.setDate(now.getDate() - now.getDay());
            startOfWeek.setHours(0, 0, 0, 0);
            
            filteredRecords = alertRecords.filter(record => 
                record.time >= startOfWeek
            );
            
            // 创建7天的时间段
            const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
            for (let i = 0; i < 7; i++) {
                labels.push(days[i]);
            }
            
            timeFormat = 'weekday';
            break;
            
        case 'all':
        default:
            // 全部记录，按天分组
            filteredRecords = [...alertRecords];
            
            // 如果记录跨越多天，按天分组
            if (filteredRecords.length > 0) {
                const oldestRecord = filteredRecords.reduce((oldest, record) => 
                    record.time < oldest.time ? record : oldest
                );
                
                const daysDiff = Math.ceil((now - oldestRecord.time) / (24 * 60 * 60 * 1000));
                
                // 如果记录跨越超过30天，按月分组
                if (daysDiff > 30) {
                    // 按月分组
                    const months = {};
                    filteredRecords.forEach(record => {
                        const monthKey = `${record.time.getFullYear()}-${record.time.getMonth() + 1}`;
                        months[monthKey] = (months[monthKey] || 0) + 1;
                    });
                    
                    labels = Object.keys(months).map(key => {
                        const [year, month] = key.split('-');
                        return `${year}年${month}月`;
                    });
                    
                    const data = Object.values(months);
                    
                    // 更新图表
                    frequencyChart.data.labels = labels;
                    frequencyChart.data.datasets[0].data = data;
                    frequencyChart.update();
                    return;
                } else {
                    // 按天分组
                    const startDate = new Date(oldestRecord.time);
                    startDate.setHours(0, 0, 0, 0);
                    
                    for (let i = 0; i <= daysDiff; i++) {
                        const date = new Date(startDate);
                        date.setDate(date.getDate() + i);
                        labels.push(`${date.getMonth() + 1}/${date.getDate()}`);
                    }
                    
                    timeFormat = 'MM/DD';
                }
            }
            break;
    }
    
    // 统计各时间段的报警次数
    const timeCounts = new Array(labels.length).fill(0);
    
    filteredRecords.forEach(record => {
        let index = 0;
        
        switch (timeRange) {
            case 'hour':
                // 计算记录时间在过去一小时内的5分钟索引
                index = Math.floor((record.time - (now.getTime() - 60 * 60 * 1000)) / (5 * 60 * 1000));
                break;
                
            case 'today':
                // 使用小时作为索引
                index = record.time.getHours();
                break;
                
            case 'week':
                // 使用星期几作为索引
                index = record.time.getDay();
                break;
                
            case 'all':
            default:
                if (timeFormat === 'MM/DD') {
                    // 计算记录日期与起始日期的天数差
                    const startDate = new Date(labels[0].split('/')[0], labels[0].split('/')[1] - 1);
                    const recordDate = new Date(record.time);
                    recordDate.setHours(0, 0, 0, 0);
                    
                    index = Math.floor((recordDate - startDate) / (24 * 60 * 60 * 1000));
                }
                break;
        }
        
        // 确保索引在有效范围内
        if (index >= 0 && index < timeCounts.length) {
            timeCounts[index]++;
        }
    });
    
    // 更新图表
    frequencyChart.data.labels = labels;
    frequencyChart.data.datasets[0].data = timeCounts;
    frequencyChart.update();
}

/**
 * 更新统计卡片
 */
function updateStatCards() {
    // 总报警次数
    document.getElementById('total-alerts-count').textContent = alertRecords.length;
    
    // 今日报警次数
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayAlerts = alertRecords.filter(record => record.time >= today);
    document.getElementById('today-alerts-count').textContent = todayAlerts.length;
    
    // 目标类别数
    const uniqueCategories = new Set(alertRecords.map(record => record.category));
    document.getElementById('unique-targets-count').textContent = uniqueCategories.size;
    
    // 平均置信度
    const avgConfidence = alertRecords.reduce((sum, record) => sum + record.confidence, 0) / alertRecords.length;
    document.getElementById('avg-confidence').textContent = `${(avgConfidence * 100).toFixed(1)}%`;
}

/**
 * 导出报警数据为CSV文件
 */
function exportAlertData() {
    if (alertRecords.length === 0) {
        alert('没有报警数据可导出');
        return;
    }
    
    // 创建CSV内容
    let csvContent = '时间,目标类别,置信度\n';
    
    alertRecords.forEach(record => {
        const time = record.time.toLocaleString();
        const category = record.category;
        const confidence = (record.confidence * 100).toFixed(1) + '%';
        
        csvContent += `${time},${category},${confidence}\n`;
    });
    
    // 创建Blob对象
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    
    // 创建下载链接
    const link = document.createElement('a');
    const url = window.memoryManager.createObjectURL(blob);
    
    // 设置下载属性
    link.setAttribute('href', url);
    link.setAttribute('download', `报警记录_${new Date().toISOString().slice(0, 10)}.csv`);
    link.style.visibility = 'hidden';
    
    // 添加到文档并触发点击
    document.body.appendChild(link);
    link.click();
    
    // 清理
    document.body.removeChild(link);
    // 延迟释放URL，确保下载完成
    window.memoryManager.setTimeout(() => {
        window.memoryManager.revokeObjectURL(url);
    }, 2000);
}

// 在页面加载时加载报警记录
window.addEventListener('load', loadAlertRecords);

// 导出函数供main.js使用
window.alertStats = {
    addAlertRecord,
    clearAlertRecords,
    updateStatistics
};
