/**
 * 自注意力追踪模块 - 前端JavaScript实现
 *
 * 该模块提供了与后端自注意力追踪服务交互的功能，包括：
 * 1. 摄像头追踪
 * 删除视频追踪功能（20250512）
 */

// 全局变量
let API_BASE_URL = '';
let TRACKING_API_URL = '';
let trackingPollingManager = null;

// 追踪状态
let isTracking = false;
let cameraStream = null;
let videoElement = null;
let canvasElement = null;
let canvasContext = null;
let detectionCanvasElement = null;
let detectionCanvasContext = null;
let animationFrameId = null;
let selectedTargetId = null;
let selectedClassId = null;
let selectedClassName = null;

// 在文档加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 获取API基础URL
    API_BASE_URL = window.API_URL || '/api';
    TRACKING_API_URL = `${API_BASE_URL}/tracking`;

    // 初始化轮询管理器
    try {
        if (typeof PollingManager === 'object') {
            trackingPollingManager = PollingManager;
            console.log('轮询管理器初始化成功');
        } else {
            console.warn('PollingManager未定义，跳过初始化');
            // 创建一个空对象，避免后续代码出错
            trackingPollingManager = {
                startPolling: function(url, interval, callback) {
                    console.warn('轮询功能不可用');
                    if (typeof callback === 'function') {
                        callback({ status: 'error', message: '轮询功能不可用' });
                    }
                },
                stopPolling: function() { console.warn('轮询功能不可用'); }
            };
        }
    } catch (error) {
        console.error('初始化轮询管理器失败:', error);
        // 创建一个空对象，避免后续代码出错
        trackingPollingManager = {
            startPolling: function(url, interval, callback) {
                console.warn('轮询功能不可用');
                if (typeof callback === 'function') {
                    callback({ status: 'error', message: '轮询功能不可用' });
                }
            },
            stopPolling: function() { console.warn('轮询功能不可用'); }
        };
    }
});

/**
 * 初始化追踪页面
 */
function initTrackingPage() {
    console.log('初始化追踪页面');

    // 加载模型列表
    loadModelsForTracking();

    // 加载流媒体列表
    loadStreamOptionsForTracking();

    // 绑定摄像头追踪相关事件
    initCameraTracking();
}

/**
 * 加载模型列表
 */
function loadModelsForTracking() {
    fetch(`${API_URL}/models/`)
        .then(response => response.json())
        .then(models => {
            // 填充摄像头追踪模型选择器
            const cameraTrackingModelSelect = document.getElementById('camera-tracking-model-select');
            if (cameraTrackingModelSelect) {
                // 保留默认选项
                const defaultOption = cameraTrackingModelSelect.querySelector('option');
                cameraTrackingModelSelect.innerHTML = '';
                cameraTrackingModelSelect.appendChild(defaultOption);

                // 添加模型选项
                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = `${model.name} (${model.type}, ${model.task})`;
                    cameraTrackingModelSelect.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('加载模型列表失败:', error);
        });
}

/**
 * 加载流媒体选项（用于目标追踪页面）
 */
function loadStreamOptionsForTracking() {
    fetch(`${API_URL}/streaming/list`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.streams) {
                const streamSelect = document.getElementById('tracking-stream-select');
                if (streamSelect) {
                    // 清空现有选项（除了第一个默认选项）
                    while (streamSelect.options.length > 1) {
                        streamSelect.remove(1);
                    }

                    // 添加流媒体选项
                    Object.entries(data.streams).forEach(([streamId, streamInfo]) => {
                        const option = document.createElement('option');
                        option.value = streamId;
                        option.textContent = `${streamId} - ${streamInfo.type} (${streamInfo.source})`;
                        streamSelect.appendChild(option);
                    });

                    // 如果没有流媒体，显示提示
                    if (Object.keys(data.streams).length === 0) {
                        const option = document.createElement('option');
                        option.value = "";
                        option.textContent = "没有可用的流媒体";
                        option.disabled = true;
                        streamSelect.appendChild(option);
                    }
                }
            }
        })
        .catch(error => {
            console.error('加载流媒体列表失败:', error);
            const streamSelect = document.getElementById('tracking-stream-select');
            if (streamSelect) {
                const option = document.createElement('option');
                option.value = "";
                option.textContent = "加载流媒体失败";
                option.disabled = true;
                streamSelect.appendChild(option);
            }
        });
}

/**
 * 初始化摄像头追踪
 */
