// 旋转框工具类
class OBBTool {
    constructor(annotationTool) {
        this.annotationTool = annotationTool;
        this.isDrawing = false;
        this.isRotating = false;
        this.currentBox = null;
        this.rotationCenter = null;
        this.startAngle = 0;
        this.currentAngle = 0;
    }

    // 开始绘制旋转框
    startDrawing(e) {
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);
        
        if (!this.isDrawing) {
            this.isDrawing = true;
            this.startX = canvasX;
            this.startY = canvasY;
            console.log('开始绘制旋转框:', canvasX, canvasY);
        }
    }

    // 绘制过程中
    onDrawing(e) {
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);
        
        if (this.isDrawing) {
            this.currentBox = {
                x: Math.min(this.startX, canvasX),
                y: Math.min(this.startY, canvasY),
                width: Math.abs(canvasX - this.startX),
                height: Math.abs(canvasY - this.startY),
                angle: 0 // 初始角度为0
            };
            
            console.log('旋转框绘制过程中:', this.currentBox);
            this.annotationTool.redraw();
        }
    }

    // 完成绘制
    finishDrawing() {
        if (this.isDrawing && this.currentBox && this.currentBox.width > 5 && this.currentBox.height > 5) {
            // 创建旋转框标注
            const obbAnnotation = {
                class_id: this.annotationTool.selectedClass,
                x: this.currentBox.x,
                y: this.currentBox.y,
                width: this.currentBox.width,
                height: this.currentBox.height,
                angle: this.currentBox.angle
            };
            
            // 添加到标注数组
            this.annotationTool.annotations.push(obbAnnotation);
            
            // 更新标注列表
            this.annotationTool.updateAnnotationList();
            
            // 重置状态
            this.isDrawing = false;
            this.currentBox = null;
            
            // 重新绘制
            this.annotationTool.redraw();
            
            // 保存标注
            setTimeout(() => {
                this.annotationTool.saveAnnotation();
            }, 100);
        }
    }

    // 开始旋转
    startRotation(e, annotation) {
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);
        
        this.isRotating = true;
        this.rotationAnnotation = annotation;
        this.rotationCenter = {
            x: annotation.x + annotation.width / 2,
            y: annotation.y + annotation.height / 2
        };
        
        // 计算起始角度
        const dx = canvasX - this.rotationCenter.x;
        const dy = canvasY - this.rotationCenter.y;
        this.startAngle = Math.atan2(dy, dx);
        this.currentAngle = annotation.angle || 0;
    }

    // 旋转过程中
    onRotating(e) {
        if (!this.isRotating || !this.rotationAnnotation) return;
        
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);
        
        // 计算当前角度
        const dx = canvasX - this.rotationCenter.x;
        const dy = canvasY - this.rotationCenter.y;
        const currentAngle = Math.atan2(dy, dx);
        
        // 计算角度差
        let angleDiff = currentAngle - this.startAngle;
        
        // 更新旋转框角度（确保角度在 [0, 2π] 范围内）
        let newAngle = this.currentAngle + angleDiff;
        while (newAngle >= 2 * Math.PI) {
            newAngle -= 2 * Math.PI;
        }
        while (newAngle < 0) {
            newAngle += 2 * Math.PI;
        }
        
        this.rotationAnnotation.angle = newAngle;
        
        // 重新绘制
        this.annotationTool.redraw();
    }

    // 完成旋转
    finishRotation() {
        this.isRotating = false;
        this.rotationAnnotation = null;
        this.rotationCenter = null;
        
        // 保存标注
        this.annotationTool.saveAnnotation();
    }

    // 通过键盘调整旋转角度
    adjustRotation(angleDelta) {
        if (this.annotationTool.selectedAnnotation && this.annotationTool.selectedAnnotation.hasOwnProperty('angle')) {
            // 调整角度（弧度）
            let newAngle = (this.annotationTool.selectedAnnotation.angle || 0) + angleDelta;
            
            // 限制角度在 [0, 2π] 范围内，符合YOLO格式要求
            while (newAngle >= 2 * Math.PI) {
                newAngle -= 2 * Math.PI;
            }
            while (newAngle < 0) {
                newAngle += 2 * Math.PI;
            }
            
            this.annotationTool.selectedAnnotation.angle = newAngle;
            
            // 重新绘制
            this.annotationTool.redraw();
            
            // 更新标注列表
            this.annotationTool.updateAnnotationList();
            
            // 保存标注
            this.annotationTool.saveAnnotation();
        }
    }

    // 重新绘制旋转框
    redraw() {
        if (!this.annotationTool.currentImage) return;
        
        // 绘制已完成的旋转框
        this.annotationTool.annotations.forEach((ann, index) => {
            if (ann.hasOwnProperty('angle')) {
                const isSelected = this.annotationTool.selectedAnnotation === ann;
                this.drawOBB(ann, this.annotationTool.getClassColor(ann.class_id), false, index + 1, isSelected);
            }
        });
        
        // 绘制当前正在绘制的旋转框
        if (this.currentBox) {
            this.drawOBB(this.currentBox, this.annotationTool.getClassColor(this.annotationTool.selectedClass), true);
        }
    }

    // 绘制旋转框
    drawOBB(box, color, isDrawing = false, index = null, isSelected = false) {
        this.annotationTool.ctx.save();
        
        // 设置边框颜色
        let borderColor;
        if (isDrawing) {
            borderColor = '#2196F3';
        } else if (isSelected) {
            borderColor = '#44FF44'; // 选中时使用绿色
        } else {
            // 将十六进制颜色转换为 RGBA 格式，设置 50% 透明度
            if (color.startsWith('#')) {
                const r = parseInt(color.substr(1, 2), 16);
                const g = parseInt(color.substr(3, 2), 16);
                const b = parseInt(color.substr(5, 2), 16);
                borderColor = `rgba(${r}, ${g}, ${b}, 0.5)`;
            } else {
                // 如果不是十六进制颜色，使用原来的格式
                borderColor = color + '80';
            }
        }
        
        // 保存当前上下文
        this.annotationTool.ctx.save();
        
        // 移动到旋转中心
        const centerX = box.x + box.width / 2;
        const centerY = box.y + box.height / 2;
        this.annotationTool.ctx.translate(centerX, centerY);
        
        // 旋转
        const angle = box.angle || 0;
        this.annotationTool.ctx.rotate(angle);
        
        // 绘制矩形（相对于旋转中心）
        this.annotationTool.ctx.strokeStyle = borderColor;
        this.annotationTool.ctx.lineWidth = isSelected ? 3 : (isDrawing ? 3 : 2);
        this.annotationTool.ctx.strokeRect(-box.width / 2, -box.height / 2, box.width, box.height);
        
        // 恢复上下文
        this.annotationTool.ctx.restore();
        
        // 绘制旋转控制点（仅在选中时显示）
        if (isSelected && !isDrawing) {
            // 保存当前上下文
            this.annotationTool.ctx.save();
            
            // 移动到旋转中心
            this.annotationTool.ctx.translate(centerX, centerY);
            
            // 旋转
            this.annotationTool.ctx.rotate(angle);
            
            // 右侧旋转控制点
            this.annotationTool.ctx.fillStyle = '#44FF44';
            this.annotationTool.ctx.beginPath();
            this.annotationTool.ctx.arc(box.width / 2 - 5, 0, 6, 0, Math.PI * 2);
            this.annotationTool.ctx.fill();
            
            // 左侧旋转控制点
            this.annotationTool.ctx.beginPath();
            this.annotationTool.ctx.arc(-box.width / 2 + 5, 0, 6, 0, Math.PI * 2);
            this.annotationTool.ctx.fill();
            
            // 恢复上下文
            this.annotationTool.ctx.restore();
        }
        
        // 绘制序号和类别标签
        if (!isDrawing) {
            const className = this.annotationTool.projectData.classes[box.class_id] || '未知';
            let label = className;
            if (index !== null) {
                label = `${index}. ${className}`;
            }
            
            // 标签背景使用半透明颜色
            if (isSelected) {
                this.annotationTool.ctx.fillStyle = 'rgba(68, 255, 68, 0.7)'; // 半透明绿色
            } else {
                // 将颜色转换为半透明格式
                if (color.startsWith('#')) {
                    const r = parseInt(color.substr(1, 2), 16);
                    const g = parseInt(color.substr(3, 2), 16);
                    const b = parseInt(color.substr(5, 2), 16);
                    this.annotationTool.ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.7)`;
                } else {
                    // 如果不是十六进制颜色，使用默认半透明白色背景
                    this.annotationTool.ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                }
            }
            
            // 计算标签位置（考虑旋转后的坐标）
            const labelX = box.x;
            const labelY = box.y - 20;
            
            this.annotationTool.ctx.fillRect(labelX, labelY, this.annotationTool.ctx.measureText(label).width + 10, 20);
            this.annotationTool.ctx.fillStyle = 'white';
            this.annotationTool.ctx.font = '12px Arial';
            this.annotationTool.ctx.fillText(label, labelX + 5, labelY + 15);
            
            // 显示角度信息
            if (box.angle !== undefined) {
                const angleText = `角度: ${(box.angle * 180 / Math.PI).toFixed(1)}°`;
                const angleTextWidth = this.annotationTool.ctx.measureText(angleText).width;
                this.annotationTool.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
                this.annotationTool.ctx.fillRect(box.x, box.y + box.height + 5, angleTextWidth + 10, 20);
                this.annotationTool.ctx.fillStyle = 'white';
                this.annotationTool.ctx.fillText(angleText, box.x + 5, box.y + box.height + 20);
            }
        }
        
        this.annotationTool.ctx.restore();
    }

    // 删除旋转框标注
    removeOBB(index) {
        const obbIndex = this.annotationTool.annotations.findIndex(ann => ann.hasOwnProperty('angle') && index-- === 0);
        if (obbIndex !== -1) {
            this.annotationTool.annotations.splice(obbIndex, 1);
            this.annotationTool.updateAnnotationList();
            this.annotationTool.redraw();
            // 实时保存
            this.annotationTool.saveAnnotation();
        }
    }

    // 转换为YOLO格式
    toYoloFormat(obb) {
        // 计算中心点坐标（归一化）
        const x_center = (obb.x + obb.width / 2) / this.annotationTool.canvas.width;
        const y_center = (obb.y + obb.height / 2) / this.annotationTool.canvas.height;
        
        // 计算宽高（归一化）
        const width = obb.width / this.annotationTool.canvas.width;
        const height = obb.height / this.annotationTool.canvas.height;
        
        // 角度（弧度）
        const angle = obb.angle || 0;
        
        return `${obb.class_id} ${x_center.toFixed(6)} ${y_center.toFixed(6)} ${width.toFixed(6)} ${height.toFixed(6)} ${angle.toFixed(6)}`;
    }
    
    // 检查指定位置是否有旋转框
    getObbAtPosition(x, y) {
        // 从后往前遍历，优先选中上层的标注
        for (let i = this.annotationTool.annotations.length - 1; i >= 0; i--) {
            const ann = this.annotationTool.annotations[i];
            
            // 检查是否为旋转框标注
            if (ann.hasOwnProperty('angle')) {
                if (this.isPointInRotatedRect(ann, x, y)) {
                    return ann;
                }
            }
        }
        return null;
    }
    
    // 检查点是否在旋转矩形内
    isPointInRotatedRect(rect, x, y) {
        // 计算矩形中心点
        const centerX = rect.x + rect.width / 2;
        const centerY = rect.y + rect.height / 2;
        
        // 将点相对于矩形中心进行旋转，以抵消矩形的旋转
        const angle = -(rect.angle || 0);
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        
        // 逆向旋转点
        const dx = x - centerX;
        const dy = y - centerY;
        const rotatedX = dx * cos - dy * sin + centerX;
        const rotatedY = dx * sin + dy * cos + centerY;
        
        // 检查旋转后的点是否在未旋转的矩形内
        return rotatedX >= rect.x &&
               rotatedX <= rect.x + rect.width &&
               rotatedY >= rect.y &&
               rotatedY <= rect.y + rect.height;
    }
    
    // 检查是否点击了旋转控制点
    isRotationHandleClicked(obb, x, y) {
        const centerX = obb.x + obb.width / 2;
        const centerY = obb.y + obb.height / 2;
        
        // 将点相对于矩形中心进行旋转，以匹配旋转后的控制点位置
        const angle = obb.angle || 0;
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        
        // 右侧控制点的原始位置
        const originalRightX = obb.x + obb.width / 2 + obb.width / 2;
        const originalRightY = obb.y + obb.height / 2;
        
        // 左侧控制点的原始位置
        const originalLeftX = obb.x + obb.width / 2 - obb.width / 2;
        const originalLeftY = obb.y + obb.height / 2;
        
        // 旋转后的控制点位置
        const rightX = centerX + (originalRightX - centerX) * cos - (originalRightY - centerY) * sin;
        const rightY = centerY + (originalRightX - centerX) * sin + (originalRightY - centerY) * cos;
        
        const leftX = centerX + (originalLeftX - centerX) * cos - (originalLeftY - centerY) * sin;
        const leftY = centerY + (originalLeftX - centerX) * sin + (originalLeftY - centerY) * cos;
        
        // 检查是否点击了右侧控制点
        if (x >= rightX - 10 && x <= rightX + 10 && y >= rightY - 10 && y <= rightY + 10) {
            return true;
        }
        
        // 检查是否点击了左侧控制点
        if (x >= leftX - 10 && x <= leftX + 10 && y >= leftY - 10 && y <= leftY + 10) {
            return true;
        }
        
        return false;
    }
    
    // 开始旋转
    startRotation(obb, x, y) {
        this.isRotating = true;
        this.rotationAnnotation = obb;
        this.rotationCenter = {
            x: obb.x + obb.width / 2,
            y: obb.y + obb.height / 2
        };
        
        // 计算起始角度
        const dx = x - this.rotationCenter.x;
        const dy = y - this.rotationCenter.y;
        this.startAngle = Math.atan2(dy, dx);
        this.currentAngle = obb.angle || 0;
    }
    
    // 完成旋转
    finishRotation() {
        this.isRotating = false;
        this.rotationAnnotation = null;
        this.rotationCenter = null;
        
        // 保存标注
        this.annotationTool.saveAnnotation();
    }
}

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OBBTool;
}