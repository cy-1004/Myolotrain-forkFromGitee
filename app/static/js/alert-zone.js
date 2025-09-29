/**
 * 报警区域设置功能
 * 允许用户在画面中划定特定区域，只在该区域内检测到目标物体时才触发报警
 */

// 报警区域相关变量
let alertZone = null;
let isDrawingZone = false;
let zoneStartX = 0;
let zoneStartY = 0;
let zoneEnabled = false;
let drawingCanvas = null;
let drawingContext = null;

// 初始化报警区域功能
document.addEventListener('DOMContentLoaded', function() {
    console.log('初始化报警区域功能');

    // 获取绘制区域按钮
    const drawZoneBtn = document.getElementById('draw-zone-btn');
    if (drawZoneBtn) {
        console.log('绑定绘制区域按钮点击事件');
        drawZoneBtn.addEventListener('click', function() {
            console.log('绘制区域按钮被点击');
            // 先创建画布，再调用startDrawingZone
            createDrawingCanvas();
            startDrawingZone();
        });
    } else {
        // 只在DEBUG模式下显示错误日志，并且当前页面需要报警区域功能
        // 检查是否存在全局DEBUG_MODE变量和currentPage变量
        if (typeof DEBUG_MODE !== 'undefined' && DEBUG_MODE) {
            // 假设需要报警区域功能的页面是'detection'或'streaming'等
            if (typeof currentPage !== 'undefined' && (currentPage === 'detection' || currentPage === 'streaming')) {
                console.error('未找到绘制区域按钮');
            }
        }
    }

    // 获取清除区域按钮
    const clearZoneBtn = document.getElementById('clear-zone-btn');
    if (clearZoneBtn) {
        clearZoneBtn.addEventListener('click', function() {
            console.log('清除区域按钮被点击');
            clearAlertZone(); // 直接调用内部函数
        });
    }

    // 调试功能已移除

    // 获取启用区域复选框
    const enableZoneCheck = document.getElementById('enable-alert-zone');
    if (enableZoneCheck) {
        enableZoneCheck.addEventListener('change', function() {
            zoneEnabled = this.checked;
            console.log('报警区域启用状态已更改:', zoneEnabled);

            // 如果启用但没有设置区域，提示用户绘制区域
            if (zoneEnabled && !alertZone) {
                alert('请先绘制报警区域');
                createDrawingCanvas();
                startDrawingZone();
            }

            // 保存设置
            saveZoneSettings();
        });
    }

    // 加载保存的区域设置
    loadZoneSettings();
});

/**
 * 创建绘制画布
 */
function createDrawingCanvas() {
    console.log('创建绘制画布');

    // 获取检测画布
    const detectionCanvas = document.getElementById('detection-canvas');
    if (!detectionCanvas) {
        console.error('未找到检测画布');
        alert('请先开始检测');
        return false;
    }

    // 获取检测结果容器
    const detectionContainer = detectionCanvas.parentElement;
    if (!detectionContainer) {
        console.error('未找到检测结果容器');
        alert('未找到检测结果容器，请先开始检测');
        return false;
    }

    console.log('检测画布大小:', detectionCanvas.width, detectionCanvas.height);

    // 如果画布大小为0，设置默认大小
    const canvasWidth = detectionCanvas.width || 640;
    const canvasHeight = detectionCanvas.height || 480;

    // 创建绘制画布（如果不存在）
    if (!drawingCanvas) {
        console.log('创建新的绘制画布');

        // 先移除现有的画布（如果有）
        const existingCanvas = document.getElementById('alert-zone-canvas');
        if (existingCanvas) {
            existingCanvas.parentElement.removeChild(existingCanvas);
        }

        drawingCanvas = document.createElement('canvas');
        drawingCanvas.id = 'alert-zone-canvas';
        drawingCanvas.className = 'position-absolute top-0 start-0';
        drawingCanvas.width = canvasWidth;
        drawingCanvas.height = canvasHeight;

        // 设置画布样式
        drawingCanvas.style.position = 'absolute';
        drawingCanvas.style.top = '0';
        drawingCanvas.style.left = '0';
        drawingCanvas.style.zIndex = '10';
        drawingCanvas.style.pointerEvents = 'auto';
        drawingCanvas.style.cursor = 'crosshair';

        // 设置容器样式
        detectionContainer.style.position = 'relative';

        // 将画布添加到检测结果容器
        detectionContainer.appendChild(drawingCanvas);

        // 获取绘图上下文
        drawingContext = drawingCanvas.getContext('2d');

        // 添加鼠标事件
        drawingCanvas.addEventListener('mousedown', startZoneDrawing);
        drawingCanvas.addEventListener('mousemove', continueZoneDrawing);
        drawingCanvas.addEventListener('mouseup', finishZoneDrawing);
        drawingCanvas.addEventListener('mouseleave', finishZoneDrawing);

        console.log('绘制画布创建完成，大小:', drawingCanvas.width, drawingCanvas.height);
    } else {
        // 如果画布已存在，确保它是可见的
        console.log('使用现有绘制画布');
        drawingCanvas.style.display = 'block';

        // 更新画布大小
        if (drawingCanvas.width !== canvasWidth || drawingCanvas.height !== canvasHeight) {
            console.log('更新画布大小:', canvasWidth, canvasHeight);
            drawingCanvas.width = canvasWidth;
            drawingCanvas.height = canvasHeight;
        }
    }

    return true;
}