function initCameraTracking() {
    console.log('初始化摄像头追踪');

    // 获取DOM元素
    videoElement = document.getElementById('camera-video');

    // 移除旧的画布元素（如果存在）
    const oldCanvas = document.getElementById('tracking-canvas');
    if (oldCanvas) {
        oldCanvas.parentNode.removeChild(oldCanvas);
    }

    // 创建新的画布元素 - 用于捕获视频帧
    canvasElement = document.createElement('canvas');
    canvasElement.id = 'tracking-canvas';
    canvasElement.className = 'position-absolute top-0 start-0';
    canvasElement.style.width = '100%';
    canvasElement.style.height = '100%';
    canvasElement.style.zIndex = '1000';
    canvasElement.style.position = 'absolute';
    canvasElement.style.top = '0';
    canvasElement.style.left = '0';
    canvasElement.style.display = 'block';
    canvasElement.style.pointerEvents = 'none';
    canvasElement.style.backgroundColor = 'transparent';

    // 创建新的检测框画布元素 - 专门用于绘制检测框和追踪框
    detectionCanvasElement = document.createElement('canvas');
    detectionCanvasElement.id = 'detection-canvas';
    detectionCanvasElement.className = 'position-absolute top-0 start-0';
    detectionCanvasElement.style.width = '100%';
    detectionCanvasElement.style.height = '100%';
    detectionCanvasElement.style.zIndex = '1001';  // 确保在视频和主画布之上
    detectionCanvasElement.style.position = 'absolute';
    detectionCanvasElement.style.top = '0';
    detectionCanvasElement.style.left = '0';
    detectionCanvasElement.style.display = 'block';
    detectionCanvasElement.style.pointerEvents = 'none';
    detectionCanvasElement.style.backgroundColor = 'transparent';

    // 将画布添加到视频容器中
    if (videoElement && videoElement.parentNode) {
        videoElement.parentNode.appendChild(canvasElement);
        videoElement.parentNode.appendChild(detectionCanvasElement);
        console.log('已创建并添加新的画布元素和检测框画布元素');
    } else {
        console.error('无法添加画布元素，因为视频元素或其父节点不存在');
    }

    // 绑定摄像头追踪按钮事件
    const startCameraTrackingButton = document.getElementById('start-camera-tracking');
    const stopCameraTrackingButton = document.getElementById('stop-camera-tracking');

    if (startCameraTrackingButton) {
        startCameraTrackingButton.addEventListener('click', startCameraTracking);
    }

    if (stopCameraTrackingButton) {
        stopCameraTrackingButton.addEventListener('click', stopCameraTracking);
    }

    // 绑定重置追踪器按钮事件
    const resetTrackingButton = document.getElementById('reset-tracking');
    if (resetTrackingButton) {
        resetTrackingButton.addEventListener('click', resetTracker);
    }
}

/**
 * 开始摄像头追踪
 */
