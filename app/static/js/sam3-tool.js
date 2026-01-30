// SAM3工具类
class SAM3Tool {
    constructor(annotationTool) {
        this.annotationTool = annotationTool;
        this.isActive = false; // SAM3功能是否激活
        this.mode = 'point'; // 当前模式: point, box, text
        this.tempPoints = []; // 临时点集合（用于点提示）
        this.tempBox = null; // 临时框（用于框提示）
        this.isDrawingBox = false; // 是否正在绘制框
        this.boxStartX = 0;
        this.boxStartY = 0;
        this.selectedModel = null; // 选中的SAM3模型
        this.promptHistory = []; // 提示历史记录
        this.isProcessing = false; // 是否正在处理
        
        // 初始化时加载已保存的配置
        this.loadSavedConfig();
    }
    
    // 加载已保存的配置
    async loadSavedConfig() {
        try {
            const response = await fetch('/api/sam3/check_config');
            const data = await response.json();
            
            if (data.configured && data.config) {
                // 从保存的配置中加载参数
                this.imgsz = data.config.imgsz || 1024;
                this.halfPrecision = data.config.half_precision || true;
            } else {
                // 使用默认值
                this.imgsz = 1024;
                this.halfPrecision = true;
            }
        } catch (error) {
            console.error('加载SAM3配置失败:', error);
            // 使用默认值
            this.imgsz = 1024;
            this.halfPrecision = true;
        }
    }

    // 激活SAM3工具
    activate() {
        this.isActive = true;
        
        // 显示SAM3操作工具栏
        const sam3Toolbar = document.getElementById('sam3-operation-toolbar');
        if (sam3Toolbar) {
            sam3Toolbar.style.display = 'block';
        }
        
        // 切换到SAM3工具
        this.annotationTool.currentTool = 'sam3';
        
        // 更新工具按钮状态
        const toolButtons = document.querySelectorAll('#tool-selector .btn');
        toolButtons.forEach(btn => {
            btn.classList.remove('active');
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline-primary');
        });
        
        // 更新全新SAM3控制容器状态
        // 使用setTimeout确保在其他UI更新完成后执行
        setTimeout(() => {
            const sam3Switch = document.getElementById('sam3-toggle-switch');
            const statusLabel = document.getElementById('sam3-status-label');
            if (sam3Switch) {
                sam3Switch.checked = true;  // 开启滑块
                sam3Switch.title = '关闭SAM3分割工具';
            }
            if (statusLabel) {
                statusLabel.textContent = '开启';
                statusLabel.style.color = '#28a745';
            }
        }, 0);
        
        this.annotationTool.redraw();
        this.annotationTool.showMessage('SAM3分割已激活', 'info');
    }

    // 停用SAM3工具
    deactivate() {
        this.isActive = false;
        this.cleanup();
        
        // 隐藏SAM3操作工具栏
        const sam3Toolbar = document.getElementById('sam3-operation-toolbar');
        if (sam3Toolbar) {
            sam3Toolbar.style.display = 'none';
        }
        
        this.annotationTool.showMessage('SAM3分割已停用', 'info');
        
        // 切换回默认工具（segment）
        if (this.annotationTool.projectData && this.annotationTool.projectData.project_type === 'segmentation') {
            // 对于实例分割项目，确保切换回segment工具
            this.annotationTool.currentTool = 'segment';
            
            // 更新工具按钮状态
            const toolButtons = document.querySelectorAll('#tool-selector .btn');
            toolButtons.forEach(btn => {
                btn.classList.remove('active');
                btn.classList.remove('btn-primary');
                btn.classList.add('btn-outline-primary');
            });
            
            const activeButton = document.getElementById('tool-segment');
            if (activeButton) {
                activeButton.classList.remove('btn-outline-primary');
                activeButton.classList.add('btn-primary');
                activeButton.classList.add('active');
            }
            
            this.annotationTool.redraw();
        }
        
        // 更新全新SAM3控制容器状态（无论项目类型）
        // 使用setTimeout确保在其他UI更新完成后执行
        setTimeout(() => {
            const sam3Switch = document.getElementById('sam3-toggle-switch');
            const statusLabel = document.getElementById('sam3-status-label');
            if (sam3Switch) {
                sam3Switch.checked = false;  // 关闭滑块
                sam3Switch.title = '启用SAM3分割工具';
            }
            if (statusLabel) {
                statusLabel.textContent = '关闭';
                statusLabel.style.color = '#6c757d';
            }
        }, 0);
    }

