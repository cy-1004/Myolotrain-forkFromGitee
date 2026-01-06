// 关键点标注工具类
class KeypointsTool {
    constructor(annotationTool) {
        this.annotationTool = annotationTool;
        this.isDrawing = false;
        this.currentKeypoints = [];
        this.selectedKeypoint = null;
        this.isDraggingKeypoint = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.keypointRadius = 5; // 关键点半径
        this.currentBox = null;
        this.isDrawingBox = false;
        this.tempBox = null; // 临时框用于绘制过程中的显示
        this.selectedBox = null;
        this.currentMode = 'box'; // 'keypoints' 或 'box'
        this.outsideAlertShown = false; // 用于避免重复提示
    }

    // 设置当前模式
    setMode(mode) {
        this.currentMode = mode;
        console.log('关键点工具模式已切换为:', mode);
    }
    
    // 设置关键点配置
    setClassKeypointsConfig(config) {
        this.classKeypointsConfig = config || [];
        console.log('关键点配置已设置:', this.classKeypointsConfig);
    }
    
    // 删除选中的关键点
    deleteSelectedKeypoint() {
        if (this.selectedKeypoint && this.annotationTool.selectedAnnotation && this.annotationTool.selectedAnnotation.keypoints) {
            const index = this.annotationTool.selectedAnnotation.keypoints.indexOf(this.selectedKeypoint);
            if (index !== -1) {
                this.annotationTool.selectedAnnotation.keypoints.splice(index, 1);
                
                // 在新逻辑中，即使没有关键点了，也保留矩形框
                // 不删除整个标注，只删除关键点
                
                // 更新标注列表
                this.annotationTool.updateAnnotationList();
                
                // 重新绘制
                this.annotationTool.redraw();
                
                // 保存标注
                setTimeout(() => {
                    this.annotationTool.saveAnnotation();
                }, 100);
            }
        }
    }
    
    // 拖拽关键点
    dragKeypoint(e) {
        if (!this.isDraggingKeypoint || !this.selectedKeypoint) return;
        
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);
        
        // 检查是否有选中的标注框
        if (this.annotationTool.selectedAnnotation && this.annotationTool.selectedAnnotation.keypoints) {
            const box = this.annotationTool.selectedAnnotation;
            
            // 检查关键点是否在矩形框边界外
            let isOutside = false;
            let finalX = canvasX;
            let finalY = canvasY;
            
            if (canvasX < box.x || canvasX > box.x + box.width || 
                canvasY < box.y || canvasY > box.y + box.height) {
                isOutside = true;
                // 如果在边界外，约束到边界内
                finalX = Math.max(box.x, Math.min(canvasX, box.x + box.width));
                finalY = Math.max(box.y, Math.min(canvasY, box.y + box.height));
                
                // 提示用户关键点已自动调整到边界内
                if (!this.outsideAlertShown) {  // 避免重复提示
                    this.outsideAlertShown = true;
                    setTimeout(() => {
                        this.outsideAlertShown = false;
                    }, 1000); // 1秒后重置标志
                    alert('关键点位置已自动调整到标注框内');
                }
            }
            
            // 更新关键点位置（使用画布坐标）
            this.selectedKeypoint.x = finalX;
            this.selectedKeypoint.y = finalY;
        } else {
            // 如果没有选中的标注框，仍然更新关键点位置
            // 直接使用画布坐标
            this.selectedKeypoint.x = canvasX;
            this.selectedKeypoint.y = canvasY;
        }
        
