/**
 * 流媒体功能模块
 * 提供流媒体创建、管理和检测功能
 */

// 流媒体管理类
class StreamManager {
    constructor() {
        this.apiUrl = '/api/streaming';
        this.streams = new Map();
        this.activeStreamId = null;
    }

    /**
     * 创建新的流媒体
     * @param {string} source - 流媒体源地址
     * @param {string} type - 流媒体类型
     * @returns {Promise<string>} - 返回流媒体ID
     */
    async createStream(source, type = 'auto') {
        try {
            const formData = new FormData();
            formData.append('source', source);
            formData.append('stream_type', type);

            const response = await fetch(`${this.apiUrl}/create`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (data.success) {
                return data.stream_id;
            } else {
                throw new Error(data.message || '创建流媒体失败');
            }
        } catch (error) {
            console.error('创建流媒体失败:', error);
            throw error;
        }
    }

    /**
     * 启动流媒体
     * @param {string} streamId - 流媒体ID
     * @returns {Promise<boolean>} - 启动是否成功
     */
    async startStream(streamId) {
        try {
            const response = await fetch(`${this.apiUrl}/start/${streamId}`, {
                method: 'POST'
            });

            const data = await response.json();
            if (data.success) {
                this.streams.set(streamId, { ...this.streams.get(streamId), is_running: true });
                return true;
            } else {
                throw new Error(data.message || '启动流媒体失败');
            }
        } catch (error) {
            console.error('启动流媒体失败:', error);
            throw error;
        }
    }

    /**
     * 停止流媒体
     * @param {string} streamId - 流媒体ID
     * @returns {Promise<boolean>} - 停止是否成功
     */
    async stopStream(streamId) {
        try {
            const response = await fetch(`${this.apiUrl}/stop/${streamId}`, {
                method: 'POST'
            });

            const data = await response.json();
            if (data.success) {
                this.streams.set(streamId, { ...this.streams.get(streamId), is_running: false });
                return true;
            } else {
                throw new Error(data.message || '停止流媒体失败');
            }
        } catch (error) {
            console.error('停止流媒体失败:', error);
            throw error;
        }
    }

    /**
     * 获取流媒体列表
     * @returns {Promise<Object>} - 流媒体列表
     */
    async getStreamsList() {
        try {
            const response = await fetch(`${this.apiUrl}/list`);
            const data = await response.json();
            
            if (data.success) {
                // 更新本地缓存
                this.streams.clear();
                Object.entries(data.streams).forEach(([id, info]) => {
                    this.streams.set(id, info);
                });
                return data.streams;
            } else {
                throw new Error('获取流媒体列表失败');
            }
        } catch (error) {
            console.error('获取流媒体列表失败:', error);
            throw error;
        }
    }

    /**
     * 获取流媒体信息
     * @param {string} streamId - 流媒体ID
     * @returns {Promise<Object>} - 流媒体信息
     */
    async getStreamInfo(streamId) {
        try {
            const response = await fetch(`${this.apiUrl}/info/${streamId}`);
            const data = await response.json();
            
            if (data.success) {
                return data.info;
            } else {
                throw new Error(data.message || '获取流媒体信息失败');
            }
        } catch (error) {
            console.error('获取流媒体信息失败:', error);
            throw error;
        }
    }

    /**
     * 测试流媒体连接
     * @param {string} source - 流媒体源地址
     * @param {string} type - 流媒体类型
     * @returns {Promise<Object>} - 测试结果
     */
    async testConnection(source, type = 'auto') {
        try {
            const formData = new FormData();
            formData.append('source', source);
            formData.append('stream_type', type);

            const response = await fetch(`${this.apiUrl}/test-connection`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('测试连接失败:', error);
            throw error;
        }
    }

    /**
     * 获取流媒体的MJPEG URL
     * @param {string} streamId - 流媒体ID
     * @returns {string} - MJPEG URL
     */
    getMjpegUrl(streamId) {
        return `${this.apiUrl}/mjpeg/${streamId}`;
    }

    /**
     * 获取流媒体的单帧URL
     * @param {string} streamId - 流媒体ID
     * @returns {string} - 单帧URL
     */
    getFrameUrl(streamId) {
        return `${this.apiUrl}/frame/${streamId}`;
    }

    /**
     * 获取支持的流媒体格式
     * @returns {Promise<Object>} - 支持的格式列表
     */
    async getSupportedFormats() {
        try {
            const response = await fetch(`${this.apiUrl}/supported-formats`);
            const data = await response.json();
            
            if (data.success) {
                return data.formats;
            } else {
                throw new Error('获取支持格式失败');
            }
        } catch (error) {
            console.error('获取支持格式失败:', error);
            throw error;
        }
    }
}

// 流媒体检测器类
class StreamDetector {
    constructor(streamManager) {
        this.streamManager = streamManager;
        this.isDetecting = false;
        this.currentStreamId = null;
        this.detectionInterval = null;
        this.videoElement = null;
        this.canvasElement = null;
        this.onDetectionResult = null;
        
        // 添加页面关闭事件监听器
        this.addPageUnloadListener();
    }
    
    // 添加页面关闭事件监听器
    addPageUnloadListener() {
        window.addEventListener('beforeunload', () => {
            console.log('Page unloading, stopping stream detection');
            this.stopDetection();
        });
        
        // 页面隐藏时也停止检测
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden' && this.isDetecting) {
                console.log('Page hidden, stopping stream detection');
                this.stopDetection();
            }
        });
    }

    /**
     * 开始流媒体检测
     * @param {string} streamId - 流媒体ID
     * @param {string} modelId - 模型ID
     * @param {Object} options - 检测选项
     */
    async startDetection(streamId, modelId, options = {}) {
        if (this.isDetecting) {
            throw new Error('检测已在进行中');
        }

        try {
            // 获取流媒体信息
            const streamInfo = await this.streamManager.getStreamInfo(streamId);
            if (!streamInfo.is_running) {
                throw new Error('流媒体未运行');
            }

            this.currentStreamId = streamId;
            this.isDetecting = true;

            // 设置视频元素
            if (this.videoElement) {
                const mjpegUrl = this.streamManager.getMjpegUrl(streamId);
                this.videoElement.src = mjpegUrl;
                this.videoElement.load();
            }

            // 开始检测循环
            this.startDetectionLoop(modelId, options);

        } catch (error) {
            this.isDetecting = false;
            throw error;
        }
    }

    /**
     * 停止流媒体检测
     */
    stopDetection() {
        this.isDetecting = false;
        this.currentStreamId = null;

        // 清除检测循环
        if (this.detectionInterval) {
            window.memoryManager.clearInterval(this.detectionInterval);
            this.detectionInterval = null;
        }

        // 清除视频元素
        if (this.videoElement) {
            this.videoElement.src = '';
            this.videoElement.load();
        }

        // 清除画布内容
        if (this.canvasElement) {
            const ctx = this.canvasElement.getContext('2d');
            ctx.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height);
        }

        // 重置检测结果回调
        this.onDetectionResult = null;
    }

    /**
     * 开始检测循环
     * @param {string} modelId - 模型ID
     * @param {Object} options - 检测选项
     */
    startDetectionLoop(modelId, options) {
        // 清除任何现有的检测循环
        if (this.detectionInterval) {
            window.memoryManager.clearInterval(this.detectionInterval);
            this.detectionInterval = null;
        }

        const detectFrame = async () => {
            // 检查是否应该继续检测
            if (!this.isDetecting || !this.currentStreamId) {
                console.log('Stream detection stopped, exiting detection loop');
                return;
            }

            try {
                // 获取当前帧
                const frameUrl = this.streamManager.getFrameUrl(this.currentStreamId);
                const response = await fetch(frameUrl);
                
                // 再次检查是否应该继续检测
                if (!this.isDetecting || !this.currentStreamId) {
                    return;
                }
                
                if (response.ok) {
                    const blob = await response.blob();
                    // 再次检查是否应该继续检测
                    if (!this.isDetecting || !this.currentStreamId) {
                        return;
                    }
                    
                    const file = new File([blob], `frame_${Date.now()}.jpg`, { type: 'image/jpeg' });

                    // 发送检测请求
                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('model_id', modelId);
                    formData.append('conf_thres', options.confThreshold || 0.25);
                    formData.append('iou_thres', options.iouThreshold || 0.45);

                    const detectionResponse = await fetch('/api/detection/', {
                        method: 'POST',
                        body: formData
                    });

                    // 再次检查是否应该继续检测
                    if (!this.isDetecting || !this.currentStreamId) {
                        return;
                    }

                    if (detectionResponse.ok) {
                        const detectionData = await detectionResponse.json();
                        
                        // 再次检查是否应该继续检测
                        if (!this.isDetecting || !this.currentStreamId) {
                            return;
                        }
                        
                        if (detectionData && detectionData.id) {
                            // 获取检测结果
                            const resultResponse = await fetch(`/api/detection/${detectionData.id}/result`);
                            const resultData = await resultResponse.json();

                            // 再次检查是否应该继续检测
                            if (!this.isDetecting || !this.currentStreamId) {
                                return;
                            }

                            if (resultData.status === 'completed' && this.onDetectionResult) {
                                this.onDetectionResult(resultData.results);
                            }
                        }
                    }
                }
            } catch (error) {
                console.error('检测帧失败:', error);
                // 即使出错也继续检测循环（除非明确停止）
                if (this.isDetecting && this.currentStreamId) {
                    console.log('Continuing detection despite error');
                }
            }
            
            // 继续检测循环（如果仍在检测中）
            if (this.isDetecting && this.currentStreamId) {
                this.detectionInterval = window.memoryManager.setInterval(detectFrame, 33);
            }
        };

        // 设置检测间隔（约30fps）
        this.detectionInterval = window.memoryManager.setInterval(detectFrame, 33);
    }

    /**
     * 设置视频元素
     * @param {HTMLVideoElement} videoElement - 视频元素
     */
    setVideoElement(videoElement) {
        this.videoElement = videoElement;
    }

    /**
     * 设置画布元素
     * @param {HTMLCanvasElement} canvasElement - 画布元素
     */
    setCanvasElement(canvasElement) {
        this.canvasElement = canvasElement;
    }

    /**
     * 设置检测结果回调
     * @param {Function} callback - 回调函数
     */
    setDetectionResultCallback(callback) {
        this.onDetectionResult = callback;
    }
}

