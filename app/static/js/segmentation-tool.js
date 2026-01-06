// 实例分割工具类
class SegmentationTool {
    constructor(annotationTool) {
        this.annotationTool = annotationTool;
        this.isDrawing = false;
        this.currentPoints = [];
        this.tempPoint = null;
        // 新增：用于跟踪正在拖拽的点
        this.isDraggingPoint = false;
        this.draggedPointIndex = -1;
        // 新增：用于跟踪整体拖动
        this.isDraggingSegment = false;
        this.segmentDragStartX = 0;
        this.segmentDragStartY = 0;
    }

    // 开始绘制分割区域
    startDrawing(e) {
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);
        
        // 如果是第一次点击，初始化点数组
        if (!this.isDrawing) {
            this.isDrawing = true;
            this.currentPoints = [];
        }
        
        // 添加点到当前点数组
        this.currentPoints.push({ x: canvasX, y: canvasY });
        this.tempPoint = null; // 清除临时点
        this.redraw();
        
        console.log('实例分割工具添加点，当前点数:', this.currentPoints.length);
    }

    // 新增：处理鼠标移动事件
    onMouseMove(e) {
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);
        
        // 只有在绘制过程中才更新临时点位置
        if (this.isDrawing) {
            this.tempPoint = { x: canvasX, y: canvasY };
            this.redraw();
        }
        // 如果正在拖拽点，则更新点位置
        else if (this.isDraggingPoint && this.draggedPointIndex >= 0) {
            // 更新被拖拽点的位置
            const selectedAnn = this.annotationTool.selectedAnnotation;
            if (selectedAnn && selectedAnn.points) {
                selectedAnn.points[this.draggedPointIndex][0] = canvasX;
                selectedAnn.points[this.draggedPointIndex][1] = canvasY;
                
                // 重新计算边界框
                this.updateBoundingBox(selectedAnn);
                
                // 重新绘制
                this.annotationTool.redraw();
            }
        }
        // 如果正在整体拖动分割区域，则更新所有点的位置
        else if (this.isDraggingSegment) {
            const selectedAnn = this.annotationTool.selectedAnnotation;
            if (selectedAnn && selectedAnn.points) {
                const deltaX = canvasX - this.segmentDragStartX;
                const deltaY = canvasY - this.segmentDragStartY;
                
                // 更新所有点的位置
                selectedAnn.points.forEach(point => {
                    point[0] += deltaX;
                    point[1] += deltaY;
                });
                
                // 更新边界框
                selectedAnn.x += deltaX;
                selectedAnn.y += deltaY;
                
                // 更新拖动起始位置
                this.segmentDragStartX = canvasX;
                this.segmentDragStartY = canvasY;
                
                // 重新绘制
                this.annotationTool.redraw();
            }
        }
    }
    
    // 新增：处理画布点击事件
    onCanvasClick(e) {
        // 实例分割工具的点击事件已经在startDrawing中处理
        // 这里可以添加额外的点击处理逻辑
        console.log('实例分割工具处理点击事件');
    }
    
    // 新增：处理画布双击事件
    onCanvasDoubleClick(e) {
        // 完成分割区域绘制
        this.finishDrawingOnDoubleClick(e);
    }

    // 更新边界框
    updateBoundingBox(annotation) {
        if (!annotation.points || annotation.points.length < 3) return;
        
        let minX = annotation.points[0][0], maxX = annotation.points[0][0];
        let minY = annotation.points[0][1], maxY = annotation.points[0][1];
        
        annotation.points.forEach(point => {
            minX = Math.min(minX, point[0]);
            maxX = Math.max(maxX, point[0]);
            minY = Math.min(minY, point[1]);
            maxY = Math.max(maxY, point[1]);
        });
        
        annotation.x = minX;
        annotation.y = minY;
        annotation.width = maxX - minX;
        annotation.height = maxY - minY;
    }

    // 双击完成绘制
    finishDrawingOnDoubleClick(e) {
        if (this.isDrawing && this.currentPoints.length >= 3) {
            this.finishDrawing();
        } else if (this.isDrawing) {
            // 如果点数不足3个，取消绘制
            this.cancelDrawing();
        }
    }

    // 完成分割区域绘制
    finishDrawing() {
        if (this.isDrawing && this.currentPoints.length >= 3) {
            // 计算边界框
            const points = this.currentPoints.map(p => [p.x, p.y]);
            let minX = 0, maxX = 1, minY = 0, maxY = 1;
            if (points.length > 0) {
                minX = points[0][0];
                maxX = points[0][0];
                minY = points[0][1];
                maxY = points[0][1];
                
                points.forEach(point => {
                    minX = Math.min(minX, point[0]);
                    maxX = Math.max(maxX, point[0]);
                    minY = Math.min(minY, point[1]);
                    maxY = Math.max(maxY, point[1]);
                });
                
                // 确保边界框有有效值
                if (minX >= maxX) {
                    maxX = minX + 1; // 避免除零错误
                }
                if (minY >= maxY) {
                    maxY = minY + 1; // 避免除零错误
                }
            }
            
            // 确保边界框值是有效的数字
            minX = isNaN(minX) ? 0 : minX;
            minY = isNaN(minY) ? 0 : minY;
            maxX = isNaN(maxX) ? 1 : maxX;
            maxY = isNaN(maxY) ? 1 : maxY;
            
            // 创建分割标注
            const segmentAnnotation = {
                class_id: this.annotationTool.selectedClass,
                points: points,
                x: minX,
                y: minY,
                width: maxX - minX,
                height: maxY - minY
            };
            
            // 添加到标注数组
            this.annotationTool.annotations.push(segmentAnnotation);
            
            // 更新标注列表
            this.annotationTool.updateAnnotationList();
            
            // 重置状态
            this.isDrawing = false;
            this.currentPoints = [];
            this.tempPoint = null;
            
            // 重新绘制
            this.annotationTool.redraw();
            
            // 保存标注
            setTimeout(() => {
                this.annotationTool.saveAnnotation();
            }, 100);
        }
    }

    // 取消当前绘制
    cancelDrawing() {
        this.isDrawing = false;
        this.currentPoints = [];
        this.tempPoint = null;
        this.annotationTool.redraw();
    }

    // 重新绘制分割区域
    redraw() {
        if (!this.annotationTool.currentImage) return;
        
        // 绘制所有类型的标注（包括分割标注和其他类型）
        this.annotationTool.annotations.forEach((ann, index) => {
            const isSelected = this.annotationTool.selectedAnnotation === ann;
            
            // 检查标注类型并使用相应的绘制方法
            if (ann.points) {
                // 实例分割标注
                this.annotationTool.drawSegmentAnnotation(ann, this.annotationTool.getClassColor(ann.class_id), false, index + 1, isSelected);
            } else {
                // 普通边界框标注和其他类型（旋转框、关键点等）
                this.annotationTool.drawBox(ann, this.annotationTool.getClassColor(ann.class_id), false, index + 1, isSelected);
            }
        });
        
        // 绘制当前正在绘制的分割区域
        if (this.isDrawing && this.currentPoints.length > 0) {
            this.drawCurrentSegment();
        }
    }

    // 绘制已完成的分割区域
    drawSegment(segment, color, isDrawing = false, index = null, isSelected = false) {
        if (!segment.points || segment.points.length < 3) return;
        
        this.annotationTool.ctx.save();
        
        // 设置边框颜色
        let borderColor;
        if (isDrawing) {
            borderColor = '#2196F3';
        } else if (isSelected) {
            borderColor = 'rgba(68, 255, 68, 0.5)'; // 选中时使用半透明绿色
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
        
        // 绘制填充区域
        this.annotationTool.ctx.fillStyle = borderColor;
        this.annotationTool.ctx.beginPath();
        this.annotationTool.ctx.moveTo(segment.points[0][0], segment.points[0][1]);
        for (let i = 1; i < segment.points.length; i++) {
            this.annotationTool.ctx.lineTo(segment.points[i][0], segment.points[i][1]);
        }
        this.annotationTool.ctx.closePath();
        this.annotationTool.ctx.fill();
        
        // 绘制边框
        this.annotationTool.ctx.strokeStyle = isSelected ? 'rgba(68, 255, 68, 0.7)' : '#FFFFFF';
        this.annotationTool.ctx.lineWidth = isSelected ? 3 : 2;
        this.annotationTool.ctx.stroke();
        
        // 绘制点
        segment.points.forEach((point, i) => {
            this.annotationTool.ctx.fillStyle = isSelected ? 'rgba(68, 255, 68, 0.7)' : '#FFFFFF';
            this.annotationTool.ctx.beginPath();
            this.annotationTool.ctx.arc(point[0], point[1], 4, 0, Math.PI * 2);
            this.annotationTool.ctx.fill();
            
            // 绘制序号
            if (!isDrawing) {
                this.annotationTool.ctx.fillStyle = '#FFFFFF';
                this.annotationTool.ctx.font = '12px Arial';
                this.annotationTool.ctx.fillText(i + 1, point[0] + 5, point[1] - 5);
            }
        });
        
        // 绘制序号和类别标签
        if (!isDrawing) {
            const className = this.annotationTool.projectData.classes[segment.class_id] || '未知';
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
            
            const textWidth = this.annotationTool.ctx.measureText(label).width;
            const textX = segment.points[0][0];
            const textY = segment.points[0][1] - 25;
            
            this.annotationTool.ctx.fillRect(textX, textY - 15, textWidth + 10, 20);
            this.annotationTool.ctx.fillStyle = 'black';
            this.annotationTool.ctx.font = '12px Arial';
            this.annotationTool.ctx.fillText(label, textX + 5, textY);
        }
        
        this.annotationTool.ctx.restore();
    }

    // 绘制当前正在绘制的分割区域
    drawCurrentSegment() {
        if (this.currentPoints.length < 1) return;
        
        this.annotationTool.ctx.save();
        
        // 只在相邻点之间绘制线条，不绘制临时点和虚线
        if (this.currentPoints.length >= 2) {
            this.annotationTool.ctx.strokeStyle = '#2196F3';
            this.annotationTool.ctx.lineWidth = 2;
            this.annotationTool.ctx.beginPath();
            this.annotationTool.ctx.moveTo(this.currentPoints[0].x, this.currentPoints[0].y);
            for (let i = 1; i < this.currentPoints.length; i++) {
                this.annotationTool.ctx.lineTo(this.currentPoints[i].x, this.currentPoints[i].y);
            }
            this.annotationTool.ctx.stroke();
            
            // 绘制点
            this.currentPoints.forEach(point => {
                this.annotationTool.ctx.fillStyle = '#2196F3';
                this.annotationTool.ctx.beginPath();
                this.annotationTool.ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
                this.annotationTool.ctx.fill();
            });
        } else if (this.currentPoints.length === 1) {
            // 当只有一个点时，只绘制这个点
            const point = this.currentPoints[0];
            this.annotationTool.ctx.fillStyle = '#2196F3';
            this.annotationTool.ctx.beginPath();
            this.annotationTool.ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
            this.annotationTool.ctx.fill();
        }
        
        this.annotationTool.ctx.restore();
    }

    // 删除分割标注
    removeSegment(index) {
        const segmentIndex = this.annotationTool.annotations.findIndex(ann => ann.points && index-- === 0);
        if (segmentIndex !== -1) {
            this.annotationTool.annotations.splice(segmentIndex, 1);
            this.annotationTool.updateAnnotationList();
            this.annotationTool.redraw();
            // 实时保存
            setTimeout(() => {
                this.annotationTool.saveAnnotation();
            }, 100);
        }
    }

    // 转换为YOLO格式
    toYoloFormat(segment) {
        if (!segment.points) return null;
        
        // 将点坐标归一化到0-1范围
        const normalizedPoints = segment.points.map(point => [
            point[0] / this.annotationTool.canvas.width,
            point[1] / this.annotationTool.canvas.height
        ]);
        
        // 展平点坐标数组
        const flatPoints = [];
        normalizedPoints.forEach(point => {
            flatPoints.push(point[0].toFixed(6), point[1].toFixed(6));
        });
        
        return `${segment.class_id} ${flatPoints.join(' ')}`;
    }
    
    // 新增：检查是否点击了标注点
    isPointClicked(segment, canvasX, canvasY) {
        const handleSize = 8;
        
        // 检查segment对象是否存在以及points数组是否存在
        if (!segment || !segment.points || !Array.isArray(segment.points)) {
            return -1; // 没有点击任何点
        }
        
        for (let i = 0; i < segment.points.length; i++) {
            const point = segment.points[i];
            // 检查point是否有效
            if (!point || point.length < 2) {
                continue; // 跳过无效的点
            }
            if (canvasX >= point[0] - handleSize && canvasX <= point[0] + handleSize &&
                canvasY >= point[1] - handleSize && canvasY <= point[1] + handleSize) {
                return i; // 返回被点击的点索引
            }
        }
        return -1; // 没有点击任何点
    }
    
    // 新增：开始拖拽点
    startDraggingPoint(pointIndex) {
        this.isDraggingPoint = true;
        this.draggedPointIndex = pointIndex;
    }
    
    // 新增：停止拖拽点
    stopDraggingPoint() {
        this.isDraggingPoint = false;
        this.draggedPointIndex = -1;
        
        // 保存标注
        setTimeout(() => {
            this.annotationTool.saveAnnotation();
        }, 100);
    }
    
    // 新增：开始整体拖动分割区域
    startDraggingSegment(startX, startY) {
        this.isDraggingSegment = true;
        this.segmentDragStartX = startX;
        this.segmentDragStartY = startY;
    }
    
    // 新增：停止整体拖动分割区域
    stopDraggingSegment() {
        this.isDraggingSegment = false;
        
        // 保存标注
        setTimeout(() => {
            this.annotationTool.saveAnnotation();
        }, 100);
    }
    
    // 检查指定位置是否有分割标注
    getSegmentAtPosition(x, y) {
        // 从后往前遍历，优先选中上层的标注
        for (let i = this.annotationTool.annotations.length - 1; i >= 0; i--) {
            const ann = this.annotationTool.annotations[i];
            
            // 检查是否为分割标注，以及points是否有效
            if (ann.points && Array.isArray(ann.points) && ann.points.length >= 3) {
                if (this.isPointInPolygon(ann.points, x, y)) {
                    return ann;
                }
            }
        }
        return null;
    }
    
    // 检查点是否在多边形内（使用射线法）
    isPointInPolygon(points, x, y) {
        // 检查points是否有效
        if (!points || !Array.isArray(points) || points.length < 3) {
            return false;
        }
        
        let inside = false;
        
        for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
            // 检查当前点和前一个点是否有效
            if (!points[i] || points[i].length < 2 || !points[j] || points[j].length < 2) {
                continue; // 跳过无效的点
            }
            
            const xi = points[i][0], yi = points[i][1];
            const xj = points[j][0], yj = points[j][1];
            
            // 避免除零错误
            if (yj === yi) {
                continue;
            }
            
            const intersect = ((yi > y) !== (yj > y)) &&
                (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
            
            if (intersect) inside = !inside;
        }
        
        return inside;
    }
}

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SegmentationTool;
}