/**
 * 轨迹记录和预测功能
 * 用于跟踪检测到的目标物体的运动轨迹并预测未来位置
 */

// 轨迹记录对象
const trajectories = {};

// 轨迹设置
const trajectorySettings = {
    enabled: false,           // 是否启用轨迹功能
    maxLength: 20,            // 最大轨迹长度
    predictionSteps: 3,       // 预测步数
    showTrajectoryLine: true, // 是否显示轨迹线
    showPredictionLine: true, // 是否显示预测线
    cleanupInterval: 2000,    // 清理不活跃轨迹的间隔(毫秒)
    inactiveThreshold: 5000   // 轨迹不活跃的阈值(毫秒)
};

// 上次清理时间
let lastCleanupTime = 0;

/**
 * 生成随机颜色
 * @returns {string} RGBA颜色字符串
 */
function getRandomColor() {
    const r = Math.floor(Math.random() * 200 + 55);
    const g = Math.floor(Math.random() * 200 + 55);
    const b = Math.floor(Math.random() * 200 + 55);
    return `rgba(${r}, ${g}, ${b}, 0.7)`;
}

/**
 * 跟踪目标物体，为每个目标分配唯一ID
 * @param {Array} detections 当前帧检测到的目标
 * @returns {Array} 带有ID的检测结果
 */
function trackObjects(detections) {
    const now = Date.now();
    const trackedObjects = [];
    
    // 为每个检测结果分配ID
    detections.forEach((detection, index) => {
        // 获取目标中心点
        const box = detection.bbox || detection.box;
        if (!box) return;
        
        let centerX, centerY;
        
        // 计算中心点坐标
        if (Array.isArray(box)) {
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
                return;
            }
        } else if (typeof box === 'object') {
            // 如果是对象格式 {x, y, width, height}
            centerX = box.x + box.width / 2;
            centerY = box.y + box.height / 2;
        } else {
            return;
        }
        
        // 获取类别名称
        let className = '';
        if (detection.class_name) {
            className = detection.class_name.toLowerCase();
        } else if (detection.class) {
            className = detection.class.toLowerCase();
        }
        
        // 尝试匹配现有轨迹
        let bestMatchId = null;
        let bestMatchDistance = Infinity;
        
        Object.keys(trajectories).forEach(id => {
            const trajectory = trajectories[id];
            if (trajectory.class !== className) return; // 类别必须匹配
            
            const points = trajectory.points;
            if (points.length === 0) return;
            
            const lastPoint = points[points.length - 1];
            const distance = Math.sqrt(
                Math.pow(centerX - lastPoint.x, 2) + 
                Math.pow(centerY - lastPoint.y, 2)
            );
            
            // 如果距离小于阈值且小于当前最佳匹配，更新最佳匹配
            if (distance < 50 && distance < bestMatchDistance) {
                bestMatchId = id;
                bestMatchDistance = distance;
            }
        });
        
        // 如果找到匹配的轨迹，使用该ID
        if (bestMatchId) {
            detection.id = bestMatchId;
        } else {
            // 否则创建新ID
            detection.id = `obj_${className}_${now}_${index}`;
        }
        
        trackedObjects.push(detection);
    });
    
    return trackedObjects;
}

/**
 * 更新目标轨迹
 * @param {Array} trackedObjects 带有ID的检测结果
 */
function updateTrajectories(trackedObjects) {
    const now = Date.now();
    
    // 更新现有轨迹
    trackedObjects.forEach(obj => {
        const id = obj.id;
        
        // 获取目标中心点
        const box = obj.bbox || obj.box;
        if (!box) return;
        
        let centerX, centerY;
        
        // 计算中心点坐标
        if (Array.isArray(box)) {
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
                return;
            }
        } else if (typeof box === 'object') {
            // 如果是对象格式 {x, y, width, height}
            centerX = box.x + box.width / 2;
            centerY = box.y + box.height / 2;
        } else {
            return;
        }
        
        // 获取类别名称
        let className = '';
        if (obj.class_name) {
            className = obj.class_name.toLowerCase();
        } else if (obj.class) {
            className = obj.class.toLowerCase();
        }
        
        // 如果是新目标，创建新轨迹
        if (!trajectories[id]) {
            trajectories[id] = {
                points: [],
                class: className,
                color: getRandomColor(),
                predictedPoints: []
            };
        }
        
        // 添加新位置点
        trajectories[id].points.push({
            x: centerX,
            y: centerY,
            timestamp: now
        });
        
        // 限制轨迹长度
        if (trajectories[id].points.length > trajectorySettings.maxLength) {
            trajectories[id].points.shift();
        }
        
        // 更新预测点
        trajectories[id].predictedPoints = predictTrajectory(trajectories[id]);
    });
    
    // 定期清理不活跃的轨迹
    if (now - lastCleanupTime > trajectorySettings.cleanupInterval) {
        cleanupInactiveTrajectories(now);
        lastCleanupTime = now;
    }
}