// 导出全局实例
window.streamManager = new StreamManager();
window.streamDetector = new StreamDetector(window.streamManager);

// 流媒体功能检查
function checkStreamingFunctions() {
    // 1. 检查新建流媒体功能
    const createStreamForm = document.getElementById('create-stream-form');
    if (createStreamForm) {
        createStreamForm.addEventListener('submit', function(e) {
            e.preventDefault();
            createStream();
        });
    }

    // 2. 检查测试连接功能
    const testConnectionBtn = document.getElementById('test-connection-btn');
    if (testConnectionBtn) {
        testConnectionBtn.addEventListener('click', testStreamConnection);
    }

    // 3. 检查流媒体应用功能
    const applyStreamBtn = document.getElementById('apply-stream-btn');
    if (applyStreamBtn) {
        applyStreamBtn.addEventListener('click', applyStream);
    }
}

// 创建流媒体
async function createStream() {
    const source = document.getElementById('stream-source').value;
    const type = document.getElementById('stream-type').value;

    if (!source) {
        alert('请输入流媒体地址');
        return;
    }

    try {
        const streamId = await window.streamManager.createStream(source, type);
        await window.streamManager.startStream(streamId);
        alert('流媒体创建并启动成功！');
        
        // 刷新列表
        if (typeof loadStreamsList === 'function') {
            loadStreamsList();
        }
    } catch (error) {
        alert('创建流媒体失败: ' + error.message);
    }
}

// 测试流媒体连接
async function testStreamConnection() {
    const source = document.getElementById('stream-source').value;
    const type = document.getElementById('stream-type').value;

    if (!source) {
        alert('请输入流媒体地址');
        return;
    }

    try {
        const result = await window.streamManager.testConnection(source, type);
        if (result.success) {
            alert('连接测试成功！');
        } else {
            alert('连接测试失败: ' + result.message);
        }
    } catch (error) {
        alert('连接测试失败: ' + error.message);
    }
}

// 应用流媒体到检测
function applyStream() {
    const streamId = document.getElementById('stream-select').value;
    if (!streamId) {
        alert('请选择一个流媒体');
        return;
    }

    // 这里可以添加将流媒体应用到检测的逻辑
    console.log('应用流媒体:', streamId);
}

// 初始化流媒体功能检查
document.addEventListener('DOMContentLoaded', function() {
    checkStreamingFunctions();
});