function startCameraTracking() {
    try {
        console.log('开始摄像头追踪');

        // 检查是否已经在追踪
        if (isTracking) {
            console.log('已经在追踪中');
            return;
        }

        // 获取模型ID
        const modelSelect = document.getElementById('camera-tracking-model-select');
        const modelId = modelSelect ? modelSelect.value : 'default';
        console.log('模型ID:', modelId);

        // 获取追踪参数
        let confThreshold = 0.25; // 默认值
        let iouThreshold = 0.45; // 默认值

        const confThresholdElement = document.getElementById('camera-conf-threshold');
        if (confThresholdElement) {
            confThreshold = confThresholdElement.value;
            console.log('置信度阈值:', confThreshold);
        } else {
            console.warn('未找到置信度阈值元素，使用默认值:', confThreshold);
        }

        const iouThresholdElement = document.getElementById('camera-iou-threshold');
        if (iouThresholdElement) {
            iouThreshold = iouThresholdElement.value;
            console.log('IoU阈值:', iouThreshold);
        } else {
            console.warn('未找到IoU阈值元素，使用默认值:', iouThreshold);
        }

        // 显示追踪容器
        const trackingContainer = document.getElementById('camera-tracking-container');
        if (trackingContainer) {
            trackingContainer.style.display = 'block';
        } else {
            console.warn('未找到追踪容器元素');
        }

        // 显示停止按钮，隐藏开始按钮
        const startButton = document.getElementById('start-camera-tracking');
        const stopButton = document.getElementById('stop-camera-tracking');
        if (startButton) startButton.style.display = 'none';
        if (stopButton) stopButton.style.display = 'inline-block';

        // 更新追踪状态
        const trackingStatus = document.getElementById('camera-tracking-status');
        if (trackingStatus) {
            trackingStatus.textContent = '正在初始化摄像头...';
        } else {
            console.warn('未找到追踪状态元素');
        }
    } catch (error) {
        console.error('启动摄像头追踪时发生错误:', error);
        alert('启动摄像头追踪失败: ' + error.message);
    }

    // 获取摄像头设备ID和追踪状态元素
    const cameraSelect = document.getElementById('camera-select');
    const deviceId = cameraSelect ? cameraSelect.value : '';
    const trackingStatus = document.getElementById('camera-tracking-status');
    
    // 重置追踪器
    resetTracker()
        .then(() => {
            try {
                console.log('重置追踪器成功，准备打开摄像头');

                // 打开摄像头
                const constraints = {
                    video: deviceId ? { deviceId: { exact: deviceId } } : true
                };
                console.log('摄像头约束:', constraints);

                return navigator.mediaDevices.getUserMedia(constraints);
            } catch (error) {
                console.error('准备打开摄像头时出错:', error);
                throw error;
            }
        })
        .then(stream => {
            try {
                console.log('成功获取摄像头流');

                // 保存流
                cameraStream = stream;

                // 设置视频源
                if (videoElement) {
                    videoElement.srcObject = stream;
                    console.log('已设置视频源');

                    // 等待视频元数据加载
                    return new Promise(resolve => {
                        videoElement.onloadedmetadata = () => {
                            console.log('视频元数据已加载');
                            videoElement.play();
                            resolve();
                        };

                        // 添加错误处理
                        videoElement.onerror = (e) => {
                            console.error('视频加载错误:', e);
                            resolve(); // 继续流程
                        };

                        // 添加超时处理
                        setTimeout(() => {
                            if (videoElement.readyState === 0) {
                                console.warn('视频元数据加载超时，继续流程');
                                resolve();
                            }
                        }, 5000);
                    });
                } else {
                    console.error('视频元素不存在');
                    throw new Error('视频元素不存在');
                }
            } catch (error) {
                console.error('设置视频源时出错:', error);
                throw error;
            }
        })
        .then(() => {
            try {
                console.log('准备设置画布');

                // 设置画布大小
                if (canvasElement && videoElement) {
                    // 确保画布大小与视频实际大小匹配
                    // 如果视频尺寸不可用，使用固定的尺寸
                    const videoWidth = videoElement.videoWidth || 640;
                    const videoHeight = videoElement.videoHeight || 480;

                    // 确保画布尺寸不为0
                    canvasElement.width = videoWidth > 0 ? videoWidth : 640;
                    canvasElement.height = videoHeight > 0 ? videoHeight : 480;
                    console.log(`设置画布尺寸: ${canvasElement.width} x ${canvasElement.height}`);

                    // 获取2D绘图上下文
                    canvasContext = canvasElement.getContext('2d', { alpha: true });
                    if (!canvasContext) {
                        console.error('无法获取2D绘图上下文');
                    }

                    // 设置检测框画布的尺寸
                    if (detectionCanvasElement) {
                        detectionCanvasElement.width = canvasElement.width;
                        detectionCanvasElement.height = canvasElement.height;
                        console.log(`设置检测框画布尺寸: ${detectionCanvasElement.width} x ${detectionCanvasElement.height}`);

                        // 获取检测框画布的2D绘图上下文
                        detectionCanvasContext = detectionCanvasElement.getContext('2d', { alpha: true });
                        if (!detectionCanvasContext) {
                            console.error('无法获取检测框画布的2D绘图上下文');
                        }
                    } else {
                        console.error('检测框画布元素不存在');
                    }

                    // 只在调试模式下绘制测试矩形
                    window.DEBUG_MODE = false; // 默认关闭调试模式

                    // 获取视频容器元素
                    const videoContainer = videoElement.parentElement;
                    if (videoContainer) {
                        // 确保容器使用相对定位，这样画布的绝对定位才能正确工作
                        videoContainer.style.position = 'relative';
                        videoContainer.style.overflow = 'hidden';
                        console.log('设置视频容器样式:', videoContainer.style.cssText);
                    }

                    console.log('已设置画布样式');
                } else {
                    console.error('画布或视频元素不存在');
                    if (!canvasElement) console.error('画布元素不存在');
                    if (!videoElement) console.error('视频元素不存在');
                }

                // 更新追踪状态
                if (trackingStatus) {
                    trackingStatus.textContent = '追踪中...';
                    console.log('已更新追踪状态为"追踪中..."');
                }

                // 开始追踪
                isTracking = true;
                console.log('开始追踪，调用processFrame');
                requestAnimationFrame(processFrame);
            } catch (error) {
                console.error('设置画布时出错:', error);
                throw error;
            }
        })
        .catch(error => {
            console.error('启动摄像头追踪失败:', error);
            
            // 更新追踪状态
            if (trackingStatus) {
                trackingStatus.textContent = `启动失败: ${error.message}`;
            }

            // 显示简单错误提示
            let errorMessage = '启动摄像头追踪失败: ' + error.message;
            alert(errorMessage);
            
            // 恢复按钮状态
            const startButton = document.getElementById('start-camera-tracking');
            const stopButton = document.getElementById('stop-camera-tracking');
            if (startButton) startButton.style.display = 'inline-block';
            if (stopButton) stopButton.style.display = 'none';
            
            // 停止可能已经启动的摄像头流
            if (cameraStream) {
                cameraStream.getTracks().forEach(track => track.stop());
                cameraStream = null;
            }
        });
}