// 调试功能已移除

/**
 * 开始绘制报警区域
 */
function startDrawingZone() {
    console.log('开始绘制报警区域');

    // 检查画布是否已创建
    if (!drawingCanvas || !drawingContext) {
        console.log('画布未创建，尝试创建画布');
        if (!createDrawingCanvas()) {
            console.error('创建画布失败');
            return;
        }
    }

    // 设置绘制状态
    isDrawingZone = true;

    console.log('绘制模式已启用:', isDrawingZone);

    // 清除现有区域
    clearDrawingCanvas();

    // 显示提示
    alert('请在检测结果画面上拖动鼠标绘制矩形报警区域');

    // 启用区域复选框
    document.getElementById('enable-alert-zone').checked = true;
    zoneEnabled = true;

    // 延迟检查绘制模式状态
    setTimeout(() => {
        console.log('延迟检查绘制模式状态:', isDrawingZone);
    }, 500);
}

/**
 * 开始绘制区域（鼠标按下）
 * @param {MouseEvent} e 鼠标事件
 */
function startZoneDrawing(e) {
    console.log('鼠标按下事件触发');
    console.log('当前绘制模式状态:', isDrawingZone);

    // 强制启用绘制模式
    if (!isDrawingZone) {
        console.log('强制启用绘制模式');
        isDrawingZone = true;
    }

    console.log('开始绘制区域');

    // 获取鼠标在画布上的位置
    const rect = drawingCanvas.getBoundingClientRect();
    zoneStartX = e.clientX - rect.left;
    zoneStartY = e.clientY - rect.top;

    console.log(`起始点坐标: (${zoneStartX}, ${zoneStartY})`);
    console.log('画布大小:', drawingCanvas.width, drawingCanvas.height);

    // 清除画布
    clearDrawingCanvas();

    // 绘制起始点
    drawingContext.fillStyle = 'rgba(255, 0, 0, 0.5)';
    drawingContext.fillRect(zoneStartX - 5, zoneStartY - 5, 10, 10);

    console.log('起始点绘制完成');
}

/**
 * 继续绘制区域（鼠标移动）
 * @param {MouseEvent} e 鼠标事件
 */
function continueZoneDrawing(e) {
    // 强制启用绘制模式
    if (!isDrawingZone) {
        console.log('鼠标移动: 强制启用绘制模式');
        isDrawingZone = true;
    }

    if (e.buttons !== 1) {
        return;
    }

    // 获取鼠标在画布上的位置
    const rect = drawingCanvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // 清除画布
    clearDrawingCanvas();

    // 绘制矩形
    const width = x - zoneStartX;
    const height = y - zoneStartY;

    console.log(`绘制矩形: 起点(${zoneStartX}, ${zoneStartY}), 宽高(${width}, ${height})`);

    drawingContext.fillStyle = 'rgba(255, 0, 0, 0.2)';
    drawingContext.fillRect(zoneStartX, zoneStartY, width, height);

    drawingContext.strokeStyle = 'rgba(255, 0, 0, 0.8)';
    drawingContext.lineWidth = 2;
    drawingContext.strokeRect(zoneStartX, zoneStartY, width, height);
}

/**
 * 完成绘制区域（鼠标释放）
 * @param {MouseEvent} e 鼠标事件
 */