    // 清理临时状态
    cleanup() {
        this.tempPoints = [];
        this.tempBox = null;
        this.isDrawingBox = false;
        this.mode = 'point';
        this.annotationTool.redraw();
    }


    
    
    // 设置当前模式
    setMode(mode) {
        this.mode = mode;
        
        // 更新按钮状态
        const modes = ['point', 'box', 'text'];
        modes.forEach(m => {
            const btn = document.getElementById(`sam3-${m}-mode`);
            if (btn) {
                if (m === mode) {
                    btn.classList.add('btn-primary');
                    btn.classList.remove('btn-outline-primary');
                } else {
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline-primary');
                }
            }
        });

        this.annotationTool.showMessage(`已切换到${this.getModeName(mode)}模式`, 'info');
        this.cleanupTempState();
    }

    // 获取模式名称
    getModeName(mode) {
        const names = {
            'point': '点提示',
            'box': '框提示',
            'text': '文本提示'
        };
        return names[mode] || mode;
    }
    
    // 设置提示类型（兼容annotation.js）
    setPromptType(type) {
        this.setMode(type);
    }

    // 清除提示
    clearPrompts() {
        this.tempPoints = [];
        this.tempBox = null;
        this.isDrawingBox = false;
        this.annotationTool.showMessage('已清除所有提示', 'info');
        this.annotationTool.redraw();
    }

    // 清理临时状态
    cleanupTempState() {
        this.tempPoints = [];
        this.tempBox = null;
        this.isDrawingBox = false;
    }

    // 处理鼠标按下事件
    onMouseDown(e) {
        if (!this.isActive) return;

        const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);

        if (this.mode === 'point') {
            // 添加点提示
            this.tempPoints.push({ x: canvasX, y: canvasY });
            this.annotationTool.showMessage(`已添加点提示 (${this.tempPoints.length}个)`, 'info');
            this.annotationTool.redraw();
        } else if (this.mode === 'box') {
            // 开始绘制框
            this.isDrawingBox = true;
            this.boxStartX = canvasX;
            this.boxStartY = canvasY;
            this.tempBox = {
                x: canvasX,
                y: canvasY,
                width: 0,
                height: 0
            };
        }
        // 文本模式不需要鼠标事件
        