/**
 * 停止摄像头追踪
 */
function stopCameraTracking() {
    console.log('停止摄像头追踪');

    // 停止追踪
    isTracking = false;

    // 取消动画帧请求
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
        console.log('已取消动画帧请求');
    }

    // 停止摄像头流
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => {
            track.stop();
            console.log('已停止摄像头轨道:', track.kind);
        });
        cameraStream = null;
        console.log('已停止摄像头流');
    }

    // 清除视频源
    if (videoElement) {
        videoElement.srcObject = null;
        console.log('已清除视频源');
    }

    // 清除画布
    if (canvasContext && canvasElement) {
        canvasContext.clearRect(0, 0, canvasElement.width, canvasElement.height);
        console.log('已清除主画布');
    }

    // 清除检测框画布
    if (detectionCanvasContext && detectionCanvasElement) {
        detectionCanvasContext.clearRect(0, 0, detectionCanvasElement.width, detectionCanvasElement.height);
        console.log('已清除检测框画布');
    }

    // 显示开始按钮，隐藏停止按钮
    const startButton = document.getElementById('start-camera-tracking');
    const stopButton = document.getElementById('stop-camera-tracking');
    if (startButton) startButton.style.display = 'inline-block';
    if (stopButton) stopButton.style.display = 'none';
    console.log('已更新按钮显示状态');

    // 更新追踪状态
    const trackingStatus = document.getElementById('camera-tracking-status');
    if (trackingStatus) {
        trackingStatus.textContent = '已停止';
        console.log('已更新追踪状态为"已停止"');
    }

    // 重置选中的目标
    selectedTargetId = null;
    selectedClassId = null;
    selectedClassName = null;
    console.log('已重置选中的目标');

    // 清空检测到的目标列表
    updateDetectedObjectsList([]);
    // 清空追踪目标列表
    updateTrackedObjectsList([]);
    console.log('已清空目标列表');
}

/**
 * 重置追踪器
 */
function resetTracker() {
    console.log('重置追踪器');
    return Promise.resolve({});
}

/**
 * 根据ID生成颜色
 */
function getColorById(id) {
    // 使用固定的颜色列表
    const colors = [
        [255, 0, 0],    // 红色
        [0, 255, 0],    // 绿色
        [0, 0, 255],    // 蓝色
        [255, 255, 0],  // 黄色
        [255, 0, 255],  // 紫色
        [0, 255, 255],  // 青色
        [128, 0, 0],    // 深红色
        [0, 128, 0],    // 深绿色
        [0, 0, 128],    // 深蓝色
        [128, 128, 0]   // 橄榄色
    ];

    // 使用ID取模选择颜色
    return colors[id % colors.length];
}

/**
 * 更新检测到的目标列表
 */
