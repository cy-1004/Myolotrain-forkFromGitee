// 设置管理模块
class SettingsManager {
    constructor() {
        // 构造函数
    }

    // 绑定设置页面事件
    bindSettingsEvents() {
        // 保存设置按钮事件
        const saveBtn = document.getElementById('saveSettingsBtn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                const debugModeToggle = document.getElementById('debugModeToggle');
                if (debugModeToggle) {
                    const newDebugMode = debugModeToggle.checked;
                    this.saveDebugMode(newDebugMode);
                    
                    // 显示保存成功消息
                    this.showSettingsSaveMessage(`DEBUG模式已${newDebugMode ? '启用' : '禁用'}`);
                }
            });
        }
    }

    // 保存DEBUG模式设置到localStorage
    saveDebugMode(debugMode) {
        DEBUG_MODE = debugMode;
        localStorage.setItem('debugMode', debugMode);
        console.log(`DEBUG模式已${DEBUG_MODE ? '启用' : '禁用'}`);
    }

    // 显示设置保存消息
    showSettingsSaveMessage(message) {
        const messageElement = document.getElementById('settings-save-message');
        if (messageElement) {
            messageElement.textContent = message;
            messageElement.className = 'mt-2 alert alert-success';
            messageElement.style.display = 'block';
            
            // 3秒后隐藏消息
            setTimeout(function() {
                messageElement.style.display = 'none';
            }, 3000);
        }
    }
}

// 创建全局实例
window.settingsManager = new SettingsManager();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SettingsManager;
}