        e.stopPropagation(); // 阻止事件冒泡
    }

    // 处理鼠标移动事件
    onMouseMove(e) {
        if (!this.isActive) return;

        const { x: canvasX, y: canvasY } = this.annotationTool.getCanvasCoordinates(e);

        if (this.mode === 'box' && this.isDrawingBox) {
            // 更新临时框
            this.tempBox = {
                x: Math.min(this.boxStartX, canvasX),
                y: Math.min(this.boxStartY, canvasY),
                width: Math.abs(canvasX - this.boxStartX),
                height: Math.abs(canvasY - this.boxStartY)
            };
            this.annotationTool.redraw();
        }

        e.stopPropagation(); // 阻止事件冒泡
    }

    // 处理鼠标抬起事件
    onMouseUp(e) {
        if (!this.isActive) return;

        if (this.mode === 'box' && this.isDrawingBox) {
            this.isDrawingBox = false;
            this.annotationTool.showMessage('已添加框提示', 'info');
        }

        e.stopPropagation(); // 阻止事件冒泡
    }

    // 显示文本提示对话框
    showTextPromptDialog() {
        // 创建模态框
        const modal = document.createElement('div');
        modal.className = 'modal fade show';
        modal.style.cssText = 'display: block; background-color: rgba(0,0,0,0.5); position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 1050;';
        modal.innerHTML = `
            <div class="modal-dialog" style="max-width: 500px; margin: 2rem auto;">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">文本提示</h5>
                        <button type="button" class="btn-close" id="sam3-text-modal-close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label for="sam3-text-input" class="form-label">请输入描述性文本（用逗号分隔多个概念）</label>
                            <textarea class="form-control" id="sam3-text-input" rows="3" placeholder="例如：person, car, dog 或 红色汽车, 黄色公交车"></textarea>
                            <div class="form-text">支持多种概念，用逗号分隔</div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" id="sam3-text-cancel">取消</button>
                        <button type="button" class="btn btn-primary" id="sam3-text-confirm">确定</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // 绑定事件
        document.getElementById('sam3-text-modal-close')?.addEventListener('click', () => {
            document.body.removeChild(modal);
        });

        document.getElementById('sam3-text-cancel')?.addEventListener('click', () => {
            document.body.removeChild(modal);
        });

        document.getElementById('sam3-text-confirm')?.addEventListener('click', () => {
            const textInput = document.getElementById('sam3-text-input').value.trim();
            if (textInput) {
                this.processTextPrompt(textInput);
                document.body.removeChild(modal);
            } else {
                alert('请输入文本提示');
            }
        });

        // 聚焦到输入框
        document.getElementById('sam3-text-input')?.focus();
    }

    // 处理文本提示
    processTextPrompt(text) {
        this.textPrompt = text;
        this.annotationTool.showMessage(`已设置文本提示: ${text}`, 'info');
    }

    // 执行SAM3分割
    async executeSegmentation() {
        if (this.isProcessing) {
            this.annotationTool.showMessage('正在处理中，请稍候...', 'warning');
            return;
        }

        // 检查是否已配置模型
        if (!this.selectedModel) {
            // 尝试从配置中获取模型路径
            try {
                const configResponse = await fetch('/api/sam3/check_config');
                const configData = await configResponse.json();
                
                if (configData.configured && configData.config && configData.config.model_path) {
                    // 使用配置的模型
                    this.selectedModel = {
                        name: configData.config.model_path.split(/[\/]/).pop(),
                        path: configData.config.model_path,
                        type: 'SAM3',
                        task: 'segmentation'
                    };
                    
                    // 使用配置的参数
                    this.imgsz = configData.config.imgsz || 1024;
                    this.halfPrecision = configData.config.half_precision || true;
                } else {
                    // 如果没有配置，显示错误消息
                    this.annotationTool.showMessage('SAM3未配置，请先在在线标注列表页配置SAM3', 'error');
                    this.deactivate();
                    return;
                }
            } catch (error) {
                console.error('检查SAM3配置失败:', error);
                this.annotationTool.showMessage('检查SAM3配置失败，请先在在线标注列表页配置SAM3', 'error');
                this.deactivate();
                return;
            }
        }

        this.isProcessing = true;
        const executeBtn = document.getElementById('sam3-execute');
        if (executeBtn) {
            executeBtn.disabled = true;
            executeBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 处理中...';
        }

        try {
            // 准备参数
            // 如果有经过验证的运行时路径，使用它，否则使用原始路径
            const modelPath = this.lastValidatedModelPath || this.selectedModel.path;
            
            // 使用配置的参数
            const imgsz = this.imgsz !== undefined ? this.imgsz : 1024;
            const halfPrecision = this.halfPrecision !== undefined ? this.halfPrecision : true;
            
            // 获取当前图像ID，确保有值再发送
            console.log('检查annotationTool对象:', this.annotationTool);
            console.log('检查currentImageData:', this.annotationTool.currentImageData);
            
            if (!this.annotationTool || !this.annotationTool.currentImageData) {
                throw new Error('annotationTool或currentImageData未初始化');
            }
            
            const currentImageId = this.annotationTool.currentImageData.id;
            console.log('当前图像ID:', currentImageId);
            
            if (!currentImageId) {
                throw new Error('无法获取当前图像ID，请确保已加载图像');
            }
            
            const params = {
                image_id: currentImageId,  // 使用当前图像ID
                model_path: modelPath,
                prompt_type: this.mode,
                imgsz: imgsz,  // 添加图像大小参数
                half_precision: halfPrecision  // 添加半精度参数
            };
            
            // 根据模式准备不同的提示数据
            if (this.mode === 'point' && this.tempPoints.length > 0) {
                // 将点坐标转换为字符串格式 "x1,y1,x2,y2,..."
                const pointCoords = this.tempPoints.flatMap(p => [p.x, p.y]).join(',');
                params.points = pointCoords;
            } else if (this.mode === 'box' && this.tempBox) {
                // 将框坐标转换为字符串格式 "x1,y1,x2,y2"
                const boxCoords = [
                    this.tempBox.x,
                    this.tempBox.y,
                    this.tempBox.x + this.tempBox.width,
                    this.tempBox.y + this.tempBox.height
                ].join(',');
                params.bboxes = boxCoords;
            } else if (this.mode === 'text' && this.textPrompt) {
                params.text_prompt = this.textPrompt;
            }

            // 额外验证params对象
            console.log('发送的参数:', params);
            
            // 确保FormData正确添加所有参数
            const formData = new FormData();
            Object.keys(params).forEach(key => {
                console.log(`添加参数: ${key} = ${params[key]}`);
                formData.append(key, params[key]);
            });

            // 发送请求到SAM3 API
            const response = await fetch('/api/sam3/segment', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();

            if (result.success) {
                // 处理分割结果
                this.processSegmentationResults(result);
                this.annotationTool.showMessage('SAM3分割完成', 'success');
                
                // 添加到提示历史
                this.addToPromptHistory({
                    mode: this.mode,
                    params: params,
                    timestamp: new Date().toISOString()
                });
            } else {
                throw new Error('SAM3分割未成功返回结果');
            }

        } catch (error) {
            console.error('SAM3分割错误:', error);
            this.annotationTool.showMessage(`SAM3分割失败: ${error.message}`, 'error');
        } finally {
            this.isProcessing = false;
            if (executeBtn) {
                executeBtn.disabled = false;
                executeBtn.innerHTML = '<i class="bi bi-play-circle"></i> 执行分割';
            }
        }
    }

    // 处理分割结果
    processSegmentationResults(result) {
        if (!result.masks || result.masks.length === 0) {
            this.annotationTool.showMessage('SAM3未提取到有效目标', 'warning');
            return;
        }

        const canvasW = this.annotationTool.canvas.width;
        const canvasH = this.annotationTool.canvas.height;

        // 遍历所有返回的多边形
        result.masks.forEach(polyFlat => {
            // polyFlat 是归一化的 [x1, y1, x2, y2, ...]
            
            // 转换为 annotation.js 需要的 [[x,y], [x,y]] 格式，且是画布绝对坐标
            const points = [];
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

            for (let i = 0; i < polyFlat.length; i += 2) {
                const x = polyFlat[i] * canvasW;
                const y = polyFlat[i+1] * canvasH;
                points.push([x, y]);

                // 计算包围盒
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
            }

            // 创建标注对象
            const newAnnotation = {
                class_id: this.annotationTool.selectedClass,
                points: points, // 分割点集
                x: minX,
                y: minY,
                width: maxX - minX,
                height: maxY - minY
            };

            this.annotationTool.annotations.push(newAnnotation);
        });

        this.annotationTool.showMessage(`SAM3 已生成 ${result.masks.length} 个实例`, 'success');
        this.annotationTool.updateAnnotationList();
        this.annotationTool.redraw();
        
        // 自动保存
        this.annotationTool.saveAnnotation();
        
        // 清除当前的提示点/框，准备下一次操作
        this.clearPrompts();
    }

    // 将mask转换为点坐标（简化实现）
    convertMaskToPoints(mask) {
        // 这是一个简化的实现
        // 实际应用中需要使用图像处理算法从mask中提取轮廓点
        // 这里返回一个简单的矩形轮廓作为示例
        if (mask && mask.length > 0) {
            // 假设mask包含一些坐标信息，提取边界点
            // 简化：返回一个矩形的四个顶点
            return [
                [100, 100],
                [200, 100],
                [200, 200],
                [100, 200]
            ];
        }
        return [];
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

    // 添加到提示历史
    addToPromptHistory(promptData) {
        this.promptHistory.unshift(promptData);
        // 限制历史记录数量
        if (this.promptHistory.length > 10) {
            this.promptHistory = this.promptHistory.slice(0, 10);
        }
    }

    
    // 设置提示类型（兼容annotation.js中的调用）
    setPromptType(type) {
        this.setMode(type);
    }
    
    // 验证模型
    async validateModel(modelPath) {
        try {
            const formData = new FormData();
            formData.append('model_path', modelPath);
            
            const response = await fetch('/api/sam3/validate', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            
            // 如果验证成功，使用返回的runtime_path
            if (data.valid === true && data.runtime_path) {
                // 更新模型路径为运行时路径
                this.lastValidatedModelPath = data.runtime_path;
                return true;
            }
            
            return data.valid === true;
        } catch (error) {
            console.error('模型验证错误:', error);
            return false;
        }
    }

    // 绘制SAM3相关元素
    drawSAM3Elements() {
        if (!this.isActive) return;

        const ctx = this.annotationTool.ctx;

        // 绘制点提示
        if (this.tempPoints.length > 0) {
            this.tempPoints.forEach((point, index) => {
                ctx.fillStyle = '#FF6B6B'; // 红色表示点提示
                ctx.beginPath();
                ctx.arc(point.x, point.y, 6, 0, Math.PI * 2);
                ctx.fill();
                
                ctx.fillStyle = 'white';
                ctx.font = '12px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(index + 1, point.x, point.y);
            });
        }

        // 绘制框提示
        if (this.tempBox) {
            ctx.strokeStyle = '#4ECDC4'; // 青色表示框提示
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]); // 虚线
            ctx.strokeRect(this.tempBox.x, this.tempBox.y, this.tempBox.width, this.tempBox.height);
            ctx.setLineDash([]); // 重置线型
            
            // 绘制填充效果
            ctx.fillStyle = 'rgba(78, 205, 196, 0.2)';
            ctx.fillRect(this.tempBox.x, this.tempBox.y, this.tempBox.width, this.tempBox.height);
        }
    }

    // 检查快捷键
    handleKeyDown(event) {
        if (!this.isActive) return;
        
        const key = event.key.toLowerCase();
        
        // 处理导航和类别切换快捷键，不阻止这些键的默认行为
        const navigationKeys = ['a', 'd', 'arrowleft', 'arrowright', 'w', 's'];
        const classSelectionKeys = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];
        
        if (navigationKeys.includes(key) || classSelectionKeys.includes(event.key)) {
            // 不处理导航和类别切换快捷键，让主界面处理
            return;
        }
        
        // T键：文本提示模式
        if (key === 't' || key === 'f') {
            event.preventDefault();
            this.setMode('text');
            this.showTextPromptDialog();
        }
        // Esc键：取消当前操作或停用SAM3
        else if (event.key === 'Escape') {
            if (this.tempPoints.length > 0 || this.tempBox) {
                this.clearPrompts();
            } else {
                this.deactivate();
            }
        }
        // 其他SAM3特定快捷键
        else if (key === 'c') {
            // C键：清除提示
            event.preventDefault();
            this.clearPrompts();
        }
    }
}

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SAM3Tool;
}