/**
 * 预测目标未来轨迹
 * @param {Object} trajectory 目标轨迹
 * @returns {Array} 预测的位置点
 */
function predictTrajectory(trajectory) {
    const points = trajectory.points;
    if (points.length < 3) return []; // 至少需要3个点才能预测
    
    // 使用简单的线性预测
    const predictedPoints = [];
    
    // 获取最近的几个点计算速度向量
    const n = points.length;
    const recentPoints = points.slice(Math.max(0, n - 3), n);
    
    if (recentPoints.length >= 2) {
        // 计算平均速度向量
        let avgVelocityX = 0;
        let avgVelocityY = 0;
        let avgTimeInterval = 0;
        
        for (let i = 1; i < recentPoints.length; i++) {
            const p1 = recentPoints[i - 1];
            const p2 = recentPoints[i];
            const dt = (p2.timestamp - p1.timestamp) / 1000; // 转换为秒
            
            if (dt > 0) {
                avgVelocityX += (p2.x - p1.x) / dt;
                avgVelocityY += (p2.y - p1.y) / dt;
                avgTimeInterval += dt;
            }
        }
        
        const divisor = recentPoints.length - 1;
        if (divisor > 0 && avgTimeInterval > 0) {
            avgVelocityX /= divisor;
            avgVelocityY /= divisor;
            avgTimeInterval /= divisor;
            
            // 预测未来位置
            const lastPoint = points[points.length - 1];
            for (let step = 1; step <= trajectorySettings.predictionSteps; step++) {
                predictedPoints.push({
                    x: lastPoint.x + avgVelocityX * avgTimeInterval * step,
                    y: lastPoint.y + avgVelocityY * avgTimeInterval * step
                });
            }
        }
    }
    
    return predictedPoints;
}

/**
 * 绘制轨迹和预测线
 * @param {CanvasRenderingContext2D} ctx 画布上下文
 */
function drawTrajectories(ctx) {
    if (!trajectorySettings.enabled) return;
    
    Object.values(trajectories).forEach(trajectory => {
        const points = trajectory.points;
        if (points.length < 2) return;
        
        // 绘制历史轨迹
        if (trajectorySettings.showTrajectoryLine) {
            ctx.beginPath();
            ctx.moveTo(points[0].x, points[0].y);
            
            for (let i = 1; i < points.length; i++) {
                ctx.lineTo(points[i].x, points[i].y);
            }
            
            ctx.strokeStyle = trajectory.color;
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // 绘制轨迹点
            points.forEach((point, index) => {
                // 越近的点越大
                const radius = 2 + (index / points.length) * 3;
                ctx.beginPath();
                ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
                ctx.fillStyle = trajectory.color;
                ctx.fill();
            });
        }
        
        // 绘制预测线
        if (trajectorySettings.showPredictionLine && trajectory.predictedPoints.length > 0) {
            const lastPoint = points[points.length - 1];
            
            ctx.beginPath();
            ctx.moveTo(lastPoint.x, lastPoint.y);
            
            trajectory.predictedPoints.forEach(point => {
                ctx.lineTo(point.x, point.y);
            });
            
            ctx.strokeStyle = 'rgba(255, 255, 0, 0.7)'; // 预测线使用黄色
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 3]); // 虚线
            ctx.stroke();
            ctx.setLineDash([]); // 恢复实线
            
            // 绘制预测点
            trajectory.predictedPoints.forEach((point, index) => {
                ctx.beginPath();
                ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(255, 255, 0, 0.7)';
                ctx.fill();
            });
        }
    });
}

/**
 * 清理不活跃的轨迹
 * @param {number} currentTime 当前时间戳
 */
function cleanupInactiveTrajectories(currentTime) {
    Object.keys(trajectories).forEach(id => {
        const trajectory = trajectories[id];
        const lastPoint = trajectory.points[trajectory.points.length - 1];
        
        // 如果轨迹长时间未更新，则删除
        if (currentTime - lastPoint.timestamp > trajectorySettings.inactiveThreshold) {
            delete trajectories[id];
        }
    });
}

/**
 * 清空所有轨迹
 */
function clearAllTrajectories() {
    Object.keys(trajectories).forEach(id => delete trajectories[id]);
}

/**
 * 更新轨迹设置
 * @param {Object} settings 新设置
 */
function updateTrajectorySettings(settings) {
    Object.assign(trajectorySettings, settings);
}

// 导出函数供main.js使用
window.trajectory = {
    trackObjects,
    updateTrajectories,
    drawTrajectories,
    clearAllTrajectories,
    updateTrajectorySettings,
    getSettings: () => trajectorySettings
};