function updateDetectedObjectsList(detections) {
    console.log('更新检测到的目标列表:', detections);

    // 获取检测到的目标列表容器
    const detectedObjectsList = document.getElementById('detected-objects-list');
    if (!detectedObjectsList) {
        console.warn('未找到检测到的目标列表容器');
        return;
    }

    // 清空列表
    detectedObjectsList.innerHTML = '';

    // 如果没有检测结果，显示提示信息
    if (!detections || detections.length === 0) {
        const emptyItem = document.createElement('li');
        emptyItem.className = 'list-group-item text-center';
        emptyItem.textContent = '未检测到目标';
        detectedObjectsList.appendChild(emptyItem);
        return;
    }

    // 按类别分组
    const groupedDetections = {};
    detections.forEach(det => {
        const className = det.class_name || 'unknown';
        const classId = det.class_id !== undefined ? det.class_id : -1;

        if (!groupedDetections[className]) {
            groupedDetections[className] = {
                count: 0,
                classId: classId,
                items: []
            };
        }

        groupedDetections[className].count++;
        groupedDetections[className].items.push(det);
    });

    // 为每个类别创建列表项
    Object.keys(groupedDetections).forEach(className => {
        const group = groupedDetections[className];
        const listItem = document.createElement('li');
        listItem.className = 'list-group-item d-flex justify-content-between align-items-center';

        // 创建类别名称和数量标签
        const nameSpan = document.createElement('span');
        nameSpan.textContent = `${className} (ID: ${group.classId})`;

        const countBadge = document.createElement('span');
        countBadge.className = 'badge bg-primary rounded-pill';
        countBadge.textContent = group.count;

        // 创建追踪按钮
        const trackButton = document.createElement('button');

        // 检查是否是当前选中的类别
        if (selectedClassId !== null && selectedClassId == group.classId) {
            trackButton.className = 'btn btn-sm btn-danger ms-2';
            trackButton.textContent = '取消追踪';
        } else {
            trackButton.className = 'btn btn-sm btn-success ms-2';
            trackButton.textContent = '追踪';
        }

        trackButton.dataset.classId = group.classId;
        trackButton.dataset.className = className;

        // 绑定追踪按钮点击事件
        trackButton.addEventListener('click', function() {
            console.log('追踪按钮被点击');

            // 检查当前按钮状态
            if (this.textContent === '追踪') {
                // 设置选中的类别
                selectedClassId = group.classId;
                selectedClassName = className;
                console.log(`选中类别: ${className} (ID: ${group.classId})`);

                // 更新按钮状态
                const allTrackButtons = document.querySelectorAll('#detected-objects-list button');
                allTrackButtons.forEach(btn => {
                    if (btn.dataset.classId == group.classId) {
                        btn.textContent = '取消追踪';
                        btn.className = 'btn btn-sm btn-danger ms-2';
                    } else {
                        btn.textContent = '追踪';
                        btn.className = 'btn btn-sm btn-success ms-2';
                    }
                });
            } else {
                // 取消选中
                selectedClassId = null;
                selectedClassName = null;
                this.textContent = '追踪';
                this.className = 'btn btn-sm btn-success ms-2';
                console.log('取消选中类别');

                // 发送取消追踪请求
                const cancelTrackingFormData = new FormData();
                cancelTrackingFormData.append('cancel_tracking', 'true');

                fetch(`${TRACKING_API_URL}/track-frame`, {
                    method: 'POST',
                    body: cancelTrackingFormData
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`取消追踪请求失败: ${response.status} ${response.statusText}`);
                    }
                    console.log('已发送取消追踪请求');
                })
                .catch(error => {
                    console.error('取消追踪请求错误:', error);
                });
            }
        });

        // 将元素添加到列表项
        listItem.appendChild(nameSpan);
        const rightGroup = document.createElement('div');
        rightGroup.appendChild(countBadge);
        rightGroup.appendChild(trackButton);
        listItem.appendChild(rightGroup);

        // 将列表项添加到容器
        detectedObjectsList.appendChild(listItem);
    });
}

/**
 * 更新追踪目标列表
 */
function updateTrackedObjectsList(tracks) {
    console.log('更新追踪目标列表:', tracks);

    // 获取追踪目标列表容器
    const trackedObjectsList = document.getElementById('tracked-objects-list');
    if (!trackedObjectsList) {
        console.warn('未找到追踪目标列表容器');
        return;
    }

    // 清空列表
    trackedObjectsList.innerHTML = '';

    // 如果没有追踪结果，显示提示信息
    if (!tracks || tracks.length === 0) {
        const emptyItem = document.createElement('li');
        emptyItem.className = 'list-group-item text-center';

        // 根据是否选择了追踪目标显示不同的提示信息
        if (selectedClassId !== null) {
            emptyItem.textContent = `正在等待类别ID为 ${selectedClassId} 的目标出现...`;
            emptyItem.style.color = 'blue';
        } else {
            emptyItem.textContent = '未选择追踪目标';
        }

        trackedObjectsList.appendChild(emptyItem);
        return;
    }

    // 如果在单目标追踪模式下，但没有该类别的追踪结果
    if (selectedClassId !== null && !tracks.some(track => track.class_id == selectedClassId)) {
        const emptyItem = document.createElement('li');
        emptyItem.className = 'list-group-item text-center';
        emptyItem.textContent = `正在等待类别ID为 ${selectedClassId} 的目标出现...`;
        emptyItem.style.color = 'blue';
        trackedObjectsList.appendChild(emptyItem);
        return;
    }

    // 在单目标追踪模式下，只显示选中类别的追踪目标
    const tracksToShow = selectedClassId !== null
        ? tracks.filter(track => track.class_id == selectedClassId)
        : tracks;

    // 为每个追踪目标创建列表项
    tracksToShow.forEach(track => {
        const listItem = document.createElement('li');
        listItem.className = 'list-group-item d-flex justify-content-between align-items-center';

        // 创建ID和类别标签
        const idSpan = document.createElement('span');

        // 确保显示正确的类别名称和ID
        const className = track.class_name || '未知';
        const classId = track.class_id !== undefined ? track.class_id : '未知';
        const confidence = Math.round((track.confidence || 0) * 100);

        idSpan.textContent = `ID: ${track.id} - ${className} (类别ID: ${classId}, 置信度: ${confidence}%)`;

        // 根据ID生成颜色
        const color = getColorById(track.id);
        const colorStr = `rgb(${color[0]}, ${color[1]}, ${color[2]})`;

        // 创建颜色标记
        const colorMark = document.createElement('span');
        colorMark.className = 'color-mark me-2';
        colorMark.style.display = 'inline-block';
        colorMark.style.width = '12px';
        colorMark.style.height = '12px';
        colorMark.style.backgroundColor = colorStr;
        colorMark.style.borderRadius = '50%';

        // 将颜色标记添加到ID标签前面
        idSpan.insertBefore(colorMark, idSpan.firstChild);

        // 将元素添加到列表项
        listItem.appendChild(idSpan);

        // 将列表项添加到容器
        trackedObjectsList.appendChild(listItem);
    });

    // 如果过滤后没有追踪目标，显示提示信息
    if (selectedClassId !== null && tracksToShow.length === 0 && tracks.length > 0) {
        const emptyItem = document.createElement('li');
        emptyItem.className = 'list-group-item text-center';
        emptyItem.textContent = `未找到类别ID为 ${selectedClassId} 的追踪目标`;
        emptyItem.style.color = 'orange';
        trackedObjectsList.appendChild(emptyItem);
    }
}

