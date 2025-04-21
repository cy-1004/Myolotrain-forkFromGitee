/**
 * 轮询管理器 - 用于管理和清理API轮询
 */
const PollingManager = {
    // 存储所有活动的轮询定时器
    activePolls: {},
    
    // 添加轮询
    addPoll: function(key, intervalId) {
        this.activePolls[key] = intervalId;
        console.log(`添加轮询: ${key}, 当前活动轮询数: ${Object.keys(this.activePolls).length}`);
    },
    
    // 移除轮询
    removePoll: function(key) {
        if (this.activePolls[key]) {
            clearInterval(this.activePolls[key]);
            delete this.activePolls[key];
            console.log(`移除轮询: ${key}, 当前活动轮询数: ${Object.keys(this.activePolls).length}`);
            return true;
        }
        return false;
    },
    
    // 清除所有轮询
    clearAllPolls: function() {
        Object.keys(this.activePolls).forEach(key => {
            clearInterval(this.activePolls[key]);
        });
        this.activePolls = {};
        console.log('已清除所有轮询');
    },
    
    // 清除特定类型的轮询
    clearPollsByType: function(type) {
        Object.keys(this.activePolls).forEach(key => {
            if (key.startsWith(type)) {
                clearInterval(this.activePolls[key]);
                delete this.activePolls[key];
            }
        });
        console.log(`已清除类型为 ${type} 的所有轮询`);
    },
    
    // 处理API错误
    handleApiError: function(key, error, status) {
        // 如果是404错误，停止轮询
        if (status === 404) {
            this.removePoll(key);
            console.log(`由于404错误，已停止轮询: ${key}`);
            
            // 清除本地存储中的相关任务ID
            if (key.includes('training')) {
                localStorage.removeItem('lastTrainingTaskId');
                sessionStorage.removeItem('lastTrainingTaskId');
            } else if (key.includes('detection')) {
                localStorage.removeItem('lastDetectionTaskId');
                sessionStorage.removeItem('lastDetectionTaskId');
            }
            
            return true;
        }
        return false;
    }
};

// 页面加载时清除所有可能的轮询
document.addEventListener('DOMContentLoaded', function() {
    // 清除所有可能存在的定时器
    for (let i = 1; i < 10000; i++) {
        clearInterval(i);
    }
    
    // 初始化轮询管理器
    PollingManager.clearAllPolls();
    
    console.log('轮询管理器已初始化');
});