function finishZoneDrawing(e) {
    console.log('鼠标释放事件触发', e.type);
    console.log('当前绘制模式状态:', isDrawingZone);

    // 强制启用绘制模式
    if (!isDrawingZone) {
        console.log('鼠标释放: 强制启用绘制模式');
        isDrawingZone = true;
    }

    if (e.type === 'mouseleave' && e.buttons !== 1) {
        console.log('鼠标离开画布且没有按下按钮，忽略');
        return;
    }

    console.log('完成绘制区域');

    // 获取鼠标在画布上的位置
    const rect = drawingCanvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    console.log(`终点坐标: (${x}, ${y})`);

    // 检查起始点是否存在
    if (typeof zoneStartX === 'undefined' || typeof zoneStartY === 'undefined') {
        console.log('起始点未定义，使用当前点作为起始点');
        zoneStartX = x - 100; // 创建一个默认的100x100的区域
        zoneStartY = y - 100;
    }

    // 计算区域
    let left = Math.min(zoneStartX, x);
    let top = Math.min(zoneStartY, y);
    let width = Math.abs(x - zoneStartX);
    let height = Math.abs(y - zoneStartY);

    console.log(`计算区域: 左上角(${left}, ${top}), 宽高(${width}, ${height})`);

    // 如果区域太小，使用默认大小
    if (width < 20 || height < 20) {
        console.log('区域太小，使用默认大小');
        width = Math.max(width, 100);
        height = Math.max(height, 100);
    }

    // 保存区域
    alertZone = { left, top, width, height };
    console.log('保存区域:', alertZone);

    // 绘制最终区域
    drawAlertZone();

    // 结束绘制状态
    isDrawingZone = false;

    // 保持绘制画布可见，但禁用绘制模式
    console.log('绘制完成，保持画布可见');

    // 保存设置
    saveZoneSettings();
}

/**
 * 绘制报警区域
 */
function drawAlertZone() {
    console.log('尝试绘制报警区域');

    if (!alertZone) {
        console.error('报警区域未定义');
        return;
    }

    if (!drawingContext) {
        console.error('绘图上下文未初始化');
        return;
    }

    console.log('绘制报警区域:', alertZone);

    // 清除画布
    clearDrawingCanvas();

    // 绘制区域
    drawingContext.fillStyle = 'rgba(255, 0, 0, 0.2)';
    drawingContext.fillRect(alertZone.left, alertZone.top, alertZone.width, alertZone.height);

    drawingContext.strokeStyle = 'rgba(255, 0, 0, 0.8)';
    drawingContext.lineWidth = 2;
    drawingContext.strokeRect(alertZone.left, alertZone.top, alertZone.width, alertZone.height);

    // 添加标签
    drawingContext.fillStyle = 'rgba(255, 0, 0, 0.8)';
    drawingContext.font = '14px Arial';
    drawingContext.fillText('报警区域', alertZone.left + 5, alertZone.top - 5);

    console.log('报警区域绘制完成');
}

/**
 * 清除绘制画布
 */
function clearDrawingCanvas() {
    if (drawingContext) {
        drawingContext.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
    }
}

/**
 * 清除报警区域
 */
function clearAlertZone() {
    console.log('清除报警区域');

    try {
        // 重置区域变量
        alertZone = null;

        // 检查画布是否存在
        if (!drawingCanvas || !drawingContext) {
            console.log('画布不存在，尝试创建');
            createDrawingCanvas();
        }

        // 清除画布
        if (drawingContext) {
            console.log('清除画布内容');
            clearDrawingCanvas();
        }

        // 禁用区域复选框
        const enableZoneCheck = document.getElementById('enable-alert-zone');
        if (enableZoneCheck) {
            console.log('禁用区域复选框');
            enableZoneCheck.checked = false;
            zoneEnabled = false;
        }

        // 保存设置
        console.log('保存设置');
        saveZoneSettings();

        // 显示提示
        alert('报警区域已清除');

        console.log('清除报警区域完成');
        return true;
    } catch (error) {
        console.error('清除报警区域失败:', error);
        alert('清除报警区域失败: ' + error.message);
        return false;
    }
}

/**
 * 保存区域设置
 */
function saveZoneSettings() {
    try {
        localStorage.setItem('alertZoneEnabled', zoneEnabled);
        localStorage.setItem('alertZone', JSON.stringify(alertZone));
    } catch (e) {
        console.error('保存报警区域设置失败:', e);
    }
}

/**
 * 加载区域设置
 */
function loadZoneSettings() {
    try {
        // 加载启用状态
        const enabled = localStorage.getItem('alertZoneEnabled');
        if (enabled !== null) {
            zoneEnabled = enabled === 'true';
            document.getElementById('enable-alert-zone').checked = zoneEnabled;
        }

        // 加载区域
        const zone = localStorage.getItem('alertZone');
        if (zone) {
            alertZone = JSON.parse(zone);
        }
    } catch (e) {
        console.error('加载报警区域设置失败:', e);
    }
}

/**
 * 检查目标是否在报警区域内
 * @param {Object} detection 检测结果对象
 * @returns {boolean} 是否在区域内
 */