/**
 * 绘制检测结果和追踪结果
 */
function drawDetectionsAndTracks(detections, tracks) {
    console.log('绘制检测和追踪结果:', {
        detections: detections ? detections.length : 0,
        tracks: tracks ? tracks.length : 0
    });

    // 如果检测框画布不存在，则退出
    if (!detectionCanvasElement || !detectionCanvasContext) {
        console.error('检测框画布不存在，无法绘制');
        return;
    }

    // 清除检测框画布
    detectionCanvasContext.clearRect(0, 0, detectionCanvasElement.width, detectionCanvasElement.height);

    // 绘制检测框
    if (detections && detections.length > 0) {
        detections.forEach(det => {
            // 如果在单目标追踪模式下，只显示选中类别的检测框
            if (selectedClassId !== null && det.class_id != selectedClassId) {
                return; // 跳过非选中类别的检测框
            }

            // 获取边界框
            const bbox = det.bbox;
            if (!bbox || bbox.length !== 4) {
                console.warn('无效的边界框:', bbox);
                return;
            }

            // 计算边界框坐标
            const x = bbox[0];
            const y = bbox[1];
            const width = bbox[2] - bbox[0];
            const height = bbox[3] - bbox[1];

            // 设置检测框样式
            detectionCanvasContext.strokeStyle = 'rgba(0, 255, 0, 0.8)';  // 绿色
            detectionCanvasContext.lineWidth = 2;
            detectionCanvasContext.setLineDash([]);  // 实线

            // 绘制检测框
            detectionCanvasContext.beginPath();
            detectionCanvasContext.rect(x, y, width, height);
            detectionCanvasContext.stroke();

            // 绘制类别标签
            const label = `${det.class_name} (${Math.round(det.confidence * 100)}%)`;
            detectionCanvasContext.font = '14px Arial';
            detectionCanvasContext.fillStyle = 'rgba(0, 255, 0, 0.8)';
            detectionCanvasContext.fillRect(x, y - 20, detectionCanvasContext.measureText(label).width + 10, 20);
            detectionCanvasContext.fillStyle = 'black';
            detectionCanvasContext.fillText(label, x + 5, y - 5);
        });
    }

    // 绘制追踪框
    if (tracks && tracks.length > 0) {
        tracks.forEach(track => {
            // 如果在单目标追踪模式下，只显示选中类别的追踪框
            if (selectedClassId !== null && track.class_id != selectedClassId) {
                return; // 跳过非选中类别的追踪框
            }

            // 获取边界框
            const bbox = track.bbox;
            if (!bbox || bbox.length !== 4) {
                console.warn('无效的追踪边界框:', bbox);
                return;
            }

            // 计算边界框坐标
            const x = bbox[0];
            const y = bbox[1];
            const width = bbox[2] - bbox[0];
            const height = bbox[3] - bbox[1];

            // 根据ID生成颜色
            const color = getColorById(track.id);
            const colorStr = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.8)`;

            // 设置追踪框样式
            detectionCanvasContext.strokeStyle = colorStr;
            detectionCanvasContext.lineWidth = 2;
            detectionCanvasContext.setLineDash([5, 5]);  // 虚线

            // 绘制追踪框
            detectionCanvasContext.beginPath();
            detectionCanvasContext.rect(x, y, width, height);
            detectionCanvasContext.stroke();

            // 绘制ID标签
            const label = `ID: ${track.id} - ${track.class_name}`;
            detectionCanvasContext.font = '14px Arial';
            detectionCanvasContext.fillStyle = colorStr;
            detectionCanvasContext.fillRect(x, y - 20, detectionCanvasContext.measureText(label).width + 10, 20);
            detectionCanvasContext.fillStyle = 'white';
            detectionCanvasContext.fillText(label, x + 5, y - 5);

            // 绘制轨迹
            if (track.trajectory && track.trajectory.length > 1) {
                detectionCanvasContext.strokeStyle = colorStr;
                detectionCanvasContext.lineWidth = 2;
                detectionCanvasContext.setLineDash([]);  // 实线

                detectionCanvasContext.beginPath();
                detectionCanvasContext.moveTo(track.trajectory[0][0], track.trajectory[0][1]);

                for (let i = 1; i < track.trajectory.length; i++) {
                    detectionCanvasContext.lineTo(track.trajectory[i][0], track.trajectory[i][1]);
                }

                detectionCanvasContext.stroke();
            }
        });
    }
}

// 帧率控制变量
let lastFrameTime = 0;
const FRAME_INTERVAL = 100; // 每100毫秒处理一帧，约等于10fps

/**
 * 处理视频帧
 */
function processFrame() {
    // 如果不在追踪状态，则退出
    if (!isTracking) {
        console.log('未在追踪状态，退出processFrame');
        return;
    }

    // 如果视频或画布元素不存在，则退出
    if (!videoElement || !canvasElement || !canvasContext) {
        console.error('视频或画布元素不存在，退出processFrame');
        return;
    }

    // 帧率控制 - 限制处理频率，减少资源占用
    const currentTime = Date.now();
    if (currentTime - lastFrameTime < FRAME_INTERVAL) {
        // 如果距离上一帧处理时间不足FRAME_INTERVAL，则跳过当前帧处理
        animationFrameId = requestAnimationFrame(processFrame);
        return;
    }
    lastFrameTime = currentTime;

    try {
        // 绘制视频帧到画布
        canvasContext.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);

        // 将画布转换为Blob对象
        canvasElement.toBlob(blob => {
            // 创建一个文件对象
            const file = new File([blob], "frame.jpg", { type: "image/jpeg" });

            // 创建FormData对象
            const formData = new FormData();
            formData.append('file', file);  // 使用'file'而不是'image'，与API期望一致

            // 获取模型ID
            const modelSelect = document.getElementById('camera-tracking-model-select');
            const modelId = modelSelect ? modelSelect.value : 'default';

            // 添加模型ID参数
            if (modelId && modelId !== 'default') {
                formData.append('model_id', modelId);
            }

            // 添加置信度和IoU阈值参数
            formData.append('conf_thres', 0.25);
            formData.append('iou_thres', 0.45);

            // 发送同步检测请求
            fetch(`${API_BASE_URL}/sync-detection/sync-detect`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`检测请求失败: ${response.status} ${response.statusText}`);
                }
                return response.json();
            })
            .catch(error => {
                console.error('检测请求错误:', error);
                // 返回一个空的检测结果，避免前端崩溃
                return { detections: [] };
            })
            .then(response => {
                // 提取检测结果
                let detections = [];

                if (response && response.detections && Array.isArray(response.detections)) {
                    // 使用detections字段
                    detections = response.detections;
                    console.log('使用API返回的检测结果');
                } else if (response && Array.isArray(response)) {
                    // 直接使用数组
                    detections = response;
                    console.log('使用API返回的检测结果数组');
                } else {
                    console.log('未找到有效的检测结果，使用空数组');
                    detections = [];
                }

                // 继续处理检测结果
                console.log('检测结果:', detections);

                // 如果没有检测结果，使用空数组
                if (detections.length === 0) {
                    console.log('没有检测结果');
                    detections = [];
                }

                console.log('检测结果:', detections);

                // 创建一个全局变量来存储格式化后的检测结果
                window.formattedDetections = [];

                // 格式化检测结果
                if (Array.isArray(detections)) {
                    window.formattedDetections = detections.map(det => {
                        // 处理不同格式的边界框
                        let bbox;
                        if (det.bbox) {
                            bbox = det.bbox;
                        } else {
                            // 默认边界框
                            bbox = [0, 0, 100, 100];
                        }

                        // 确保边界框坐标是数字
                        if (Array.isArray(bbox)) {
                            bbox = bbox.map(coord => {
                                const num = parseFloat(coord);
                                return isNaN(num) ? 0 : num;
                            });
                        } else {
                            // 如果bbox不是数组，使用默认值
                            bbox = [0, 0, 100, 100];
                        }

                        // 处理不同的字段名称
                        const class_id = det.class_id !== undefined ? det.class_id : 
                                        det.class !== undefined ? det.class : 0;
                        const confidence = det.confidence !== undefined ? det.confidence : 0.5;
                        const class_name = det.class_name || det.name || 'object';

                        return {
                            bbox: bbox,
                            class_id: class_id,
                            confidence: confidence,
                            class_name: class_name
                        };
                    });
                }

                console.log('格式化后的检测结果:', window.formattedDetections);

                // 更新检测到的目标列表
                updateDetectedObjectsList(window.formattedDetections);

                // 发送追踪请求
                const trackingFormData = new FormData();
                trackingFormData.append('image', file);  // 这里使用'image'是正确的，与API期望一致
                trackingFormData.append('detections', JSON.stringify(window.formattedDetections));

                // 添加追踪参数
                if (selectedClassId !== null) {
                    trackingFormData.append('target_class_id', selectedClassId);
                    trackingFormData.append('enable_tracking', 'true');
                    console.log('追踪请求使用类别ID:', selectedClassId);
                } else {
                    // 确保明确设置为false
                    trackingFormData.append('enable_tracking', 'false');
                }

                // 明确设置cancel_tracking参数
                trackingFormData.append('cancel_tracking', 'false');

                // 注意：tracking API不需要model_id参数
                console.log('发送追踪请求，检测结果数量:', window.formattedDetections.length);

                // 发送追踪请求
                fetch(`${TRACKING_API_URL}/track-frame`, {
                    method: 'POST',
                    body: trackingFormData
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`追踪请求失败: ${response.status} ${response.statusText}`);
                    }
                    return response.json();
                })
                .catch(error => {
                    console.error('追踪请求错误:', error);
                    // 返回一个空的追踪结果，避免前端崩溃
                    return { tracks: [] };
                })
                .then(response => {
                    // 如果没有追踪结果，返回空数组
                    if (!response.tracks || response.tracks.length === 0) {
                        console.log('没有追踪结果');
                        return { tracks: [] };
                    }

                    return response;
                })
                .then(response => {
                    console.log('追踪响应:', response);

                    // 提取追踪结果
                    let tracks = [];

                    if (response && response.tracks && Array.isArray(response.tracks)) {
                        // 使用tracks字段
                        tracks = response.tracks;
                        console.log('使用tracks字段中的追踪结果');
                    } else if (response && Array.isArray(response)) {
                        // 直接使用数组
                        tracks = response;
                        console.log('使用直接返回的追踪结果数组');
                    } else {
                        console.log('未找到有效的追踪结果');
                    }

                    // 如果选择了特定类别，只显示该类别的检测框
                    let detectionsToShow = window.formattedDetections;
                    if (selectedClassId !== null) {
                        detectionsToShow = window.formattedDetections.filter(det =>
                            det.class_id == selectedClassId || det.class_name == selectedClassName
                        );
                        console.log(`仅显示类别 ${selectedClassName} (ID: ${selectedClassId}) 的检测框，共 ${detectionsToShow.length} 个`);
                    }

                    // 保存当前的检测结果和追踪结果，以便在点击追踪按钮时能够重新绘制
                    // 只保存必要的数据，减少内存占用
                    window.currentDetections = detectionsToShow.map(det => ({
                        bbox: det.bbox,
                        class_id: det.class_id,
                        class_name: det.class_name,
                        confidence: det.confidence
                    }));

                    window.currentTracks = tracks.map(track => ({
                        id: track.id,
                        bbox: track.bbox,
                        class_id: track.class_id,
                        class_name: track.class_name,
                        confidence: track.confidence,
                        trajectory: track.trajectory ? track.trajectory.slice(-10) : [] // 只保留最近10个轨迹点
                    }));

                    // 绘制检测结果和追踪结果
                    drawDetectionsAndTracks(detectionsToShow, tracks);

                    // 更新追踪目标列表
                    updateTrackedObjectsList(tracks);

                    // 继续处理下一帧
                    animationFrameId = requestAnimationFrame(processFrame);
                })
                .catch(error => {
                    console.error('处理帧失败:', error);

                    // 继续处理下一帧
                    animationFrameId = requestAnimationFrame(processFrame);
                });
            });
        }, 'image/jpeg');
    } catch (error) {
        console.error('处理视频帧时出错:', error);

        // 继续处理下一帧
        animationFrameId = requestAnimationFrame(processFrame);
    }
}

// 在页面加载时注册追踪页面初始化函数
document.addEventListener('DOMContentLoaded', function() {
    // 将追踪页面初始化函数添加到页面加载函数中
    if (typeof loadPage === 'function') {
        const originalLoadPage = loadPage;
        loadPage = function(page) {
            originalLoadPage(page);
            if (page === 'tracking') {
                initTrackingPage();
            }
        };
    }
});
