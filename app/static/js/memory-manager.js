/**
 * 内存管理器 - 统一管理JavaScript内存资源
 * 解决URL.createObjectURL和定时器内存泄漏问题
 */

class MemoryManager {
    constructor() {
        this.objectUrls = new Set();
        this.intervals = new Set();
        this.timeouts = new Set();
        this.cleanupInterval = null;
        
        // 启动自动清理机制
        this.startAutoCleanup();
        
        // 页面卸载时清理所有资源
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
        
        // 页面隐藏时也执行清理
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') {
                this.partialCleanup();
            }
        });
    }
    
    /**
     * 创建Object URL并自动管理
     * @param {Blob} blob - Blob对象
     * @returns {string} - Object URL
     */
    createObjectURL(blob) {
        const url = URL.createObjectURL(blob);
        this.objectUrls.add(url);
        console.log(`Created Object URL: ${url}, Total URLs: ${this.objectUrls.size}`);
        return url;
    }
    
    /**
     * 释放Object URL
     * @param {string} url - Object URL
     */
    revokeObjectURL(url) {
        if (this.objectUrls.has(url)) {
            URL.revokeObjectURL(url);
            this.objectUrls.delete(url);
            console.log(`Revoked Object URL: ${url}, Remaining URLs: ${this.objectUrls.size}`);
        }
    }
    
    /**
     * 创建定时器并自动管理
     * @param {Function} callback - 回调函数
     * @param {number} delay - 延迟时间(毫秒)
     * @returns {number} - 定时器ID
     */
    setInterval(callback, delay) {
        const intervalId = setInterval(callback, delay);
        this.intervals.add(intervalId);
        console.log(`Created interval: ${intervalId}, Total intervals: ${this.intervals.size}`);
        return intervalId;
    }
    
    /**
     * 清除定时器
     * @param {number} intervalId - 定时器ID
     */
    clearInterval(intervalId) {
        if (this.intervals.has(intervalId)) {
            clearInterval(intervalId);
            this.intervals.delete(intervalId);
            console.log(`Cleared interval: ${intervalId}, Remaining intervals: ${this.intervals.size}`);
        }
    }
    
    /**
     * 创建超时器并自动管理
     * @param {Function} callback - 回调函数
     * @param {number} delay - 延迟时间(毫秒)
     * @returns {number} - 超时器ID
     */
    setTimeout(callback, delay) {
        const timeoutId = setTimeout(() => {
            // 执行回调后自动删除
            this.timeouts.delete(timeoutId);
            callback();
        }, delay);
        this.timeouts.add(timeoutId);
        console.log(`Created timeout: ${timeoutId}, Total timeouts: ${this.timeouts.size}`);
        return timeoutId;
    }
    
    /**
     * 清除超时器
     * @param {number} timeoutId - 超时器ID
     */
    clearTimeout(timeoutId) {
        if (this.timeouts.has(timeoutId)) {
            clearTimeout(timeoutId);
            this.timeouts.delete(timeoutId);
            console.log(`Cleared timeout: ${timeoutId}, Remaining timeouts: ${this.timeouts.size}`);
        }
    }
    
    /**
     * 启动自动清理机制
     */
    startAutoCleanup() {
        // 每5秒执行一次轻量级清理
        this.cleanupInterval = setInterval(() => {
            this.partialCleanup();
        }, 5000);
        
        console.log('Memory manager auto cleanup started');
    }
    
    /**
     * 部分清理 - 清理过期的Object URLs
     */
    partialCleanup() {
        // 检查并清理未使用的Object URLs
        // 这里可以添加更智能的检测逻辑
        const urlsToRemove = [];
        
        this.objectUrls.forEach(url => {
            // 检查URL是否还在使用中
            const isInUse = this.isUrlInUse(url);
            if (!isInUse) {
                urlsToRemove.push(url);
            }
        });
        
        urlsToRemove.forEach(url => {
            this.revokeObjectURL(url);
        });
        
        if (urlsToRemove.length > 0) {
            console.log(`Partial cleanup: removed ${urlsToRemove.length} unused URLs`);
        }
    }
    
    /**
     * 检查URL是否还在使用中
     * @param {string} url - Object URL
     * @returns {boolean} - 是否在使用中
     */
    isUrlInUse(url) {
        // 检查img元素
        const images = document.querySelectorAll('img');
        for (let img of images) {
            if (img.src === url) {
                return true;
            }
        }
        
        // 检查link元素
        const links = document.querySelectorAll('a[download]');
        for (let link of links) {
            if (link.href === url) {
                return true;
            }
        }
        
        // 检查video元素
        const videos = document.querySelectorAll('video');
        for (let video of videos) {
            if (video.src === url) {
                return true;
            }
        }
        
        return false;
    }
    
    /**
     * 完全清理所有资源
     */
    cleanup() {
        console.log('Starting complete memory cleanup...');
        
        // 清理所有Object URLs
        this.objectUrls.forEach(url => {
            URL.revokeObjectURL(url);
        });
        this.objectUrls.clear();
        console.log('All Object URLs cleaned up');
        
        // 清理所有定时器
        this.intervals.forEach(intervalId => {
            clearInterval(intervalId);
        });
        this.intervals.clear();
        console.log('All intervals cleaned up');
        
        // 清理所有超时器
        this.timeouts.forEach(timeoutId => {
            clearTimeout(timeoutId);
        });
        this.timeouts.clear();
        console.log('All timeouts cleaned up');
        
        // 停止自动清理
        if (this.cleanupInterval) {
            clearInterval(this.cleanupInterval);
            this.cleanupInterval = null;
        }
        
        console.log('Memory cleanup completed');
    }
    
    /**
     * 获取内存使用统计
     * @returns {Object} - 内存使用统计
     */
    getMemoryStats() {
        return {
            objectUrls: this.objectUrls.size,
            intervals: this.intervals.size,
            timeouts: this.timeouts.size,
            totalManagedResources: this.objectUrls.size + this.intervals.size + this.timeouts.size
        };
    }
    
    /**
     * 强制垃圾收集（如果浏览器支持）
     */
    forceGarbageCollection() {
        if (window.gc) {
            window.gc();
            console.log('Forced garbage collection');
        } else {
            console.log('Garbage collection not available');
        }
    }
}

// 创建全局内存管理器实例
window.memoryManager = new MemoryManager();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MemoryManager;
}

console.log('Memory Manager initialized successfully');