function isInAlertZone(detection) {
    // 检查启用状态
    const checkboxElement = document.getElementById('enable-alert-zone');
    // 从复选框获取当前启用状态
    zoneEnabled = checkboxElement ? checkboxElement.checked : false;

    console.log('区域检查: 区域启用状态:', zoneEnabled);
    console.log('区域检查: 区域设置:', alertZone);

    // 如果未启用区域，返回true
    if (!zoneEnabled) {
        console.log('区域检查: 区域未启用，返回true');
        return true;
    }

    // 如果未设置区域，返回true
    if (!alertZone) {
        console.log('区域检查: 区域未设置，返回true');
        return true;
    }

    // 获取检测框
    const box = detection.bbox || detection.box;
    if (!box) {
        console.log('区域检查: 检测框不存在，返回true');
        return true;
    }

    let centerX, centerY;

    // 检查检测框格式
    if (Array.isArray(box)) {
        // 如果是数组格式 [x1, y1, x2, y2] 或 [x, y, width, height]
        if (box.length === 4) {
            if (box[2] > box[0] && box[3] > box[1]) {
                // 如果是 [x1, y1, x2, y2] 格式
                centerX = (box[0] + box[2]) / 2;
                centerY = (box[1] + box[3]) / 2;
            } else {
                // 如果是 [x, y, width, height] 格式
                centerX = box[0] + box[2] / 2;
                centerY = box[1] + box[3] / 2;
            }
        } else {
            console.log('区域检查: 检测框格式不支持，返回true');
            return true;
        }
    } else if (typeof box === 'object') {
        // 如果是对象格式 {x, y, width, height}
        centerX = box.x + box.width / 2;
        centerY = box.y + box.height / 2;
    } else {
        console.log('区域检查: 检测框格式不支持，返回true');
        return true;
    }

    // 检查中心点是否在区域内
    const inZone = (
        centerX >= alertZone.left &&
        centerX <= alertZone.left + alertZone.width &&
        centerY >= alertZone.top &&
        centerY <= alertZone.top + alertZone.height
    );

    console.log(`区域检查: 中心点(${centerX.toFixed(1)}, ${centerY.toFixed(1)}) 在区域内: ${inZone}`);
    return inZone;
}

/**
 * 调整报警区域大小
 * @param {number} width 新宽度
 * @param {number} height 新高度
 */
function resizeAlertZone(width, height) {
    console.log('调整报警区域大小:', width, height);

    // 获取检测画布
    const detectionCanvas = document.getElementById('detection-canvas');
    if (!detectionCanvas) {
        console.error('未找到检测画布');
        return;
    }

    // 获取检测结果容器
    const detectionContainer = detectionCanvas.parentElement;
    if (!detectionContainer) {
        console.error('未找到检测结果容器');
        return;
    }

    console.log('找到检测结果容器:', detectionContainer);

    // 创建绘制画布（如果不存在）
    if (!drawingCanvas) {
        console.log('创建新的绘制画布');

        drawingCanvas = document.createElement('canvas');
        drawingCanvas.id = 'alert-zone-canvas';
        drawingCanvas.className = 'position-absolute top-0 start-0';

        // 设置画布样式
        drawingCanvas.style.position = 'absolute';
        drawingCanvas.style.top = '0';
        drawingCanvas.style.left = '0';
        drawingCanvas.style.zIndex = '10';
        drawingCanvas.style.pointerEvents = 'auto';
        drawingCanvas.style.cursor = 'crosshair';

        // 设置容器样式
        detectionContainer.style.position = 'relative';

        // 将画布添加到检测结果容器
        detectionContainer.appendChild(drawingCanvas);

        // 获取绘图上下文
        drawingContext = drawingCanvas.getContext('2d');

        // 添加鼠标事件
        drawingCanvas.addEventListener('mousedown', startZoneDrawing);
        drawingCanvas.addEventListener('mousemove', continueZoneDrawing);
        drawingCanvas.addEventListener('mouseup', finishZoneDrawing);
        drawingCanvas.addEventListener('mouseleave', finishZoneDrawing);

        console.log('绘制画布创建完成');
    }

    // 调整画布大小
    drawingCanvas.width = width;
    drawingCanvas.height = height;
    console.log('画布大小调整为:', width, height);

    // 如果有保存的区域，重新绘制
    if (alertZone) {
        console.log('重新绘制保存的区域:', alertZone);
        drawAlertZone();
    }
}

// 导出函数供main.js使用
window.alertZone = {
    isInAlertZone,
    drawAlertZone,
    resizeAlertZone,
    clearAlertZone  // 添加清除区域函数
};