        // 重新绘制
        this.annotationTool.redraw();
    }
    
    // 完成关键点拖拽
    finishDragging() {
        if (this.isDraggingKeypoint) {
            this.isDraggingKeypoint = false;
            
            // 重新绘制以更新显示
            this.annotationTool.redraw();
            
            // 保存标注
            setTimeout(() => {
                this.annotationTool.saveAnnotation();
            }, 100);
        }
    }
    
    // 切换选中关键点的可见性
    toggleKeypointVisibility() {
        if (this.selectedKeypoint) {
            // 循环切换可见性：0(不存在) -> 1(可见) -> 2(遮挡) -> 0(不存在)
            if (this.selectedKeypoint.v === 0) {
                this.selectedKeypoint.v = 1; // 可见
            } else if (this.selectedKeypoint.v === 1) {
                this.selectedKeypoint.v = 2; // 遮挡
            } else {
                this.selectedKeypoint.v = 0; // 不存在
            }
            
            // 重新绘制
            this.annotationTool.redraw();
            
            // 保存标注
            this.annotationTool.saveAnnotation();
        }
    }
    
    // 鼠标移动
    onMouseMove(e) {
        if (this.isDraggingKeypoint && this.selectedKeypoint) {
            // 拖拽关键点
            this.dragKeypoint(e);
        } else if (this.currentMode === 'box' && this.isDrawingBox) {
            const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);
            this.tempBox = {
                x: Math.min(this.startX, canvasX),
                y: Math.min(this.startY, canvasY),
                width: Math.abs(canvasX - this.startX),
                height: Math.abs(canvasY - this.startY)
            };
            this.annotationTool.redraw();
        }
    }
    
    // 鼠标释放
    onMouseUp(e) {
        if (this.isDraggingKeypoint) {
            // 完成关键点拖拽
            this.finishDragging();
        } else if (this.currentMode === 'box' && this.tempBox && this.tempBox.width > 5 && this.tempBox.height > 5) {
            // 创建一个边界框标注，用于后续添加关键点
            // 保存为画布坐标，在保存时再转换为归一化坐标
            const boxAnnotation = {
                class_id: this.annotationTool.selectedClass,
                x: this.tempBox.x, // 保存为画布坐标
                y: this.tempBox.y, // 保存为画布坐标
                width: this.tempBox.width, // 保存为画布坐标
                height: this.tempBox.height, // 保存为画布坐标
                keypoints: [] // 初始化关键点数组
            };
            
            // 添加到标注数组
            this.annotationTool.annotations.push(boxAnnotation);
            
            // 选中这个新的标注
            this.annotationTool.selectedAnnotation = boxAnnotation;
            
            // 清除临时框
            this.tempBox = null;
            this.isDrawingBox = false;
            
            // 更新标注列表
            this.annotationTool.updateAnnotationList();
            
            // 重新绘制
            this.annotationTool.redraw();
            
            // 保存标注
            setTimeout(() => {
                this.annotationTool.saveAnnotation();
            }, 100);
        } else {
            // 取消绘制
            this.tempBox = null;
            this.isDrawingBox = false;
            this.annotationTool.redraw();
        }
    }

    // 开始关键点标注
    startAnnotation(e) {
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);
        
        // 检查是否按下了Ctrl键，如果是，则只选中而不添加新点
        if (e.ctrlKey) {
            if (this.currentMode === 'keypoints') {
                // 在关键点模式下，检查是否点击了现有的关键点
                const clickedKeypoint = this.getKeypointAtPosition(canvasX, canvasY);
                if (clickedKeypoint) {
                    // 删除选中的关键点
                    this.deleteSelectedKeypoint();
                    return;
                }
                
                // 如果在关键点模式下点击到框，不处理
                this.annotationTool.selectedAnnotation = null;
                this.selectedKeypoint = null; // 清除关键点选中状态
                this.annotationTool.updateAnnotationList();
                this.annotationTool.redraw();
                return;
            } else if (this.currentMode === 'box') {
                // 在矩形框模式下，检查是否点击了现有的矩形框
                const clickedBox = this.getBoxAtPosition(canvasX, canvasY);
                if (clickedBox) {
                    // 选中矩形框
                    this.annotationTool.selectedAnnotation = clickedBox;
                    this.annotationTool.updateAnnotationList();
                    this.annotationTool.redraw();
                    return;
                }
                
                // 如果在矩形框模式下点击到关键点，不处理
                this.annotationTool.selectedAnnotation = null;
                this.selectedKeypoint = null; // 清除关键点选中状态
                this.annotationTool.updateAnnotationList();
                this.annotationTool.redraw();
                return;
            }
        }
        
        // 根据当前模式处理点击事件
        if (this.currentMode === 'keypoints') {
            // 在关键点模式下，只处理关键点相关操作
            const clickedKeypoint = this.getKeypointAtPosition(canvasX, canvasY);
            if (clickedKeypoint) {
                // 开始拖拽关键点
                this.selectedKeypoint = clickedKeypoint;
                this.isDraggingKeypoint = true;
                this.dragStartX = canvasX;
                this.dragStartY = canvasY;
                
                // 重新绘制以更新显示
                this.annotationTool.redraw();
                return;
            }
            
            // 如果点击了关键点框内部，添加新关键点
            const clickedBoxOnly = this.getBoxOnlyAtPosition(canvasX, canvasY);
            if (clickedBoxOnly) {
                // 在该框内添加新关键点
                this.annotationTool.selectedAnnotation = clickedBoxOnly;
                this.addKeypoint(canvasX, canvasY);
                return;
            }
            
            // 如果没有点击到任何关键点或框内区域，清除选中状态
            this.annotationTool.selectedAnnotation = null;
            this.selectedKeypoint = null; // 清除关键点选中状态
            this.annotationTool.updateAnnotationList();
            this.annotationTool.redraw();
            return;
        } else if (this.currentMode === 'box') {
            // 在矩形框模式下，只处理矩形框相关操作
            const clickedBox = this.getBoxAtPosition(canvasX, canvasY);
            if (clickedBox) {
                // 选中矩形框
                this.annotationTool.selectedAnnotation = clickedBox;
                this.annotationTool.updateAnnotationList();
                this.annotationTool.redraw();
                return;
            }
            
            // 开始绘制矩形框
            this.isDrawingBox = true;
            this.startX = canvasX;
            this.startY = canvasY;
            return;
        }
    }
    
    



    // 更新包围框以包含所有关键点（保持矩形框大小不变，仅用于显示）
    updateBoundingBox(annotation) {
        // 在新的逻辑中，矩形框大小是固定的，不随关键点变化
        // 此方法保留用于兼容性，但不执行任何操作
        // 关键点必须在预定义的矩形框内
    }

    // 获取指定位置的关键点
    getKeypointAtPosition(x, y) {
        // 遍历所有标注
        for (let i = this.annotationTool.annotations.length - 1; i >= 0; i--) {
            const ann = this.annotationTool.annotations[i];
            
            // 检查是否有关键点
            if (ann.keypoints && Array.isArray(ann.keypoints)) {
                // 遍历关键点
                for (let j = 0; j < ann.keypoints.length; j++) {
                    const kp = ann.keypoints[j];
                    
                    // 不管关键点的可见性如何，都应该能够被选中
                    // v值: 0=不存在, 1=可见, 2=遮挡 - 这些只影响数据保存，不影响交互
                    
                    // 注意：kp.x, kp.y 已经是画布坐标（像素坐标），不需要转换
                    const kpX = kp.x;
                    const kpY = kp.y;
                    
                    // 计算距离
                    const distance = Math.sqrt(Math.pow(x - kpX, 2) + Math.pow(y - kpY, 2));
                    
                    // 如果在关键点半径内
                    if (distance <= this.keypointRadius * 2) {
                        // 设置当前选中的标注
                        this.annotationTool.selectedAnnotation = ann;
                        return kp;
                    }
                }
            }
        }
        
        return null;
    }
    
    // 获取指定位置的所有矩形框（仅矩形框，不包括关键点）
    getBoxesAtPosition(x, y) {
        const boxes = [];
        
        // 遍历所有标注，找到所有包含点击位置的矩形框
        for (let i = 0; i < this.annotationTool.annotations.length; i++) {
            const ann = this.annotationTool.annotations[i];
            
            // 检查是否为关键点标注（包含矩形框和关键点）
            if (ann.keypoints && ann.x !== undefined && ann.y !== undefined && 
                ann.width !== undefined && ann.height !== undefined) {
                
                // 所有标注现在都使用画布坐标，无需转换
                let boxX = ann.x;
                let boxY = ann.y;
                let boxWidth = ann.width;
                let boxHeight = ann.height;
                
                // 检查坐标是否在矩形框内
                if (x >= boxX && x <= boxX + boxWidth &&
                    y >= boxY && y <= boxY + boxHeight) {
                    boxes.push(ann);
                }
            }
        }
        
        return boxes;
    }
    
    // 获取指定位置的矩形框（仅矩形框，不包括关键点）
    getBoxOnlyAtPosition(x, y) {
        // 获取所有重叠的框
        const boxes = this.getBoxesAtPosition(x, y);
        
        // 如果有多个框重叠，提示用户选择
        if (boxes.length > 1) {
            // 简单实现：返回第一个框，实际应用中可以显示选择界面
            return this.promptUserForBoxSelection(boxes);
        }
        
        // 如果只有一个框，直接返回
        return boxes.length > 0 ? boxes[0] : null;
    }
    
    // 提示用户选择矩形框
    promptUserForBoxSelection(boxes) {
        if (boxes.length === 0) return null;
        
        // 如果只有一个框，直接返回
        if (boxes.length === 1) {
            return boxes[0];
        }
        
        // 显示选择界面
        const boxInfo = boxes.map((box, index) => {
            const className = this.annotationTool.projectData.classes[box.class_id] || '未知';
            return `${index + 1}. ${className} (关键点: ${box.keypoints ? box.keypoints.length : 0}个)`;
        }).join('\n');
        
        const choice = prompt(`发现多个重叠的标注框:\n${boxInfo}\n\n请输入选择的框编号 (1-${boxes.length})，或点击取消选择最近的框:`);
        
        if (choice === null || choice === '') {
            // 如果用户取消或输入为空，返回最近的框（最后一个）
            return boxes[boxes.length - 1];
        }
        
        const index = parseInt(choice) - 1;
        if (index >= 0 && index < boxes.length) {
            return boxes[index];
        } else {
            // 如果输入无效，返回最近的框
            return boxes[boxes.length - 1];
        }
    }
    
    // 添加关键点
    addKeypoint(canvasX, canvasY) {
        // 首先检查是否有选中的标注
        if (!this.annotationTool.selectedAnnotation) {
            // 如果没有选中的标注，获取所有重叠的框并提示用户选择
            const boxes = this.getBoxesAtPosition(canvasX, canvasY);
                
            if (boxes.length === 0) {
                // 没有找到任何框，提示用户先创建框
                alert('请先创建一个矩形框标注，然后在该框内添加关键点');
                return;
            } else if (boxes.length === 1) {
                // 只有一个框，直接选中
                this.annotationTool.selectedAnnotation = boxes[0];
            } else {
                // 多个框重叠，提示用户选择
                this.annotationTool.selectedAnnotation = this.promptUserForBoxSelection(boxes);
            }
        }
            
        // 检查选中的标注是否已经有关键点数组
        if (!this.annotationTool.selectedAnnotation.keypoints) {
            this.annotationTool.selectedAnnotation.keypoints = [];
        }
            
        // 获取当前框的类别名称
        const selectedAnn = this.annotationTool.selectedAnnotation;
        const className = this.annotationTool.projectData.classes[selectedAnn.class_id];
            
        // 检查该类别是否有关联的关键点配置
        const classKeypointConfig = this.classKeypointsConfig.find(config => config.class_name === className);
            
        // 检查关键点是否在矩形框边界外
        let isOutside = false;
        let finalX = canvasX;
        let finalY = canvasY;
        
        if (canvasX < selectedAnn.x || canvasX > selectedAnn.x + selectedAnn.width || 
            canvasY < selectedAnn.y || canvasY > selectedAnn.y + selectedAnn.height) {
            isOutside = true;
            // 如果在边界外，约束到边界内
            finalX = Math.max(selectedAnn.x, Math.min(canvasX, selectedAnn.x + selectedAnn.width));
            finalY = Math.max(selectedAnn.y, Math.min(canvasY, selectedAnn.y + selectedAnn.height));
            
            // 提示用户关键点已自动调整到边界内
            alert('关键点位置已自动调整到标注框内');
        }
        
        const boundedX = finalX;
        const boundedY = finalY;
            
        let newKeypoint;
        if (!classKeypointConfig || !classKeypointConfig.keypoints || classKeypointConfig.keypoints.length === 0) {
            // 如果没有配置关键点，直接添加关键点
            newKeypoint = {
                x: boundedX, // boundedX是画布坐标
                y: boundedY, // boundedY是画布坐标
                v: 1 // 默认设置为可见
            };
                
            selectedAnn.keypoints.push(newKeypoint);
                
            // 选中新添加的关键点以支持立即拖拽
            this.selectedKeypoint = newKeypoint;
                
            // 更新标注列表
            this.annotationTool.updateAnnotationList();
                
            // 重新绘制
            this.annotationTool.redraw();
                
            // 保存标注
            setTimeout(() => {
                this.annotationTool.saveAnnotation();
            }, 100);
        } else {
            // 检查该框的关键点数量是否已达到配置的最大数量
            if (selectedAnn.keypoints.length >= classKeypointConfig.keypoints_count) {
                alert(`类别 "${className}" 的关键点数量已达上限（${classKeypointConfig.keypoints_count}个）！`);
                return;
            }
                
            // 添加新的关键点
            newKeypoint = {
                x: boundedX, // boundedX是画布坐标
                y: boundedY, // boundedY是画布坐标
                v: 1 // 默认设置为可见
            };
                
            selectedAnn.keypoints.push(newKeypoint);
                
            // 选中新添加的关键点以支持立即拖拽
            this.selectedKeypoint = newKeypoint;
                
            // 更新标注列表
            this.annotationTool.updateAnnotationList();
                
            // 重新绘制
            this.annotationTool.redraw();
                
            // 保存标注
            setTimeout(() => {
                this.annotationTool.saveAnnotation();
            }, 100);
        }
    }
    




    // 绘制过程中的矩形框
    drawTempBox() {
        if (this.tempBox) {
            this.annotationTool.ctx.save();
            this.annotationTool.ctx.strokeStyle = '#2196F3';
            this.annotationTool.ctx.lineWidth = 2;
            this.annotationTool.ctx.setLineDash([5, 5]);
            
            // 确保临时框坐标和尺寸是有效的数字
            const x = parseFloat(this.tempBox.x);
            const y = parseFloat(this.tempBox.y);
            const width = parseFloat(this.tempBox.width);
            const height = parseFloat(this.tempBox.height);
            
            if (!isNaN(x) && !isNaN(y) && !isNaN(width) && !isNaN(height) && 
                width > 0 && height > 0) {
                this.annotationTool.ctx.strokeRect(x, y, width, height);
            }
            
            this.annotationTool.ctx.restore();
        }
    }

    // 重新绘制关键点和矩形框
    redraw() {
        if (!this.annotationTool.currentImage) return;
        
        // 绘制已完成的关键点标注（包括矩形框）
        this.annotationTool.annotations.forEach((ann, index) => {
            if (ann.keypoints) {
                const isSelected = this.annotationTool.selectedAnnotation === ann;
                this.drawKeypoints(ann, this.annotationTool.getClassColor(ann.class_id), false, index + 1, isSelected);
            }
        });
        
        // 绘制普通矩形框标注（非关键点标注的矩形框）
        this.annotationTool.annotations.forEach((ann, index) => {
            if (ann.x && ann.y && ann.width && ann.height && !ann.keypoints) {
                const isSelected = this.annotationTool.selectedAnnotation === ann;
                this.annotationTool.drawBox(ann, this.annotationTool.getClassColor(ann.class_id), false, index + 1, isSelected);
            }
        });
        
        // 绘制临时框（如果正在绘制）
        if (this.currentMode === 'box' && this.tempBox) {
            this.drawTempBox();
        }
    }

    // 绘制关键点和矩形框
    drawKeypoints(annotation, color, isDrawing = false, index = null, isSelected = false) {
        if (!annotation.keypoints) return;
        
        this.annotationTool.ctx.save();
        
        // 设置颜色
        let keypointColor;
        if (isSelected) {
            keypointColor = '#44FF44'; // 选中时使用绿色
        } else {
            // 将十六进制颜色转换为 RGBA 格式
            if (color.startsWith('#')) {
                const r = parseInt(color.substr(1, 2), 16);
                const g = parseInt(color.substr(3, 2), 16);
                const b = parseInt(color.substr(5, 2), 16);
                keypointColor = `rgba(${r}, ${g}, ${b}, 0.8)`;
            } else {
                keypointColor = color;
            }
        }
        
        // 绘制包围框
        if (annotation.x !== undefined && annotation.y !== undefined && 
            annotation.width !== undefined && annotation.height !== undefined) {
            // 确保矩形框坐标和尺寸是有效的数字
            let x = parseFloat(annotation.x);
            let y = parseFloat(annotation.y);
            let width = parseFloat(annotation.width);
            let height = parseFloat(annotation.height);
            
            // 检查坐标和尺寸是否有效
            if (!isNaN(x) && !isNaN(y) && !isNaN(width) && !isNaN(height) && 
                width > 0 && height > 0) {
                // 所有标注现在都使用画布坐标，无需转换
                this.annotationTool.ctx.strokeStyle = keypointColor;
                this.annotationTool.ctx.lineWidth = isSelected ? 3 : 2;
                this.annotationTool.ctx.setLineDash([]);
                this.annotationTool.ctx.strokeRect(x, y, width, height);
            }
        }
        
        // 绘制关键点（在框的上方）
        annotation.keypoints.forEach((kp, i) => {
            // 不管关键点的可见性如何，都应该在画布上显示
            // v值: 0=不存在, 1=可见, 2=遮挡 - 这些只影响数据保存，不影响显示
            const visibility = kp.v !== undefined ? kp.v : 2; // 默认为遮挡状态
            
            // 注意：kp.x, kp.y 已经是画布坐标（像素坐标），不需要转换
            const canvasX = kp.x;
            const canvasY = kp.y;
            
            // 设置关键点颜色（根据可见性）
            let pointColor = keypointColor;
            if (visibility === 0) { // 不存在
                // 使用灰色表示不存在的关键点
                pointColor = 'rgba(128, 128, 128, 0.7)'; // 灰色
            } else if (visibility === 2) { // 被遮挡
                // 使用半透明红色表示被遮挡的关键点
                pointColor = 'rgba(255, 0, 0, 0.5)'; // 半透明红色
            }
            // visibility === 1 时使用默认颜色（pointColor）
            
            // 绘制关键点
            this.annotationTool.ctx.fillStyle = pointColor;
            this.annotationTool.ctx.beginPath();
            this.annotationTool.ctx.arc(canvasX, canvasY, this.keypointRadius, 0, Math.PI * 2);
            this.annotationTool.ctx.fill();
            
            // 获取当前框的类别名称
            const className = this.annotationTool.projectData.classes[annotation.class_id];
            
            // 检查该类别是否有关联的关键点配置
            const classKeypointConfig = this.classKeypointsConfig.find(config => config.class_name === className);
            
            // 绘制关键点标签
            this.annotationTool.ctx.fillStyle = '#FFFFFF';
            this.annotationTool.ctx.font = '10px Arial';
            this.annotationTool.ctx.textAlign = 'center';
            this.annotationTool.ctx.textBaseline = 'middle';
            
            if (classKeypointConfig && classKeypointConfig.keypoints && i < classKeypointConfig.keypoints.length) {
                // 如果有配置的关键点标签，使用配置的标签
                const keypointLabel = classKeypointConfig.keypoints[i];
                this.annotationTool.ctx.fillText(keypointLabel || (i + 1).toString(), canvasX, canvasY);
            } else {
                // 如果没有配置标签，使用数字序号
                this.annotationTool.ctx.fillText(i + 1, canvasX, canvasY);
            }
        });
        
        // 绘制序号和类别标签
        if (!isDrawing && annotation.x !== undefined && annotation.y !== undefined) {
            const className = this.annotationTool.projectData.classes[annotation.class_id] || '未知';
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
            
            // 确保标签坐标是有效的数字
            let x = parseFloat(annotation.x);
            let y = parseFloat(annotation.y);
            
            if (!isNaN(x) && !isNaN(y)) {
                // 所有标注现在都使用画布坐标，无需转换
                this.annotationTool.ctx.fillRect(x, y - 20, this.annotationTool.ctx.measureText(label).width + 10, 20);
                this.annotationTool.ctx.fillStyle = 'white';
                this.annotationTool.ctx.font = '12px Arial';
                this.annotationTool.ctx.fillText(label, x + 5, y - 5);
            }
        }
        
        this.annotationTool.ctx.restore();
    }

    // 删除关键点标注
    removeKeypoints(index) {
        // 先统计关键点标注的数量
        let keypointsCount = 0;
        for (let i = 0; i < this.annotationTool.annotations.length; i++) {
            if (this.annotationTool.annotations[i].keypoints) {
                keypointsCount++;
            }
        }
        
        // 查找第index个关键点标注
        let currentKeypointsIndex = 0;
        for (let i = 0; i < this.annotationTool.annotations.length; i++) {
            if (this.annotationTool.annotations[i].keypoints) {
                if (currentKeypointsIndex === index) {
                    this.annotationTool.annotations.splice(i, 1);
                    this.annotationTool.updateAnnotationList();
                    this.annotationTool.redraw();
                    // 实时保存
                    setTimeout(() => {
                        this.annotationTool.saveAnnotation();
                    }, 100);
                    return;
                }
                currentKeypointsIndex++;
            }
        }
        
        // 如果没有找到关键点标注，尝试删除普通矩形框标注
        if (keypointsCount === 0) {
            let boxCount = 0;
            for (let i = 0; i < this.annotationTool.annotations.length; i++) {
                if (this.annotationTool.annotations[i].x !== undefined && 
                    this.annotationTool.annotations[i].y !== undefined && 
                    this.annotationTool.annotations[i].width !== undefined && 
                    this.annotationTool.annotations[i].height !== undefined && 
                    !this.annotationTool.annotations[i].keypoints) {
                    if (boxCount === index) {
                        this.annotationTool.annotations.splice(i, 1);
                        this.annotationTool.updateAnnotationList();
                        this.annotationTool.redraw();
                        // 实时保存
                        setTimeout(() => {
                            this.annotationTool.saveAnnotation();
                        }, 100);
                        return;
                    }
                    boxCount++;
                }
            }
        }
    }

    // 转换为YOLO格式
    toYoloFormat(annotation) {
        if (!annotation.keypoints) return null;
        
        // 检查坐标是否为归一化坐标，如果是则直接使用，否则转换为归一化坐标
        let boxX = annotation.x;
        let boxY = annotation.y;
        let boxWidth = annotation.width;
        let boxHeight = annotation.height;
        
        // 如果坐标在0-1范围内，说明已经是归一化坐标
        if (boxX > 1 || boxY > 1 || boxWidth > 1 || boxHeight > 1) {
            // 这是画布坐标，需要转换为归一化坐标
            boxX = annotation.x / this.annotationTool.canvas.width;
            boxY = annotation.y / this.annotationTool.canvas.height;
            boxWidth = annotation.width / this.annotationTool.canvas.width;
            boxHeight = annotation.height / this.annotationTool.canvas.height;
        }
        
        // 计算中心点坐标（归一化）
        const x_center = boxX + boxWidth / 2;
        const y_center = boxY + boxHeight / 2;
        
        // 使用归一化后的宽高
        const width = boxWidth;
        const height = boxHeight;
        
        // 处理关键点数据
        const keypointsData = [];
        annotation.keypoints.forEach(kp => {
            // 注意：kp.x, kp.y 是画布坐标（像素坐标），需要转换为归一化坐标
            const normX = kp.x / this.annotationTool.canvas.width;
            const normY = kp.y / this.annotationTool.canvas.height;
            const visibility = kp.v || 2;
            
            keypointsData.push(normX.toFixed(6), normY.toFixed(6), visibility);
        });
        
        // 检查是否需要补0：根据关键点配置来确定每类应有多少个关键点
        if (this.classKeypointsConfig && annotation.class_id !== undefined) {
            // 获取当前标注类别的关键点配置
            const className = this.annotationTool.projectData.classes[annotation.class_id];
            const classKeypointConfig = this.classKeypointsConfig.find(config => config.class_name === className);
            
            if (classKeypointConfig && classKeypointConfig.keypoints_count > 0) {
                const expectedKeypoints = classKeypointConfig.keypoints_count;
                const expectedTotalValues = expectedKeypoints * 3; // 每个关键点3个值(x,y,v)
                const actualValues = keypointsData.length;
                
                // 如果关键点数量不足，补0
                if (actualValues < expectedTotalValues) {
                    const missingValues = expectedTotalValues - actualValues;
                    for (let i = 0; i < missingValues; i += 3) {
                        // 为每个缺失的关键点补充 x坐标, y坐标, 可见性
                        keypointsData.push('0.000000', '0.000000', '0');
                    }
                }
            }
        }
        
        return `${annotation.class_id} ${x_center.toFixed(6)} ${y_center.toFixed(6)} ${width.toFixed(6)} ${height.toFixed(6)} ${keypointsData.join(' ')}`;
    }
    
    // 获取指定位置的矩形框（非关键点标注的矩形框）
    getBoxAtPosition(x, y) {
        // 从后往前遍历，优先选中上层的标注
        for (let i = this.annotationTool.annotations.length - 1; i >= 0; i--) {
            const ann = this.annotationTool.annotations[i];
            
            // 检查是否为普通矩形框标注（没有关键点）
            if (ann.x !== undefined && ann.y !== undefined && 
                ann.width !== undefined && ann.height !== undefined && !ann.keypoints) {
                
                // 所有标注现在都使用画布坐标，无需转换
                let boxX = ann.x;
                let boxY = ann.y;
                let boxWidth = ann.width;
                let boxHeight = ann.height;
                
                if (x >= boxX && x <= boxX + boxWidth &&
                    y >= boxY && y <= boxY + boxHeight) {
                    return ann;
                }
            }
        }
        
        return null;
    }
    
    // 完成矩形框绘制 - 为了与annotation.js兼容
    finishBoxDrawing() {
        // 这个方法是为了与annotation.js中的stopDrawing方法兼容
        // 实际的绘制完成逻辑在onMouseUp中处理
        // 如果当前有临时框，模拟鼠标释放事件
        if (this.tempBox && this.currentMode === 'box' && this.tempBox.width > 5 && this.tempBox.height > 5) {
            // 创建一个边界框标注，用于后续添加关键点
            const boxAnnotation = {
                class_id: this.annotationTool.selectedClass,
                x: this.tempBox.x, // 保存为画布坐标
                y: this.tempBox.y, // 保存为画布坐标
                width: this.tempBox.width, // 保存为画布坐标
                height: this.tempBox.height, // 保存为画布坐标
                keypoints: [] // 初始化关键点数组
            };
            
            // 添加到标注数组
            this.annotationTool.annotations.push(boxAnnotation);
            
            // 选中这个新的标注
            this.annotationTool.selectedAnnotation = boxAnnotation;
            
            // 清除临时框
            this.tempBox = null;
            this.isDrawingBox = false;
            
            // 更新标注列表
            this.annotationTool.updateAnnotationList();
            
            // 重新绘制
            this.annotationTool.redraw();
            
            // 保存标注
            setTimeout(() => {
                this.annotationTool.saveAnnotation();
            }, 100);
        } else {
            // 取消绘制
            this.tempBox = null;
            this.isDrawingBox = false;
            this.annotationTool.redraw();
        }
    }
    
}

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = KeypointsTool;
}