class AnnotationTool {
    constructor() {
        this.canvas = document.getElementById('annotation-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.currentImage = null;
        this.currentImageData = null;
        this.annotations = [];
        this.isDrawing = false;
        this.isDragging = false;
        this.isResizing = false;
        this.isPanning = false;
        this.isPanReady = false;
        this.startX = 0;
        this.startY = 0;
        this.currentBox = null;
        this.selectedClass = 0;
        this.scale = 1;
        this.projectId = null;
        this.projectData = null;
        this.imageList = [];
        this.currentImageIndex = 0;
        this.isAutoAnnotating = false;
        this.autoAnnotateAbortController = null;
        this.availableModels = [];
        this.selectedModel = null;
        // 新增属性：辅助线开关
        this.showGuidelines = false;
        // 新增属性：辅助线颜色
        this.guidelineColor = 'rgba(255, 255, 255, 0.5)';
        // 新增属性：当前选中的标注框
        this.selectedAnnotation = null;
        // 新增属性：鼠标位置
        this.mouseX = 0;
        this.mouseY = 0;
        // 新增属性：拖拽起始位置
        this.dragStartX = 0;
        this.dragStartY = 0;
        // 新增属性：调整大小的控制点
        this.resizeHandle = null;
        // 新增属性：画布偏移量
        this.offsetX = 0;
        this.offsetY = 0;
        // 新增属性：拖动画布的起始位置
        this.panStartX = 0;
        this.panStartY = 0;
        // 新增属性：标记是否刚刚完成绘制（用于防止click事件重新选中）
        this.justFinishedDrawing = false;
        
        // 新增属性：标记是否通过点击选中
        this.selectedByClick = false;
        
        // 新增属性：标记是否刚刚完成拖拽或调整大小操作
        this.justFinishedDragging = false;
        this.justFinishedResizing = false;
        
        // 新增属性：实例分割工具
        this.segmentationTool = new SegmentationTool(this);
        // 新增属性：旋转框工具
        this.obbTool = new OBBTool(this);
        // 新增属性：关键点工具
        this.keypointsTool = new KeypointsTool(this);
        // 新增属性：SAM3工具
        this.sam3Tool = null; // 懒加载
        // 新增属性：当前工具类型
        this.currentTool = 'box'; // box, segment, obb, keypoints, sam3
        
        // 防抖相关变量
        this.debounceTimer = null;
        this.pendingSave = false;
        
        this.init();
        this.loadSAM3Tool(); // 初始化SAM3工具
    }
    
    init() {
        this.setupEventListeners();
        this.loadProject();
    }
    
    // 加载SAM3工具
    async loadSAM3Tool() {
        try {
            // 检查SAM3 API是否可用
            const response = await fetch('/api/sam3/available');
            const data = await response.json();
            
            // 即使SAM3不可用也创建按钮，只是功能受限
            const script = document.createElement('script');
            script.src = '/static/js/sam3-tool.js';
            document.head.appendChild(script);
            
            script.onload = () => {
                // 创建SAM3工具实例
                this.sam3Tool = new SAM3Tool(this);
                
                console.log('SAM3工具已加载');
                
                // 如果项目数据已经加载完成，且是实例分割项目，则添加SAM3按钮
                if (this.projectData && this.projectData.project_type === 'segmentation') {
                    this.addSAM3ToolButton();
                }
                // 否则，按钮将在loadProject完成时被添加
            };
            
            // 如果SAM3不可用，记录警告
            if (!data.available) {
                console.warn('SAM3不可用:', data.message);
            }
        } catch (error) {
            console.error('加载SAM3工具失败:', error);
        }
    }
    
    // 添加SAM3工具栏（全新实现）
    addSAM3ToolButton() {
        // 检查是否已存在SAM3容器
        if (document.getElementById('sam3-control-container')) {
            console.log('SAM3控制容器已存在，跳过创建');
            return;
        }
        
        console.log('开始创建SAM3控制容器');
        
        const toolSelector = document.getElementById('tool-selector');
        if (toolSelector) {
            // 创建一个全新的SAM3控制容器
            const containerDiv = document.createElement('div');
            containerDiv.id = 'sam3-control-container';
            containerDiv.className = 'd-flex align-items-center me-2';
            containerDiv.style.gap = '8px';
            containerDiv.style.border = '1px solid #dee2e6';
            containerDiv.style.borderRadius = '4px';
            containerDiv.style.padding = '4px 8px';
            containerDiv.style.backgroundColor = '#f8f9fa';
            
            // 创建SAM3标签
            const label = document.createElement('span');
            label.textContent = 'SAM3:';
            label.style.fontSize = '14px';
            label.style.fontWeight = 'bold';
            
            // 创建滑块开关
            const switchDiv = document.createElement('div');
            switchDiv.className = 'form-check form-switch mb-0';
            
            const switchInput = document.createElement('input');
            switchInput.type = 'checkbox';
            switchInput.className = 'form-check-input';
            switchInput.id = 'sam3-toggle-switch';
            switchInput.role = 'switch';
            switchInput.title = '启用/关闭SAM3分割工具';
            
            switchDiv.appendChild(switchInput);
            
            // 创建状态标签
            const statusLabel = document.createElement('span');
            statusLabel.id = 'sam3-status-label';
            statusLabel.textContent = '关闭';
            statusLabel.style.fontSize = '12px';
            statusLabel.style.color = '#6c757d';
            
            // 将组件添加到容器
            containerDiv.appendChild(label);
            containerDiv.appendChild(switchDiv);
            containerDiv.appendChild(statusLabel);
            
            toolSelector.appendChild(containerDiv);
            
            // 添加滑块开关事件监听器
            switchInput.addEventListener('change', async (event) => {
                if (this.sam3Tool) {
                    if (event.target.checked) {
                        // 检查SAM3是否已配置
                        const isConfigured = await this.checkSAM3Configuration();
                        if (isConfigured) {
                            // 如果已配置，开启SAM3
                            this.sam3Tool.activate();
                            // 更新状态显示
                            statusLabel.textContent = '开启';
                            statusLabel.style.color = '#28a745';
                            // 确保当前工具状态同步
                            this.currentTool = 'sam3';
                            this.redraw();
                        } else {
                            // 如果未配置，取消勾选并提示用户
                            event.target.checked = false;
                            statusLabel.textContent = '关闭';
                            statusLabel.style.color = '#6c757d';
                            this.showMessage('SAM3未配置或配置失败，请先在在线标注列表页配置SAM3', 'error');
                        }
                    } else {
                        // 如果当前是SAM3模式，停用SAM3
                        if (this.currentTool === 'sam3') {
                            this.sam3Tool.deactivate();
                            // 更新状态显示
                            statusLabel.textContent = '关闭';
                            statusLabel.style.color = '#6c757d';
                            // 确保当前工具状态同步
                            this.currentTool = 'segment';
                            this.redraw();
                        }
                    }
                }
            });
            
            console.log('全新SAM3控制容器已添加到工具栏');
            
            // 如果当前是实例分割项目，确保容器可见
            if (this.projectData && this.projectData.project_type === 'segmentation') {
                containerDiv.style.display = 'flex';
                console.log('设置SAM3控制容器为可见');
                
                // 默认关闭SAM3（滑块处于关闭状态）
                switchInput.checked = false;
                statusLabel.textContent = '关闭';
                statusLabel.style.color = '#6c757d';
            }
        } else {
            console.log('未找到工具选择器，无法添加SAM3控制容器');
        }
    }
    
    setupEventListeners() {
        // 画布事件
        this.canvas.addEventListener('mousedown', this.startDrawing.bind(this));
        this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.stopDrawing.bind(this));
        this.canvas.addEventListener('click', this.onCanvasClick.bind(this));
        this.canvas.addEventListener('dblclick', this.onCanvasDoubleClick.bind(this));
        
        // 鼠标滚轮缩放事件
        this.canvas.addEventListener('wheel', this.handleWheel.bind(this));
        
        // 按钮事件
        document.getElementById('save-annotation').addEventListener('click', this.saveAnnotation.bind(this));
        document.getElementById('mark-completed').addEventListener('click', this.markCompleted.bind(this));
        document.getElementById('mark-all-completed').addEventListener('click', this.markAllCompleted.bind(this));
        document.getElementById('clear-all').addEventListener('click', this.clearAllAnnotations.bind(this));
        document.getElementById('edit-classes-btn').addEventListener('click', this.showEditProjectClassesModal.bind(this));
        document.getElementById('prev-image').addEventListener('click', this.prevImage.bind(this));
        document.getElementById('next-image').addEventListener('click', this.nextImage.bind(this));
        document.getElementById('zoom-in').addEventListener('click', () => this.zoom(1.2));
        document.getElementById('zoom-out').addEventListener('click', () => this.zoom(0.8));
        document.getElementById('zoom-reset').addEventListener('click', this.resetZoom.bind(this));
        document.getElementById('ai-auto-annotate').addEventListener('click', this.showAutoAnnotateModal.bind(this));
        document.getElementById('stop-auto-annotate').addEventListener('click', this.stopAutoAnnotate.bind(this));
        document.getElementById('delete-image').addEventListener('click', this.deleteCurrentImage.bind(this));
        
        // 工具选择按钮事件
        document.getElementById('tool-box')?.addEventListener('click', () => this.setTool('box'));
        document.getElementById('tool-segment')?.addEventListener('click', () => this.setTool('segment'));
        document.getElementById('tool-obb')?.addEventListener('click', () => this.setTool('obb'));
        document.getElementById('tool-pose')?.addEventListener('click', () => this.setTool('keypoints'));
        
        // 关键点工具模式选择事件
        document.getElementById('keypoints-mode-keypoints')?.addEventListener('click', () => {
            if (this.currentTool === 'keypoints' && this.keypointsTool) {
                this.keypointsTool.setMode('keypoints');
                this.updateKeypointsModeButtons();
            }
        });
        
        document.getElementById('keypoints-mode-box')?.addEventListener('click', () => {
            if (this.currentTool === 'keypoints' && this.keypointsTool) {
                this.keypointsTool.setMode('box');
                this.updateKeypointsModeButtons();
            }
        });
        
        const toggleGuidelinesBtn = document.getElementById('toggle-guidelines');
        if (toggleGuidelinesBtn) {
            toggleGuidelinesBtn.addEventListener('click', this.toggleGuidelines.bind(this));
        }
        
        const filterCompletedBtn = document.getElementById('filter-completed');
        const filterUncompletedBtn = document.getElementById('filter-uncompleted');
        if (filterCompletedBtn) {
            filterCompletedBtn.addEventListener('click', this.toggleCompletedFilter.bind(this));
        }
        if (filterUncompletedBtn) {
            filterUncompletedBtn.addEventListener('click', this.toggleUncompletedFilter.bind(this));
        }
        
        const guidelineColorPicker = document.getElementById('guideline-color');
        if (guidelineColorPicker) {
            guidelineColorPicker.addEventListener('input', (e) => {
                this.guidelineColor = e.target.value;
                this.redraw();
            });
        }
        
        // 键盘快捷键
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
        document.addEventListener('keyup', this.handleKeyUp.bind(this));
        
        // 搜索
        document.getElementById('image-search').addEventListener('input', this.filterImages.bind(this));
        
        // SAM3启用开关事件
        const enableSam3Switch = document.getElementById('enable-sam3-switch');
        if (enableSam3Switch) {
            enableSam3Switch.addEventListener('change', this.handleSam3ToggleChange.bind(this));
        }
    }
    
    // 新增方法：设置辅助线颜色（供annotation-manager.js调用）
    setGuidelineColor(color) {
        this.guidelineColor = color;
        this.redraw();
    }
    
    // 检查SAM3配置状态
    async checkSAM3Configuration() {
        try {
            const response = await fetch('/api/sam3/check_config');
            const data = await response.json();
            return data.configured === true;
        } catch (error) {
            console.error('检查SAM3配置失败:', error);
            return false;
        }
    }
    
    // 根据项目类型设置默认工具
    setDefaultToolByProjectType() {
        if (!this.projectData || !this.projectData.project_type) return;
        
        // 根据项目类型映射到工具类型
        const toolTypeMap = {
            'detection': 'box',
            'segmentation': 'segment',
            'obb': 'obb',
            'pose': 'keypoints'
        };
        
        let defaultTool = toolTypeMap[this.projectData.project_type] || 'box';
        
        // 实例分割项目：确保SAM3按钮显示，但不自动启用
        if (this.projectData.project_type === 'segmentation') {
            // 确保使用segment工具作为默认工具
            this.setTool('segment');
            
            // 确保SAM3按钮被创建（如果尚未创建）
            this.addSAM3ToolButton();
            
            // 根据项目类型隐藏不相关的工具按钮
            this.hideIrrelevantTools();
            return;
        }
        
        this.setTool(defaultTool);
        
        // 根据项目类型隐藏不相关的工具按钮
        this.hideIrrelevantTools();
    }
    
    // 设置当前工具类型
    setTool(toolType) {
        console.log('切换工具到:', toolType);
        
        // 对于实例分割项目，允许在segment和SAM3之间自由切换
        let finalToolType = toolType;
        if (toolType === 'segment' && this.projectData && this.projectData.project_type === 'segmentation' && this.sam3Tool) {
            // 如果切换到segment工具且SAM3已激活，先停用SAM3
            if (this.sam3Tool.isActive) {
                this.sam3Tool.deactivate();
            }
            finalToolType = 'segment';
        } else if (toolType === 'sam3' && this.projectData && this.projectData.project_type === 'segmentation' && this.sam3Tool) {
            // 如果切换到SAM3工具且SAM3未激活，激活SAM3
            if (!this.sam3Tool.isActive) {
                this.sam3Tool.activate();
            }
            finalToolType = 'sam3';
        } else if (toolType === 'segment' && this.projectData && this.projectData.project_type === 'segmentation' && !this.sam3Tool) {
            // 如果SAM3工具未加载，允许使用segment
            finalToolType = 'segment';
        }
        
        // 如果是从SAM3切换到其他工具，先停用SAM3
        if (this.currentTool === 'sam3' && this.sam3Tool) {
            this.sam3Tool.deactivate();
        }
        
        // 如果切换到SAM3，需要特殊处理
        if (finalToolType === 'sam3') {
            if (this.sam3Tool) {
                // 确保SAM3工具已激活
                if (!this.sam3Tool.isActive) {
                    this.sam3Tool.activate();
                }
                    
// 显示SAM3操作选项
                this.showSAM3OperationOptions();
                this.showSam3HintInfo();
                
                // 更新按钮状态
                const toolButtons = document.querySelectorAll('#tool-selector .btn');
                toolButtons.forEach(btn => {
                    btn.classList.remove('active');
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline-primary');
                });
                
                const activeButton = document.getElementById('tool-sam3');
                if (activeButton) {
                    activeButton.classList.remove('btn-outline-primary');
                    activeButton.classList.add('btn-primary');
                    activeButton.classList.add('active');
                }
                
                this.currentTool = 'sam3';
                this.redraw();
                return;
            } else {
                alert('SAM3工具未加载，请稍后再试');
                // 切换回segment工具
                finalToolType = 'segment';
            }
        } else if (finalToolType === 'segment' && this.currentTool === 'sam3' && this.sam3Tool) {
            // 如果从SAM3切换回segment，确保停用SAM3
            if (this.sam3Tool.isActive) {
                this.sam3Tool.deactivate();
            }
        }
        
        this.currentTool = finalToolType;
        
        // 更新工具按钮的激活状态
        const toolButtons = document.querySelectorAll('#tool-selector .btn');
        toolButtons.forEach(btn => {
            btn.classList.remove('active');
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline-primary');
        });
        
        // 激活当前工具按钮
        const activeButton = document.getElementById(`tool-${toolType}`);
        if (activeButton) {
            activeButton.classList.remove('btn-outline-primary');
            activeButton.classList.add('btn-primary');
            activeButton.classList.add('active');
        }
        
        // 更新关键点模式选择栏的可见性
        this.updateKeypointsModeSelectorVisibility();
        
        // 如果切换到关键点工具，初始化模式按钮状态
        if (toolType === 'keypoints' && this.keypointsTool) {
            this.updateKeypointsModeButtons();
        }
        
        // 重绘画布
        this.redraw();
        
        // 重置各工具的状态，确保切换图片时不会保留之前的状态
        if (this.segmentationTool) {
            this.segmentationTool.isDrawing = false;
            this.segmentationTool.isDraggingPoint = false;
            this.segmentationTool.isDraggingSegment = false;
            this.segmentationTool.currentPoints = [];
            this.segmentationTool.tempPoint = null;
            this.segmentationTool.draggedPointIndex = -1;
        }
        
        if (this.obbTool) {
            this.obbTool.isDrawing = false;
            this.obbTool.isRotating = false;
            this.obbTool.currentBox = null;
        }
        
        if (this.keypointsTool) {
            this.keypointsTool.isDrawing = false;
            this.keypointsTool.selectedKeypoint = null;
            this.keypointsTool.isDraggingKeypoint = false;
            this.keypointsTool.currentKeypoints = [];
        }
        

    }
    
    // 更新关键点模式按钮状态
    updateKeypointsModeButtons() {
        if (this.currentTool !== 'keypoints') return;
        
        const keypointsMode = this.keypointsTool.currentMode;
        const keypointsBtn = document.getElementById('keypoints-mode-keypoints');
        const boxBtn = document.getElementById('keypoints-mode-box');
        
        if (keypointsBtn && boxBtn) {
            if (keypointsMode === 'keypoints') {
                keypointsBtn.classList.remove('btn-outline-primary');
                keypointsBtn.classList.add('btn-primary');
                boxBtn.classList.remove('btn-primary');
                boxBtn.classList.add('btn-outline-primary');
            } else {
                boxBtn.classList.remove('btn-outline-primary');
                boxBtn.classList.add('btn-primary');
                keypointsBtn.classList.remove('btn-primary');
                keypointsBtn.classList.add('btn-outline-primary');
            }
        }
    }
    
    // 显示或隐藏关键点模式选择栏
    updateKeypointsModeSelectorVisibility() {
        const selector = document.getElementById('keypoints-mode-selector');
        if (!selector) return;
        
        if (this.currentTool === 'keypoints') {
            selector.style.display = 'block';
        } else {
            selector.style.display = 'none';
        }
    }
    
    // 检查并启用SAM3功能
    async checkAndEnableSAM3Feature() {
        // 不自动启用SAM3，让用户手动开启
        // 保持默认为segment工具
    }
    
    // 根据项目类型隐藏不相关的工具按钮
    hideIrrelevantTools() {
        if (!this.projectData || !this.projectData.project_type) return;
        
        // 获取所有工具按钮
        const toolButtons = {
            'box': document.getElementById('tool-box'),
            'segment': document.getElementById('tool-segment'),
            'obb': document.getElementById('tool-obb'),
            'keypoints': document.getElementById('tool-keypoints'),
            'sam3': document.getElementById('sam3-control-container')  // 全新SAM3控制容器
        };
        
        // 根据项目类型和SAM3激活状态决定显示哪些工具
        const projectType = this.projectData.project_type;
        
        // 隐藏所有存在的工具按钮（但不包括SAM3滑块开关）
        Object.entries(toolButtons).forEach(([key, button]) => {
            if (button && key !== 'sam3') {  // 不隐藏SAM3滑块
                button.style.display = 'none';
            }
        });
        
        // 根据项目类型显示相应的工具按钮
        if (projectType === 'detection') {
            if (toolButtons['box']) toolButtons['box'].style.display = 'inline-block';
        } else if (projectType === 'segmentation') {
            // 对于实例分割项目，始终显示SAM3按钮
            if (toolButtons['sam3']) toolButtons['sam3'].style.display = 'flex';
            
            // 隐藏segment按钮，只使用SAM3滑块控制
            if (toolButtons['segment']) toolButtons['segment'].style.display = 'none';
            
            // 确保其他不相关的工具按钮隐藏
            const otherTools = ['box', 'obb', 'keypoints'];
            otherTools.forEach(tool => {
                const button = toolButtons[tool];
                if (button) {
                    button.style.display = 'none';
                }
            });
            
            // 确保SAM3操作按钮被创建
            this.ensureSAM3OperationButtonsCreated();
            
            // 只有当SAM3激活时才显示操作工具栏
            const sam3Toolbar = document.getElementById('sam3-operation-toolbar');
            if (sam3Toolbar) {
                if (this.sam3Tool && this.sam3Tool.isActive) {
                    sam3Toolbar.style.display = 'block';
                } else {
                    sam3Toolbar.style.display = 'none';
                }
            }
        } else if (projectType === 'obb') {
            if (toolButtons['obb']) toolButtons['obb'].style.display = 'inline-block';
        } else if (projectType === 'pose') {
            if (toolButtons['keypoints']) toolButtons['keypoints'].style.display = 'inline-block';
        }
    }
    
    // 确保SAM3操作按钮事件绑定
    ensureSAM3OperationButtonsCreated() {
        // 绑定SAM3操作按钮事件到预定义的HTML元素
        
        // 点提示按钮
        const pointBtn = document.getElementById('sam3-point-mode');
        if (pointBtn && !pointBtn.hasAttribute('data-bound')) {
            pointBtn.addEventListener('click', () => {
                if (this.sam3Tool) {
                    this.sam3Tool.setPromptType('point');
                }
            });
            pointBtn.setAttribute('data-bound', 'true');
        }
        
        // 框提示按钮
        const boxBtn = document.getElementById('sam3-box-mode');
        if (boxBtn && !boxBtn.hasAttribute('data-bound')) {
            boxBtn.addEventListener('click', () => {
                if (this.sam3Tool) {
                    this.sam3Tool.setPromptType('box');
                }
            });
            boxBtn.setAttribute('data-bound', 'true');
        }
        
        // 清除按钮
        const clearBtn = document.getElementById('sam3-clear');
        if (clearBtn && !clearBtn.hasAttribute('data-bound')) {
            clearBtn.addEventListener('click', () => {
                if (this.sam3Tool) {
                    this.sam3Tool.clearPrompts();
                }
            });
            clearBtn.setAttribute('data-bound', 'true');
        }
        
        // 执行分割按钮
        const executeBtn = document.getElementById('sam3-execute');
        if (executeBtn && !executeBtn.hasAttribute('data-bound')) {
            executeBtn.addEventListener('click', () => {
                if (this.sam3Tool) {
                    this.sam3Tool.executeSegmentation();
                }
            });
            executeBtn.setAttribute('data-bound', 'true');
        }
    }
    

    
    // 加载图片
    loadImage() {
        if (!this.currentImageData) return;
        
        // 更新图片列表选中状态
        this.updateImageListSelection();
        
        // 加载图片
        const img = new Image();
        img.onload = () => {
            this.currentImage = img;
            this.resizeCanvas();
            // 确保在加载标注之前画布尺寸已经正确设置
            setTimeout(() => {
                this.loadAnnotations();
                this.redraw();
            }, 0);
            
            document.getElementById('current-image-name').textContent = this.currentImageData.image_name;
            
            // 切换到新图片后立即更新标注进度
            // 改进：添加异步处理和错误捕获
            (async () => {
                try {
                    await this.loadProjectStats();
                } catch (error) {
                    console.error('更新进度失败:', error);
                }
            })();
        };
        
        // 使用API端点获取图片文件
        img.src = `/api/annotation/projects/${this.projectId}/images/${this.currentImageData.id}/file`;
    }

    onMouseMove(e) {
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY, rawX: mouseX, rawY: mouseY } = this.getCanvasCoordinates(e);
        this.mouseX = mouseX;
        this.mouseY = mouseY;
        
        // 如果SAM3工具处于活动状态，交由SAM3工具处理
        if (this.currentTool === 'sam3' && this.sam3Tool && this.sam3Tool.isActive) {
            this.sam3Tool.onMouseMove(e);
            return;
        }
        
        // 根据当前工具类型处理鼠标移动
        if (this.currentTool === 'segment') {
            // 如果实例分割工具正在绘制中，更新临时点位置
            if (this.segmentationTool.isDrawing) {
                // 使用通用坐标转换方法
                const { x: canvasX, y: canvasY } = this.getCanvasCoordinates(e);
                this.segmentationTool.tempPoint = { x: canvasX, y: canvasY };
                this.segmentationTool.redraw();
                // 不返回，继续执行下面的代码以确保辅助线更新
            }
            // 如果正在拖拽点或整体拖动分割区域
            else if (this.segmentationTool.isDraggingPoint || this.segmentationTool.isDraggingSegment) {
                this.segmentationTool.onMouseMove(e);
                return;
            }
        } else if (this.currentTool === 'obb' && this.obbTool.isDrawing) {
            // 如果旋转框工具正在绘制中，更新当前框
            this.obbTool.onDrawing(e);
            return;
        } else if (this.obbTool.isRotating) {
            // 如果正在旋转旋转框，更新旋转角度
            console.log('正在旋转旋转框');
            this.obbTool.onRotating(e);
            return;
        } else if (this.currentTool === 'keypoints' && this.keypointsTool.isDraggingKeypoint) {
            this.keypointsTool.dragKeypoint(e);
            return;
        }
        
        // 处理关键点工具的拖拽和调整大小
        if (this.currentTool === 'keypoints' && this.selectedAnnotation) {
            // 检查是否是关键点标注（包含关键点）
            if (this.selectedAnnotation.keypoints) {
                if (this.isDragging && this.selectedAnnotation) {
                    // 拖拽关键点标注框
                    const deltaX = canvasX - this.dragStartX;
                    const deltaY = canvasY - this.dragStartY;
                    
                    // 更新标注框位置
                    this.selectedAnnotation.x += deltaX;
                    this.selectedAnnotation.y += deltaY;
                    
                    // 同时更新框内的所有关键点位置
                    if (this.selectedAnnotation.keypoints) {
                        this.selectedAnnotation.keypoints.forEach(kp => {
                            kp.x += deltaX;
                            kp.y += deltaY;
                        });
                    }
                    
                    // 更新拖拽起始位置
                    this.dragStartX = canvasX;
                    this.dragStartY = canvasY;
                    
                    // 实时更新左侧列表信息
                    this.updateAnnotationList();
                    this.redraw();
                    return;
                } else if (this.isResizing && this.selectedAnnotation) {
                    // 调整关键点标注框大小
                    this.resizeAnnotation(this.selectedAnnotation, this.resizeHandle, canvasX, canvasY);
                    
                    // 重新绘制
                    this.redraw();
                    return;
                }
            } else {
                // 如果是普通矩形框（在关键点工具的矩形框模式下），也允许拖拽和调整大小
                if (this.isDragging && this.selectedAnnotation) {
                    // 拖拽普通矩形框
                    const deltaX = canvasX - this.dragStartX;
                    const deltaY = canvasY - this.dragStartY;
                    
                    // 更新标注框位置
                    this.selectedAnnotation.x += deltaX;
                    this.selectedAnnotation.y += deltaY;
                    
                    // 更新拖拽起始位置
                    this.dragStartX = canvasX;
                    this.dragStartY = canvasY;
                    
                    // 实时更新左侧列表信息
                    this.updateAnnotationList();
                    this.redraw();
                    return;
                } else if (this.isResizing && this.selectedAnnotation) {
                    // 调整普通矩形框大小
                    this.resizeAnnotation(this.selectedAnnotation, this.resizeHandle, canvasX, canvasY);
                    
                    // 重新绘制
                    this.redraw();
                    return;
                }
            }
        }
        
        if (this.isDrawing) {
            if (this.currentTool === 'obb') {
                this.obbTool.onDrawing(e);
            } else {
                this.currentBox = {
                    x: Math.min(this.startX, canvasX),
                    y: Math.min(this.startY, canvasY),
                    width: Math.abs(canvasX - this.startX),
                    height: Math.abs(canvasY - this.startY)
                };
            }
            
            this.redraw();
        } else if (this.isDragging && this.selectedAnnotation) {
            // 拖拽标注框
            const deltaX = canvasX - this.dragStartX;
            const deltaY = canvasY - this.dragStartY;
            
            // 更新标注框位置
            this.selectedAnnotation.x += deltaX;
            this.selectedAnnotation.y += deltaY;
            
            // 更新拖拽起始位置
            this.dragStartX = canvasX;
            this.dragStartY = canvasY;
            
            // 实时更新左侧列表信息
            this.updateAnnotationList();
            this.redraw();
        } else if (this.isResizing && this.selectedAnnotation) {
            // 调整标注框大小
            this.resizeAnnotation(this.selectedAnnotation, this.resizeHandle, canvasX, canvasY);
            
            // 实时更新左侧列表信息
            this.updateAnnotationList();
            this.redraw();
        } else if (this.isPanning) {
            // 拖动画布
            this.offsetX += this.mouseX - this.panStartX;
            this.offsetY += this.mouseY - this.panStartY;
            this.panStartX = this.mouseX;
            this.panStartY = this.mouseY;
            this.redraw();
        }
        
        // 更新鼠标样式
        this.updateCursorStyle(canvasX, canvasY);
        
        // 每次鼠标移动都重绘，以确保辅助线跟随鼠标
        if (this.showGuidelines) {
            this.redraw();
        }
        
        // 如果正在使用实例分割工具绘制，也重绘以更新临时点
        if (this.currentTool === 'segment' && this.segmentationTool.isDrawing) {
            this.segmentationTool.redraw();
        }
        
        // 如果正在使用关键点工具绘制矩形框，更新临时框
        if (this.currentTool === 'keypoints' && this.keypointsTool.isDrawingBox) {
            this.keypointsTool.onMouseMove(e);
        }
        if (this.currentTool === 'keypoints' && (this.keypointsTool.isDraggingKeypoint || this.isDragging || this.isResizing)) {
            this.keypointsTool.onMouseMove(e);
        }
    }
    
    updateCursorStyle(canvasX, canvasY) {
        // 如果正在绘制、拖拽、调整大小或抓手模式，使用特定光标
        if (this.isDrawing || this.isDragging || this.isResizing || this.isPanning) {
            return; // 保持当前操作的光标样式
        }
        
        // 编辑模式下，根据鼠标位置显示不同的光标
        if (this.selectedAnnotation) {
            // 对于旋转框，先检查旋转控制点
            let isRotationHandle = false;
            if (this.selectedAnnotation.hasOwnProperty('angle')) {
                // 检查是否在旋转控制点上
                const centerX = this.selectedAnnotation.x + this.selectedAnnotation.width / 2;
                const centerY = this.selectedAnnotation.y + this.selectedAnnotation.height / 2;
                const handleSize = 8;
                
                // 计算旋转后的控制点位置（右侧）
                const angle = this.selectedAnnotation.angle || 0;
                const offsetX = (this.selectedAnnotation.width / 2 - 5);
                const offsetY = 0;
                
                // 应用旋转矩阵
                const rotatedX = centerX + offsetX * Math.cos(angle) - offsetY * Math.sin(angle);
                const rotatedY = centerY + offsetX * Math.sin(angle) + offsetY * Math.cos(angle);
                
                if (canvasX >= rotatedX - handleSize && canvasX <= rotatedX + handleSize &&
                    canvasY >= rotatedY - handleSize && canvasY <= rotatedY + handleSize) {
                    isRotationHandle = true;
                }
                
                // 计算旋转后的控制点位置（左侧）
                const offsetX2 = -(this.selectedAnnotation.width / 2 - 5);
                const offsetY2 = 0;
                
                // 应用旋转矩阵
                const rotatedX2 = centerX + offsetX2 * Math.cos(angle) - offsetY2 * Math.sin(angle);
                const rotatedY2 = centerY + offsetX2 * Math.sin(angle) + offsetY2 * Math.cos(angle);
                
                if (canvasX >= rotatedX2 - handleSize && canvasX <= rotatedX2 + handleSize &&
                    canvasY >= rotatedY2 - handleSize && canvasY <= rotatedY2 + handleSize) {
                    isRotationHandle = true;
                }
                
                if (isRotationHandle) {
                    this.canvas.style.cursor = 'grab';
                    return;
                }
            }
            
            // 检查是否在调整大小的控制点上
            const handle = this.getResizeHandle(this.selectedAnnotation, canvasX, canvasY);
            if (handle) {
                switch (handle) {
                    case 'right':
                    case 'left':
                        this.canvas.style.cursor = 'ew-resize';
                        return;
                    case 'top':
                    case 'bottom':
                        this.canvas.style.cursor = 'ns-resize';
                        return;
                    case 'top-right':
                    case 'bottom-left':
                        this.canvas.style.cursor = 'ne-resize';
                        return;
                    case 'top-left':
                    case 'bottom-right':
                        this.canvas.style.cursor = 'nw-resize';
                        return;
                }
            }
            
            // 检查是否在标注框内部（用于拖拽）
            if (this.isInAnnotationArea(this.selectedAnnotation, canvasX, canvasY)) {
                this.canvas.style.cursor = 'move';
                return;
            }
            
            // 检查是否在文字标题区域
            if (this.isInTitleArea(this.selectedAnnotation, canvasX, canvasY)) {
                this.canvas.style.cursor = 'pointer';
                return;
            }
        }
        
        // 默认光标（十字标记）
        this.canvas.style.cursor = 'crosshair';
    }

    resizeAnnotation(annotation, handle, canvasX, canvasY) {
        const minWidth = 5;
        const minHeight = 5;
        
        // 如果是旋转框，使用特殊处理
        if (annotation.hasOwnProperty('angle')) {
            this.resizeRotatedAnnotation(annotation, handle, canvasX, canvasY);
            return;
        }
        
        switch (handle) {
            case 'right':
                annotation.width = Math.max(minWidth, canvasX - annotation.x);
                break;
            case 'bottom':
                annotation.height = Math.max(minHeight, canvasY - annotation.y);
                break;
            case 'left':
                const newWidth = Math.max(minWidth, annotation.x + annotation.width - canvasX);
                annotation.x = annotation.x + annotation.width - newWidth;
                annotation.width = newWidth;
                break;
            case 'top':
                const newHeight = Math.max(minHeight, annotation.y + annotation.height - canvasY);
                annotation.y = annotation.y + annotation.height - newHeight;
                annotation.height = newHeight;
                break;
            case 'top-right':
                annotation.width = Math.max(minWidth, canvasX - annotation.x);
                annotation.height = Math.max(minHeight, canvasY - annotation.y);
                break;
            case 'bottom-left':
                const newWidthBL = Math.max(minWidth, annotation.x + annotation.width - canvasX);
                annotation.x = annotation.x + annotation.width - newWidthBL;
                annotation.width = newWidthBL;
                annotation.height = Math.max(minHeight, canvasY - annotation.y);
                break;
            case 'top-left':
                const newWidthTL = Math.max(minWidth, annotation.x + annotation.width - canvasX);
                annotation.x = annotation.x + annotation.width - newWidthTL;
                annotation.width = newWidthTL;
                const newHeightTL = Math.max(minHeight, annotation.y + annotation.height - canvasY);
                annotation.y = annotation.y + annotation.height - newHeightTL;
                annotation.height = newHeightTL;
                break;
            case 'bottom-right':
                annotation.width = Math.max(minWidth, canvasX - annotation.x);
                annotation.height = Math.max(minHeight, canvasY - annotation.y);
                break;
        }
    }
    
    // 调整旋转框大小
    resizeRotatedAnnotation(annotation, handle, canvasX, canvasY) {
        const minWidth = 5;
        const minHeight = 5;
        
        // 获取旋转框的中心点
        const centerX = annotation.x + annotation.width / 2;
        const centerY = annotation.y + annotation.height / 2;
        
        // 获取旋转角度
        const angle = annotation.angle || 0;
        
        // 将鼠标坐标转换为相对于旋转框中心的坐标
        const relativeX = canvasX - centerX;
        const relativeY = canvasY - centerY;
        
        // 应用反向旋转矩阵，将坐标转换为未旋转时的坐标系
        const unrotatedX = relativeX * Math.cos(-angle) - relativeY * Math.sin(-angle);
        const unrotatedY = relativeX * Math.sin(-angle) + relativeY * Math.cos(-angle);
        
        // 计算未旋转时的边界
        const left = -annotation.width / 2;
        const right = annotation.width / 2;
        const top = -annotation.height / 2;
        const bottom = annotation.height / 2;
        
        // 保存原始尺寸，用于边界检查
        const originalWidth = annotation.width;
        const originalHeight = annotation.height;
        
        // 根据不同的控制点调整大小
        switch (handle) {
            case 'right':
                annotation.width = Math.max(minWidth, unrotatedX - left);
                break;
            case 'bottom':
                annotation.height = Math.max(minHeight, unrotatedY - top);
                break;
            case 'left':
                const newWidth = Math.max(minWidth, right - unrotatedX);
                annotation.x = centerX - (newWidth / 2);
                annotation.width = newWidth;
                break;
            case 'top':
                const newHeight = Math.max(minHeight, bottom - unrotatedY);
                annotation.y = centerY - (newHeight / 2);
                annotation.height = newHeight;
                break;
            case 'top-right':
                annotation.width = Math.max(minWidth, unrotatedX - left);
                annotation.height = Math.max(minHeight, bottom - unrotatedY);
                break;
            case 'bottom-left':
                const newWidthBL = Math.max(minWidth, right - unrotatedX);
                annotation.x = centerX - (newWidthBL / 2);
                annotation.width = newWidthBL;
                annotation.height = Math.max(minHeight, unrotatedY - top);
                break;
            case 'top-left':
                const newWidthTL = Math.max(minWidth, right - unrotatedX);
                const newHeightTL = Math.max(minHeight, bottom - unrotatedY);
                annotation.x = centerX - (newWidthTL / 2);
                annotation.y = centerY - (newHeightTL / 2);
                annotation.width = newWidthTL;
                annotation.height = newHeightTL;
                break;
            case 'bottom-right':
                annotation.width = Math.max(minWidth, unrotatedX - left);
                annotation.height = Math.max(minHeight, unrotatedY - top);
                break;
        }
        
        // 确保尺寸不会变为负数或过小
        annotation.width = Math.max(minWidth, annotation.width);
        annotation.height = Math.max(minHeight, annotation.height);
        
        // 更新中心点坐标
        annotation.x = centerX - annotation.width / 2;
        annotation.y = centerY - annotation.height / 2;
    }
    
    getCanvasCoordinates(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        
        const clickX = (e.clientX - rect.left) * scaleX;
        const clickY = (e.clientY - rect.top) * scaleY;
        
        return {
            x: (clickX - this.offsetX) / this.scale,
            y: (clickY - this.offsetY) / this.scale,
            rawX: clickX,
            rawY: clickY
        };
    }

    isInTitleArea(annotation, canvasX, canvasY, index = -1) {
        const className = this.projectData.classes[annotation.class_id] || `Class ${annotation.class_id}`;
        const label = index >= 0 ? `${index + 1}. ${className}` : className;
        
        // 创建临时canvas测量文字宽度
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.font = '12px Arial';
        const textWidth = tempCtx.measureText(label).width;
        
        // 标题区域：文字位置 + 边距
        const titleLeft = annotation.x + 4;
        const titleRight = annotation.x + textWidth + 8;
        const titleTop = annotation.y - 20;
        const titleBottom = annotation.y - 6;
        
        return canvasX >= titleLeft && canvasX <= titleRight &&
               canvasY >= titleTop && canvasY <= titleBottom;
    }

    isInAnnotationArea(annotation, canvasX, canvasY) {
        // 检查是否为实例分割标注（多点区域）
        if (annotation.points) {
            // 使用射线投射算法检测点是否在多边形内
            return this.isPointInPolygon(canvasX, canvasY, annotation.points);
        }
        
        // 默认的矩形区域检测
        return canvasX >= annotation.x && canvasX <= annotation.x + annotation.width &&
               canvasY >= annotation.y && canvasY <= annotation.y + annotation.height;
    }
    
    // 检测点是否在多边形内（射线投射算法）
    isPointInPolygon(x, y, points) {
        if (!points || points.length < 3) return false;
        
        let inside = false;
        for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
            const xi = points[i][0], yi = points[i][1];
            const xj = points[j][0], yj = points[j][1];
            
            const intersect = ((yi > y) !== (yj > y)) &&
                (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        
        return inside;
    }

    setSelectedAnnotation(annotation, byClick = false) {
        this.selectedAnnotation = annotation;
        this.selectedByClick = byClick;
        this.updateAnnotationList(); // 更新标注列表显示
        this.redraw(); // 重新绘制以显示选中状态
    }

    onCanvasClick(e) {
        // 如果正在绘制或处于抓手模式，不处理点击选择
        if (this.isDrawing || this.isPanning || this.isPanReady) return;
        
        // 如果刚刚完成绘制，不处理点击选择（防止重新选中）
        if (this.justFinishedDrawing) {
            this.justFinishedDrawing = false;
            return;
        }
        
        // 如果刚刚完成拖拽或调整大小操作，不处理点击选择（保持选中状态）
        if (this.justFinishedDragging || this.justFinishedResizing) {
            this.justFinishedDragging = false;
            this.justFinishedResizing = false;
            return;
        }
        
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.getCanvasCoordinates(e);
        
        // 检查是否点击了标注框（使用与startDrawing相同的精确规则）
        let clickedAnnotation = null;
        let clickedIndex = -1;
        
        // 从后往前遍历，确保点击的是最上层的标注框
        for (let i = this.annotations.length - 1; i >= 0; i--) {
            const ann = this.annotations[i];
            
            // 方式1：检查是否点击了标注框左上角的文字标题区域
            if (this.isInTitleArea(ann, canvasX, canvasY, i)) {
                clickedAnnotation = ann;
                clickedIndex = i;
                break;
            }
            
            // 方式2：按住Ctrl键+点击标注框区域
            if (e.ctrlKey && this.isInAnnotationArea(ann, canvasX, canvasY)) {
                clickedAnnotation = ann;
                clickedIndex = i;
                break;
            }
        }
        
        // 如果没有点击任何标注（点击了空白区域）
        if (!clickedAnnotation) {
            // 点击空白区域取消选择
            this.selectedAnnotation = null;
            this.updateAnnotationList();
            this.redraw();
        } else {
            // 更新选中的标注框
            this.setSelectedAnnotation(clickedAnnotation);
            
            // 如果点击了标注框，可以在这里添加其他处理逻辑
            if (clickedAnnotation) {
                console.log('选中标注框:', clickedIndex);
            }
        }
    }
    
    // 处理画布双击事件
    onCanvasDoubleClick(e) {
        // 根据当前工具类型处理双击事件
        if (this.currentTool === 'segment' && this.segmentationTool.isDrawing) {
            this.segmentationTool.finishDrawingOnDoubleClick(e);
            return;
        }
        
        // 其他工具的双击处理可以在这里添加
    }
    
    toggleGuidelines() {
        this.showGuidelines = !this.showGuidelines;
        const btn = document.getElementById('toggle-guidelines');
        if (btn) {
            btn.textContent = this.showGuidelines ? '隐藏辅助线' : '显示辅助线';
            btn.className = this.showGuidelines ? 'btn btn-secondary' : 'btn btn-outline-secondary';
        }
        this.redraw();
    }
    
    async loadProject() {
        const urlParams = new URLSearchParams(window.location.search);
        this.projectId = urlParams.get('project_id');
        
        if (!this.projectId) {
            alert('未指定项目ID');
            return;
        }
        
        try {
            // 加载项目信息
            const response = await fetch(`/api/annotation/projects/${this.projectId}`);
            this.projectData = await response.json();
            
            this.updateProjectInfo();
            this.loadClasses();
            await this.loadImages();
            await this.loadProjectStats();
            await this.loadAvailableModels();
            
            // 根据项目类型设置默认工具
            this.setDefaultToolByProjectType();
            
            // 如果是姿态估计项目，确保关键点工具能获取配置
            if (this.projectData.project_type === 'pose' && this.keypointsTool) {
                this.keypointsTool.setClassKeypointsConfig(this.projectData.class_keypoints || []);
            }
            
            // 如果是实例分割项目，确保SAM3工具按钮存在并显示
            if (this.projectData.project_type === 'segmentation') {
                // 确保SAM3按钮被创建（如果尚未创建）
                this.addSAM3ToolButton();
                
                // 确保SAM3控制容器可见（在容器创建后）
                setTimeout(() => {
                    const sam3Container = document.getElementById('sam3-control-container');
                    if (sam3Container) {
                        sam3Container.style.display = 'flex';
                        console.log('SAM3控制容器设置为可见');
                    } else {
                        console.log('未找到SAM3控制容器');
                    }
                }, 100); // 稍微延时以确保容器已被创建
                
                // 再次调用hideIrrelevantTools以确保所有显示状态正确
                setTimeout(() => {
                    this.hideIrrelevantTools();
                    console.log('再次调用hideIrrelevantTools以确保显示状态');
                }, 150); // 稍晚一点执行，确保前面的设置已完成
            }
        } catch (error) {
            console.error('加载项目失败:', error);
            alert('加载项目失败');
        }
    }
    
    updateProjectInfo() {
        document.getElementById('project-name').textContent = this.projectData.name;
        document.getElementById('class-count').textContent = this.projectData.classes.length;
        
        // 如果是姿态估计项目，确保关键点工具能获取配置
        if (this.projectData.project_type === 'pose' && this.keypointsTool) {
            this.keypointsTool.setClassKeypointsConfig(this.projectData.class_keypoints || []);
        }
    }
    
    loadClasses() {
        const classList = document.getElementById('class-list');
        classList.innerHTML = '';
        
        this.projectData.classes.forEach((className, index) => {
            const classItem = document.createElement('div');
            classItem.className = 'annotation-item';
            classItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span>${className}</span>
                    <span class="badge bg-secondary">${index + 1}</span>
                </div>
            `;
            classItem.addEventListener('click', () => this.selectClass(index, className));
            classList.appendChild(classItem);
        });
        
        // 默认选择第一个类别
        if (this.projectData.classes.length > 0) {
            this.selectClass(0, this.projectData.classes[0]);
        }
    }
    
    // 删除当前选中的图片
    async deleteCurrentImage() {
        if (!this.currentImageData) return;
        
        if (!confirm(`确定要删除图片 "${this.currentImageData.image_name}" 吗？\n此操作不可恢复！`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/annotation/images/${this.currentImageData.id}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const currentIndex = this.currentImageIndex;
                
                // 从列表中移除
                this.imageList.splice(currentIndex, 1);
                
                if (this.imageList.length > 0) {
                    // 如果删除的是最后一张图片，则加载前一张；否则加载当前索引的图片
                    const nextIndex = currentIndex >= this.imageList.length ? currentIndex - 1 : currentIndex;
                    await this.loadImage(nextIndex);
                } else {
                    // 如果没有图片了，清空当前显示
                    this.currentImage = null;
                    this.currentImageData = null;
                    this.annotations = [];
                    document.getElementById('current-image-name').textContent = '没有图片';
                    this.updateAnnotationList();
                    this.redraw();
                }
                
                this.updateImageList();
                await this.loadProjectStats();
                this.showMessage('图片删除成功', 'success');
            } else {
                this.showMessage('删除失败', 'error');
            }
        } catch (error) {
            console.error('删除图片失败:', error);
            this.showMessage('删除失败: ' + error.message, 'error');
        }
    }
    
    selectClass(index, name) {
        this.selectedClass = index;
        document.getElementById('selected-class').textContent = name;
        
        // 更新类别列表的选中状态
        document.querySelectorAll('#class-list .annotation-item').forEach((item, i) => {
            item.classList.toggle('selected', i === index);
        });
    }
    
    async loadImages() {
        try {
            const response = await fetch(`/api/annotation/projects/${this.projectId}/images?limit=10000`);
            this.imageList = await response.json();
            
            console.log('加载图片列表:', this.imageList);
            
            this.updateImageList();
            
            if (this.imageList.length > 0) {
                await this.loadImage(0);
            }
            
        } catch (error) {
            console.error('加载图片列表失败:', error);
        }
    }
    
    updateImageList() {
        const imageListContainer = document.getElementById('image-list');
        imageListContainer.innerHTML = '';
        
        // 应用筛选条件
        const filteredImages = this.imageList.filter(imageData => {
            // 如果没有启用任何筛选，则显示所有图片
            if (!this.showCompleted && !this.showUncompleted) {
                return true;
            }
            
            // 如果启用了已完成筛选，则显示已完成的图片
            if (this.showCompleted && imageData.is_completed) {
                return true;
            }
            
            // 如果启用了未完成筛选，则显示未完成的图片
            if (this.showUncompleted && !imageData.is_completed) {
                return true;
            }
            
            // 其他情况不显示
            return false;
        });
        
        // 保存筛选后的图片列表和对应的原始索引
        this.filteredImageList = filteredImages;
        this.filteredImageIndices = filteredImages.map(filteredImg => 
            this.imageList.findIndex(img => img.id === filteredImg.id)
        );
        
        this.filteredImageList.forEach((imageData, index) => {
            const imageItem = document.createElement('div');
            imageItem.className = `annotation-item ${this.filteredImageIndices[index] === this.currentImageIndex ? 'selected' : ''}`;
            imageItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span class="text-truncate">${imageData.image_name}</span>
                    <div>
                        ${imageData.is_completed ? '<i class="fas fa-check text-success"></i>' : ''}
                        <span class="badge bg-info">${imageData.annotations.length}</span>
                    </div>
                </div>
            `;
            imageItem.addEventListener('click', () => this.loadImage(this.filteredImageIndices[index]));
            imageListContainer.appendChild(imageItem);
        });
        
        document.getElementById('total-images').textContent = this.imageList.length;
    }
    
    async loadImage(index) {
        if (index < 0 || index >= this.imageList.length) return;
        
        // 重置各工具的状态，确保切换图片时不会保留之前的状态
        if (this.segmentationTool) {
            this.segmentationTool.isDrawing = false;
            this.segmentationTool.isDraggingPoint = false;
            this.segmentationTool.isDraggingSegment = false;
            this.segmentationTool.currentPoints = [];
            this.segmentationTool.tempPoint = null;
            this.segmentationTool.draggedPointIndex = -1;
        }
        
        if (this.obbTool) {
            this.obbTool.isDrawing = false;
            this.obbTool.isRotating = false;
            this.obbTool.currentBox = null;
        }
        
        if (this.keypointsTool) {
            this.keypointsTool.isDrawing = false;
            this.keypointsTool.selectedKeypoint = null;
            this.keypointsTool.isDraggingKeypoint = false;
            this.keypointsTool.currentKeypoints = [];
        }
        
        // 保存上一张图片的数据引用
        const previousImageData = this.currentImageData;
        const previousImageIndex = this.currentImageIndex;
        
        // 更新当前图片索引和数据
        this.currentImageIndex = index;
        this.currentImageData = this.imageList[index];
        
        // 检查并自动标记上一张图片（如果有标注且未完成）
        if (previousImageData && 
            previousImageData.annotations && 
            previousImageData.annotations.length > 0 && 
            !previousImageData.is_completed) {
            // 创建临时函数来标记上一张图片
            const markPreviousCompleted = async () => {
                try {
                    const response = await fetch(`/api/annotation/images/${previousImageData.id}`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            is_completed: true
                        })
                    });
                    
                    if (response.ok) {
                        // 更新本地数据
                        previousImageData.is_completed = true;
                        if (this.imageList && this.imageList[previousImageIndex] !== undefined) {
                            this.imageList[previousImageIndex].is_completed = true;
                        }
                        this.updateImageList();
                        // 更新标注进度
                        await this.loadProjectStats();
                    }
                } catch (error) {
                    console.error('自动标记完成失败:', error);
                }
            };
            
            (async () => {
                await markPreviousCompleted();
            })().catch(err => {
                console.error('执行标记完成过程中出错:', err);
            });
        }
        
        // 更新图片列表选中状态
        this.updateImageListSelection();
        
        // 加载图片
        const img = new Image();
        img.onload = () => {
            this.currentImage = img;
            this.resizeCanvas();
            // 确保在加载标注之前画布尺寸已经正确设置
            setTimeout(() => {
                this.loadAnnotations();
                this.redraw();
            }, 0);
            
            document.getElementById('current-image-name').textContent = this.currentImageData.image_name;
            
            // 切换到新图片后立即更新标注进度
            // 改进：添加异步处理和错误捕获
            (async () => {
                try {
                    await this.loadProjectStats();
                } catch (error) {
                    console.error('更新进度失败:', error);
                }
            })();
        };
        
        // 使用API端点获取图片文件
        img.src = `/api/annotation/projects/${this.projectId}/images/${this.currentImageData.id}/file`;
    }
    
    resizeCanvas() {
        if (!this.currentImage) return;
        
        // 获取用户屏幕分辨率和可用空间
        const screenWidth = window.screen.width;
        const screenHeight = window.screen.height;
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        
        // 计算可用空间（考虑页面布局和其他元素）
        // 为侧边栏和其他UI元素预留空间
        const reservedWidth = 300; // 左右两侧面板的宽度
        const reservedHeight = 150; // 顶部工具栏、底部导航等的高度
        
        // 计算最大可用尺寸
        const maxWidth = Math.min(screenWidth * 0.8, windowWidth - reservedWidth, 1600); // 最大不超过1600px
        const maxHeight = Math.min(screenHeight * 0.7, windowHeight - reservedHeight, 1600); // 最大不超过1600px
        
        let { width, height } = this.currentImage;
        
        // 移除可能导致尺寸限制的条件，让画布能更好地适应容器
        // 只在图片尺寸超过最大限制时才进行缩放
        if (width > maxWidth || height > maxHeight) {
            // 保持宽高比
            const aspectRatio = width / height;
            
            if (width > maxWidth) {
                width = maxWidth;
                height = width / aspectRatio;
            }
            
            if (height > maxHeight) {
                height = maxHeight;
                width = height * aspectRatio;
            }
        }
        
        // 设置画布尺寸
        this.canvas.width = width;
        this.canvas.height = height;
        
        // 重置缩放比例和偏移量
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
    }
    
    loadAnnotations() {
        console.log('开始加载标注数据:', this.currentImageData.annotations);
        console.log('画布尺寸:', this.canvas.width, this.canvas.height);
        this.annotations = (this.currentImageData.annotations || []).map(ann => {
            // 检查是否为分割标注
            if (ann.points) {
                // 实例分割格式: class_id x1 y1 x2 y2 ...
                // 检查点坐标是否已经是归一化坐标（值在0-1范围内）
                let isNormalized = true;
                if (ann.points.length > 0) {
                    if (Array.isArray(ann.points[0])) {
                        // 如果是二维数组格式 [[x1, y1], [x2, y2], ...]
                        for (let i = 0; i < ann.points.length; i++) {
                            if (ann.points[i][0] > 1 || ann.points[i][1] > 1 || ann.points[i][0] < 0 || ann.points[i][1] < 0) {
                                isNormalized = false;
                                break;
                            }
                        }
                    } else {
                        // 如果是一维数组格式 [x1, y1, x2, y2, ...]
                        for (let i = 0; i < ann.points.length; i += 2) {
                            if (ann.points[i] > 1 || ann.points[i+1] > 1 || ann.points[i] < 0 || ann.points[i+1] < 0) {
                                isNormalized = false;
                                break;
                            }
                        }
                    }
                }
                
                const points = [];
                if (ann.points.length > 0) {
                    if (Array.isArray(ann.points[0])) {
                        // 如果是二维数组格式 [[x1, y1], [x2, y2], ...]
                        if (isNormalized) {
                            // 如果是归一化坐标，转换为画布坐标
                            ann.points.forEach(point => {
                                points.push([
                                    point[0] * this.canvas.width,
                                    point[1] * this.canvas.height
                                ]);
                            });
                        } else {
                            // 如果不是归一化坐标，直接使用
                            ann.points.forEach(point => {
                                points.push([
                                    point[0],
                                    point[1]
                                ]);
                            });
                        }
                    } else {
                        // 如果是一维数组格式 [x1, y1, x2, y2, ...]
                        if (isNormalized) {
                            // 如果是归一化坐标，转换为画布坐标
                            for (let i = 0; i < ann.points.length; i += 2) {
                                points.push([
                                    ann.points[i] * this.canvas.width,
                                    ann.points[i+1] * this.canvas.height
                                ]);
                            }
                        } else {
                            // 如果不是归一化坐标，直接使用
                            for (let i = 0; i < ann.points.length; i += 2) {
                                points.push([
                                    ann.points[i],
                                    ann.points[i+1]
                                ]);
                            }
                        }
                    }
                }
                
                // 计算边界框
                if (points.length > 0) {
                    let minX = points[0][0], maxX = points[0][0];
                    let minY = points[0][1], maxY = points[0][1];
                    
                    points.forEach(point => {
                        minX = Math.min(minX, point[0]);
                        maxX = Math.max(maxX, point[0]);
                        minY = Math.min(minY, point[1]);
                        maxY = Math.max(maxY, point[1]);
                    });
                    
                    // 确保边界框值是有效的数字
                    minX = isNaN(minX) ? 0 : minX;
                    minY = isNaN(minY) ? 0 : minY;
                    maxX = isNaN(maxX) ? this.canvas.width : maxX;
                    maxY = isNaN(maxY) ? this.canvas.height : maxY;
                    
                    return {
                        class_id: ann.class_id,
                        points: points,
                        x: minX,
                        y: minY,
                        width: maxX - minX,
                        height: maxY - minY
                    };
                } else {
                    return {
                        class_id: ann.class_id,
                        points: points
                    };
                }
            }
            // 检查是否为关键点标注
            else if (ann.keypoints) {
                // 关键点格式: class_id x_center y_center width height x1 y1 v1 x2 y2 v2 ...
                const keypoints = [];
                
                // 关键点数据是对象数组格式 [{x: 0.1, y: 0.2, v: 2}, ...]
                if (Array.isArray(ann.keypoints) && ann.keypoints.length > 0 && typeof ann.keypoints[0] === 'object') {
                    ann.keypoints.forEach(kp => {
                        keypoints.push({
                            x: kp.x * this.canvas.width,      // 归一化x坐标转为画布坐标
                            y: kp.y * this.canvas.height,     // 归一化y坐标转为画布坐标
                            v: kp.v || 2                      // 可见性
                        });
                    });
                } else {
                    // 如果是数值数组格式 [x1, y1, v1, x2, y2, v2, ...]（向后兼容）
                    for (let i = 0; i < ann.keypoints.length; i += 3) {
                        if (i + 2 < ann.keypoints.length) {
                            keypoints.push({
                                x: ann.keypoints[i] * this.canvas.width,      // 归一化x坐标转为画布坐标
                                y: ann.keypoints[i + 1] * this.canvas.height, // 归一化y坐标转为画布坐标
                                v: ann.keypoints[i + 2] || 2                  // 可见性
                            });
                        }
                    }
                }
                
                // 计算矩形框坐标（从中心点和宽高转换为左上角坐标和宽高）
                const x = ann.x_center * this.canvas.width - (ann.width * this.canvas.width) / 2;
                const y = ann.y_center * this.canvas.height - (ann.height * this.canvas.height) / 2;
                const width = ann.width * this.canvas.width;
                const height = ann.height * this.canvas.height;
                
                return {
                    class_id: ann.class_id,
                    x: x,
                    y: y,
                    width: width,
                    height: height,
                    keypoints: keypoints
                };
            }
            // 检查是否为旋转框标注
            else if (ann.angle !== undefined) {
                // 旋转框格式: class_id x_center y_center width height angle
                console.log('处理旋转框标注:', ann);
                return {
                    class_id: ann.class_id,
                    x: ann.x_center * this.canvas.width - (ann.width * this.canvas.width) / 2,
                    y: ann.y_center * this.canvas.height - (ann.height * this.canvas.height) / 2,
                    width: ann.width * this.canvas.width,
                    height: ann.height * this.canvas.height,
                    angle: ann.angle
                };
            }
            // 默认边界框标注
            else {
                return {
                    class_id: ann.class_id,
                    x: ann.x_center * this.canvas.width - (ann.width * this.canvas.width) / 2,
                    y: ann.y_center * this.canvas.height - (ann.height * this.canvas.height) / 2,
                    width: ann.width * this.canvas.width,
                    height: ann.height * this.canvas.height
                };
            }
        });
        
        console.log('处理后的标注数据:', this.annotations);
        
        // 清除选中状态
        this.selectedAnnotation = null;
        this.updateAnnotationList();
    }
    
    async saveAnnotation() {
        // 实现防抖机制，防止频繁保存
        if (this.debounceTimer) {
            // 如果已经有保存请求在等待，取消之前的请求
            clearTimeout(this.debounceTimer);
            this.pendingSave = true; // 标记有新的保存需求
            this.debounceTimer = setTimeout(async () => {
                await this.performSave();
                this.pendingSave = false;
            }, 500); // 500ms延迟
            return;
        }
        
        // 如果没有等待的请求，立即执行保存
        await this.performSave();
        
        // 设置定时器，如果在此期间又有新的保存请求，则等待
        this.debounceTimer = setTimeout(() => {
            this.debounceTimer = null;
            if (this.pendingSave) {
                this.saveAnnotation();
            }
        }, 500);
    }
    
    async performSave() {
        if (!this.currentImageData) return;
        
        console.log('开始保存标注，当前工具:', this.currentTool);
        console.log('当前标注数量:', this.annotations.length);
        console.log('标注内容:', this.annotations);
        
        // 转换为YOLO格式（相对于画布尺寸）
        const yoloAnnotations = this.annotations.map(ann => {
            // 检查是否为分割标注
            if (ann.points) {
                // 实例分割格式: class_id x1 y1 x2 y2 ...
                // 检查点坐标是否已经是归一化坐标（值在0-1范围内）
                let isNormalized = true;
                if (ann.points.length > 0) {
                    if (Array.isArray(ann.points[0])) {
                        // 如果是二维数组格式 [[x1, y1], [x2, y2], ...]
                        for (let i = 0; i < ann.points.length; i++) {
                            if (ann.points[i][0] > 1 || ann.points[i][1] > 1 || ann.points[i][0] < 0 || ann.points[i][1] < 0) {
                                isNormalized = false;
                                break;
                            }
                        }
                    } else {
                        // 如果是一维数组格式 [x1, y1, x2, y2, ...]
                        for (let i = 0; i < ann.points.length; i += 2) {
                            if (ann.points[i] > 1 || ann.points[i+1] > 1 || ann.points[i] < 0 || ann.points[i+1] < 0) {
                                isNormalized = false;
                                break;
                            }
                        }
                    }
                }
                
                let points = [];
                if (ann.points.length > 0) {
                    if (Array.isArray(ann.points[0])) {
                        // 如果是二维数组格式 [[x1, y1], [x2, y2], ...]
                        if (isNormalized) {
                            // 如果已经是归一化坐标，直接使用
                            ann.points.forEach(point => {
                                points.push(point[0]);
                                points.push(point[1]);
                            });
                        } else {
                            // 如果不是归一化坐标，转换为归一化坐标
                            ann.points.forEach(point => {
                                points.push(point[0] / this.canvas.width);
                                points.push(point[1] / this.canvas.height);
                            });
                        }
                    } else {
                        // 如果是一维数组格式 [x1, y1, x2, y2, ...]
                        if (isNormalized) {
                            // 如果已经是归一化坐标，直接使用
                            for (let i = 0; i < ann.points.length; i += 2) {
                                points.push(ann.points[i]);
                                points.push(ann.points[i+1]);
                            }
                        } else {
                            // 如果不是归一化坐标，转换为归一化坐标
                            for (let i = 0; i < ann.points.length; i += 2) {
                                points.push(ann.points[i] / this.canvas.width);
                                points.push(ann.points[i+1] / this.canvas.height);
                            }
                        }
                    }
                }
                
                // 计算中心点和宽高（相对于画布尺寸）
                let minX = 1, maxX = 0, minY = 1, maxY = 0;
                if (points.length > 0) {
                    minX = points[0];
                    maxX = points[0];
                    minY = points[1];
                    maxY = points[1];
                    
                    for (let i = 0; i < points.length; i += 2) {
                        minX = Math.min(minX, points[i]);
                        maxX = Math.max(maxX, points[i]);
                        minY = Math.min(minY, points[i + 1]);
                        maxY = Math.max(maxY, points[i + 1]);
                    }
                }
                
                // 确保边界框有有效值
                if (minX >= maxX) {
                    maxX = minX + 0.001; // 避免除零错误
                }
                if (minY >= maxY) {
                    maxY = minY + 0.001; // 避免除零错误
                }
                
                // 确保边界框有有效值
                if (minX >= maxX) {
                    maxX = minX + 0.001; // 避免除零错误
                }
                if (minY >= maxY) {
                    maxY = minY + 0.001; // 避免除零错误
                }
                
                // 确保所有值都是有效数字
                minX = isNaN(minX) ? 0 : minX;
                minY = isNaN(minY) ? 0 : minY;
                maxX = isNaN(maxX) ? 0.001 : maxX;
                maxY = isNaN(maxY) ? 0.001 : maxY;
                
                const xCenter = (minX + maxX) / 2;
                const yCenter = (minY + maxY) / 2;
                const width = maxX - minX;
                const height = maxY - minY;
                
                return {
                    class_id: ann.class_id,
                    x_center: parseFloat(isNaN(xCenter) ? 0.5 : xCenter.toFixed(6)),
                    y_center: parseFloat(isNaN(yCenter) ? 0.5 : yCenter.toFixed(6)),
                    width: parseFloat(isNaN(width) ? 0.001 : width.toFixed(6)),
                    height: parseFloat(isNaN(height) ? 0.001 : height.toFixed(6)),
                    points: points.map(p => parseFloat(isNaN(p) ? 0 : p.toFixed(6)))
                };
            }
            // 检查是否为关键点标注
            else if (ann.keypoints) {
                // 关键点格式: class_id x_center y_center width height x1 y1 v1 x2 y2 v2 ...
                const keypointsData = [];
                
                // ann.keypoints 是画布坐标的关键点数组，需要转换为归一化坐标
                // 检查关键点数据格式，如果已经是对象数组格式
                if (Array.isArray(ann.keypoints) && ann.keypoints.length > 0 && typeof ann.keypoints[0] === 'object') {
                    // 如果是对象数组格式 [{x: canvas_x, y: canvas_y, v: visibility}, ...]
                    ann.keypoints.forEach(kp => {
                        keypointsData.push({
                            x: parseFloat((kp.x / this.canvas.width).toFixed(6)),
                            y: parseFloat((kp.y / this.canvas.height).toFixed(6)),
                            v: kp.v || 2
                        });
                    });
                } else {
                    // 如果是数值数组格式 [x1, y1, v1, x2, y2, v2, ...]（这种情况应该不会出现）
                    for (let i = 0; i < ann.keypoints.length; i += 3) {
                        if (i + 2 < ann.keypoints.length) {
                            // 将画布坐标转换为归一化坐标
                            keypointsData.push(parseFloat((ann.keypoints[i] / this.canvas.width).toFixed(6)));
                            keypointsData.push(parseFloat((ann.keypoints[i + 1] / this.canvas.height).toFixed(6)));
                            keypointsData.push(parseInt(ann.keypoints[i + 2]) || 2);
                        }
                    }
                }
                
                // 将画布坐标转换为归一化坐标
                const x_center = (ann.x + ann.width / 2) / this.canvas.width;
                const y_center = (ann.y + ann.height / 2) / this.canvas.height;
                const width = ann.width / this.canvas.width;
                const height = ann.height / this.canvas.height;
                
                return {
                    class_id: ann.class_id,
                    x_center: parseFloat(x_center.toFixed(6)),
                    y_center: parseFloat(y_center.toFixed(6)),
                    width: parseFloat(width.toFixed(6)),
                    height: parseFloat(height.toFixed(6)),
                    keypoints: keypointsData // 发送对象数组格式
                };
            }
            // 检查是否为旋转框标注
            else if (ann.angle !== undefined) {
                // 旋转框格式: class_id x_center y_center width height angle
                return {
                    class_id: ann.class_id,
                    x_center: parseFloat(((ann.x + ann.width / 2) / this.canvas.width).toFixed(6)),
                    y_center: parseFloat(((ann.y + ann.height / 2) / this.canvas.height).toFixed(6)),
                    width: parseFloat((ann.width / this.canvas.width).toFixed(6)),
                    height: parseFloat((ann.height / this.canvas.height).toFixed(6)),
                    angle: parseFloat(ann.angle.toFixed(6))
                };
            }
            // 检查是否为关键点工具创建的矩形框标注（具有x, y, width, height但没有keypoints）
            else if (ann.x !== undefined && ann.y !== undefined && 
                     ann.width !== undefined && ann.height !== undefined && !ann.keypoints) {
                // 这是关键点工具创建的矩形框，其坐标是画布坐标，需要转换为归一化坐标
                const x_center = (ann.x + ann.width / 2) / this.canvas.width;
                const y_center = (ann.y + ann.height / 2) / this.canvas.height;
                const width = ann.width / this.canvas.width;
                const height = ann.height / this.canvas.height;
                
                return {
                    class_id: ann.class_id,
                    x_center: parseFloat(x_center.toFixed(6)),
                    y_center: parseFloat(y_center.toFixed(6)),
                    width: parseFloat(width.toFixed(6)),
                    height: parseFloat(height.toFixed(6))
                };
            }
            // 默认边界框标注
            else {
                return {
                    class_id: ann.class_id,
                    x_center: parseFloat(((ann.x + ann.width / 2) / this.canvas.width).toFixed(6)),
                    y_center: parseFloat(((ann.y + ann.height / 2) / this.canvas.height).toFixed(6)),
                    width: parseFloat((ann.width / this.canvas.width).toFixed(6)),
                    height: parseFloat((ann.height / this.canvas.height).toFixed(6))
                };
            }
        });
        
        console.log('转换后的YOLO格式标注:', yoloAnnotations);
        
        try {
            const response = await fetch(`/api/annotation/images/${this.currentImageData.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    annotations: yoloAnnotations
                })
            });
            
            if (response.ok) {
                this.currentImageData.annotations = yoloAnnotations;
                this.updateImageList();
                this.showMessage('标注保存成功', 'success');
                console.log('标注保存成功');
            } else {
                this.showMessage('保存失败', 'error');
                console.error('保存失败，服务器响应:', response.status, response.statusText);
            }
            
        } catch (error) {
            console.error('保存标注失败:', error);
            this.showMessage('保存失败', 'error');
        }
    }
    
    updateAnnotationList() {
        const annotationList = document.getElementById('annotation-list');
        annotationList.innerHTML = '';
        
        this.annotations.forEach((ann, index) => {
            const className = this.projectData.classes[ann.class_id] || '未知类别';
            const annItem = document.createElement('div');
            annItem.className = `annotation-list-item ${this.selectedAnnotation === ann ? 'selected' : ''}`;
            
            // 根据标注类型显示不同的信息
            let positionInfo = '';
            let sizeInfo = '';
            let keypointsInfo = '';
            
            if (ann.points) {
                // 实例分割标注
                positionInfo = '<div><strong>类型:</strong> 实例分割</div>';
            } else if (ann.keypoints) {
                // 关键点标注
                positionInfo = '<div><strong>类型:</strong> 关键点</div>';
                
                // 生成关键点信息
                if (ann.keypoints && ann.keypoints.length > 0) {
                    keypointsInfo = '<div class="keypoints-list"><strong>关键点:</strong><div class="keypoints-container">';
                    
                    // 获取当前类别的关键点配置
                    let classKeypointConfig = null;
                    if (this.projectData.class_keypoints) {
                        classKeypointConfig = this.projectData.class_keypoints.find(config => config.class_name === className);
                    }
                    
                    ann.keypoints.forEach((kp, kpIndex) => {
                        const visibilityText = kp.v === 0 ? '不存在' : (kp.v === 1 ? '可见' : '遮挡');
                        const visibilityClass = kp.v === 0 ? 'visibility-hidden' : (kp.v === 1 ? 'visibility-visible' : 'visibility-occluded');
                        
                        // 获取关键点标签（如果有的话）
                        let keypointLabel = (kpIndex + 1).toString();
                        if (classKeypointConfig && classKeypointConfig.keypoints && kpIndex < classKeypointConfig.keypoints.length) {
                            keypointLabel = classKeypointConfig.keypoints[kpIndex] || keypointLabel;
                        }
                        
                        keypointsInfo += `
                            <div class="keypoint-item">
                                <span class="keypoint-label">${keypointLabel}</span>
                                <select class="keypoint-visibility" 
                                        data-ann-index="${index}" 
                                        data-kp-index="${kpIndex}" 
                                        onchange="annotationTool.updateKeypointVisibility(this, event)">
                                    <option value="0" ${kp.v === 0 ? 'selected' : ''}>不存在</option>
                                    <option value="1" ${kp.v === 1 ? 'selected' : ''}>可见</option>
                                    <option value="2" ${kp.v === 2 ? 'selected' : ''}>遮挡</option>
                                </select>
                                <span class="keypoint-visibility-text ${visibilityClass}">${visibilityText}</span>
                            </div>`;
                    });
                    keypointsInfo += '</div></div>';
                } else {
                    keypointsInfo = '<div class="keypoints-list"><strong>关键点:</strong> 无</div>';
                }
            } else {
                // 默认边界框标注
                if (ann.x !== undefined && ann.y !== undefined) {
                    positionInfo = `<div><strong>位置:</strong> (${Math.round(ann.x)}, ${Math.round(ann.y)})</div>`;
                }
                if (ann.width !== undefined && ann.height !== undefined) {
                    sizeInfo = `<div><strong>尺寸:</strong> ${Math.round(ann.width)} x ${Math.round(ann.height)}</div>`;
                }
            }
            
            annItem.innerHTML = `
                <div class="annotation-info">
                    <div><strong>ID:</strong> ${index + 1}</div>
                    <div><strong>类别:</strong> ${className}</div>
                    ${positionInfo}
                    ${sizeInfo}
                    ${keypointsInfo}
                </div>
                <div class="annotation-actions">
                    <button class="btn btn-sm btn-outline-danger" onclick="annotationTool.removeAnnotation(${index})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            
            // 方式3：点击标注列表项选中对应的标注框
            annItem.addEventListener('click', (e) => {
                // 防止点击删除按钮或关键点可见性选择框时触发选中
                if (!e.target.closest('.annotation-actions') && !e.target.closest('.keypoint-visibility')) {
                    this.selectedAnnotation = ann;
                    this.updateAnnotationList();
                    this.redraw();
                }
            });
            
            annotationList.appendChild(annItem);
        });
    }
    
    // 更新关键点可见性
    updateKeypointVisibility(selectElement, event) {
        // 阻止事件冒泡，防止触发列表项的点击事件
        if (event) {
            event.stopPropagation();
        }
        
        const annIndex = parseInt(selectElement.dataset.annIndex);
        const kpIndex = parseInt(selectElement.dataset.kpIndex);
        const newVisibility = parseInt(selectElement.value);
        
        if (annIndex >= 0 && annIndex < this.annotations.length) {
            const annotation = this.annotations[annIndex];
            if (annotation.keypoints && kpIndex >= 0 && kpIndex < annotation.keypoints.length) {
                annotation.keypoints[kpIndex].v = newVisibility;
                
                // 更新可见性文本显示
                const visibilityTextElement = selectElement.nextElementSibling;
                if (visibilityTextElement) {
                    const visibilityText = newVisibility === 0 ? '不存在' : (newVisibility === 1 ? '可见' : '遮挡');
                    const visibilityClass = newVisibility === 0 ? 'visibility-hidden' : (newVisibility === 1 ? 'visibility-visible' : 'visibility-occluded');
                    
                    visibilityTextElement.textContent = visibilityText;
                    visibilityTextElement.className = `keypoint-visibility-text ${visibilityClass}`;
                }
                
                // 重新绘制画布
                this.redraw();
                
                // 保存标注
                this.saveAnnotation();
            }
        }
    }
    
    // 重新设计：优化缩放功能，确保标注框位置稳定
    zoom(factor) {
        // 获取鼠标在画布上的位置
        const mouseX = this.mouseX || (this.canvas.width / 2);
        const mouseY = this.mouseY || (this.canvas.height / 2);
        
        // 计算鼠标位置相对于画布的坐标（考虑当前缩放和偏移）
        const canvasX = (mouseX - this.offsetX) / this.scale;
        const canvasY = (mouseY - this.offsetY) / this.scale;
        
        // 更新缩放比例
        const oldScale = this.scale;
        this.scale *= factor;
        
        // 限制缩放范围
        this.scale = Math.max(0.1, Math.min(this.scale, 5));
        
        // 计算新的偏移量，保持鼠标位置不变
        this.offsetX = mouseX - canvasX * this.scale;
        this.offsetY = mouseY - canvasY * this.scale;
        
        // 确保偏移量不会超出画布边界
        this.constrainOffset();
        
        // 重新绘制
        this.redraw();
    }
    
    resetZoom() {
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.redraw();
    }
    
    constrainOffset() {
        const maxOffsetX = Math.max(0, (this.canvas.width * this.scale - this.canvas.width) / 2);
        const maxOffsetY = Math.max(0, (this.canvas.height * this.scale - this.canvas.height) / 2);
        
        this.offsetX = Math.max(-maxOffsetX, Math.min(maxOffsetX, this.offsetX));
        this.offsetY = Math.max(-maxOffsetY, Math.min(maxOffsetY, this.offsetY));
    }
    
    startDrawing(e) {
        console.log('开始绘制，当前工具:', this.currentTool);
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.getCanvasCoordinates(e);
        
        // 如果是SAM3工具，交由SAM3工具处理
        if (this.currentTool === 'sam3' && this.sam3Tool && this.sam3Tool.isActive) {
            this.sam3Tool.onMouseDown(e);
            return;
        }
        
        // 如果准备好进行抓手模式，开始拖拽
        if (this.isPanReady) {
            this.isPanning = true;
            this.panStartX = this.mouseX;
            this.panStartY = this.mouseY;
            this.canvas.style.cursor = 'grabbing';
            return;
        }
        
        // 防止重复触发 - 但允许添加新点
        if (this.currentTool === 'segment' && this.segmentationTool.isDrawing) {
            console.log('实例分割工具已在绘制中，添加新点');
            // 仅在鼠标点击时添加点，而不是在移动时
            this.segmentationTool.startDrawing(e);
            return;
        }
        
        // 根据当前工具类型处理绘制
        // 对于实例分割、旋转框和关键点工具，也需要支持Ctrl+点击选中已有标注
        if (this.currentTool === 'segment' || this.currentTool === 'obb' || this.currentTool === 'keypoints') {
            
            // 如果按下Ctrl键，检查是否点击了已有标注点或框，用于选中
            if (e.ctrlKey) {
                if (this.currentTool === 'keypoints') {
                    // 检查是否点击了现有的关键点（优先选择关键点）
                    const clickedKeypoint = this.keypointsTool.getKeypointAtPosition(canvasX, canvasY);
                    if (clickedKeypoint) {
                        // 选中关键点所在的标注
                        this.selectedAnnotation = this.keypointsTool.annotationTool.selectedAnnotation;
                        this.updateAnnotationList();
                        this.redraw();
                        return;
                    }
                    
                    // 检查是否点击了现有关键点标注的矩形框
                    const clickedBox = this.keypointsTool.getBoxOnlyAtPosition(canvasX, canvasY);
                    if (clickedBox) {
                        this.selectedAnnotation = clickedBox;
                        this.updateAnnotationList();
                        this.redraw();
                        return;
                    }
                } else if (this.currentTool === 'segment') {
                    // 检查是否点击了分割标注的边界框
                    const clickedSeg = this.segmentationTool.getSegmentAtPosition(canvasX, canvasY);
                    if (clickedSeg) {
                        this.selectedAnnotation = clickedSeg;
                        this.updateAnnotationList();
                        this.redraw();
                        
                        // 检查是否点击了标注上的点
                        const clickedPointIndex = this.segmentationTool.isPointClicked(this.selectedAnnotation, canvasX, canvasY);
                        if (clickedPointIndex >= 0) {
                            // 如果点击了点，开始拖拽该点
                            this.segmentationTool.startDraggingPoint(clickedPointIndex);
                            this.redraw();
                            return;
                        } else {
                            // 如果没有点击点，而是点击了分割区域的其他部分，开始整体拖动
                            this.segmentationTool.startDraggingSegment(canvasX, canvasY);
                            this.redraw();
                            return;
                        }
                    }
                } else if (this.currentTool === 'obb') {
                    // 检查是否点击了旋转框标注
                    const clickedObb = this.obbTool.getObbAtPosition(canvasX, canvasY);
                    if (clickedObb) {
                        this.selectedAnnotation = clickedObb;
                        this.updateAnnotationList();
                        this.redraw();
                        return;
                    }
                }
                
                // 如果没有点击到特定元素，清除选中状态
                this.selectedAnnotation = null;
                this.updateAnnotationList();
                this.redraw();
                return;
            }
        }
        
        // 根据当前工具类型处理绘制
        if (this.currentTool === 'segment') {
            // 实例分割工具的绘制逻辑
            this.segmentationTool.startDrawing(e);
        } else if (this.currentTool === 'obb' && !this.isDragging && !this.isResizing) {
            // 检查是否点击了现有旋转框
            const clickedObb = this.obbTool.getObbAtPosition(canvasX, canvasY);
            if (clickedObb) {
                // 检查是否点击了旋转控制点
                const rotationHandle = this.obbTool.isRotationHandleClicked(clickedObb, canvasX, canvasY);
                if (rotationHandle) {
                    this.obbTool.startRotation(clickedObb, canvasX, canvasY);
                    this.redraw();
                    return;
                } else {
                    // 检查是否点击了调整大小的控制点
                    const resizeHandle = this.getResizeHandle(clickedObb, canvasX, canvasY);
                    if (resizeHandle) {
                        this.selectedAnnotation = clickedObb;
                        this.isResizing = true;
                        this.resizeHandle = resizeHandle;
                        this.startX = canvasX;
                        this.startY = canvasY;
                        this.redraw();
                        return;
                    } else {
                        // 拖拽整个旋转框
                        this.selectedAnnotation = clickedObb;
                        this.isDragging = true;
                        this.dragStartX = canvasX;
                        this.dragStartY = canvasY;
                        this.redraw();
                        return;
                    }
                }
            }
            
            // 开始绘制新的旋转框
            this.obbTool.startDrawing(e);
        } else if (this.currentTool === 'keypoints') {
            // 关键点工具的绘制逻辑
            this.keypointsTool.startAnnotation(e);
        } else {
            // 检查是否点击了现有标注框
            let clickedAnnotation = null;
            // 从后往前遍历，优先选中上层的标注
            for (let i = this.annotations.length - 1; i >= 0; i--) {
                const ann = this.annotations[i];
                if (ann.x !== undefined && ann.y !== undefined && 
                    ann.width !== undefined && ann.height !== undefined &&
                    !ann.points && !ann.keypoints) { // 排除分割和关键点标注
                    
                    if (canvasX >= ann.x && canvasX <= ann.x + ann.width &&
                        canvasY >= ann.y && canvasY <= ann.y + ann.height) {
                        
                        // 检查是否点击了调整大小的控制点
                        const handle = this.getResizeHandle(ann, canvasX, canvasY);
                        if (handle) {
                            this.selectedAnnotation = ann;
                            this.isResizing = true;
                            this.resizeHandle = handle;
                            this.startX = canvasX;
                            this.startY = canvasY;
                            this.redraw();
                            return;
                        }
                        
                        // 选中标注框
                        clickedAnnotation = ann;
                        break;
                    }
                }
            }
            
            if (clickedAnnotation) {
                // 开始拖拽标注框
                this.selectedAnnotation = clickedAnnotation;
                this.isDragging = true;
                this.dragStartX = canvasX;
                this.dragStartY = canvasY;
            } else {
                // 开始绘制新的标注框
                this.isDrawing = true;
                this.startX = canvasX;
                this.startY = canvasY;
            }
        }
        
        this.updateAnnotationList();
        this.redraw();
    }
    
    stopDrawing(e) {
        console.log('停止绘制，当前工具:', this.currentTool);
        
        // 如果是SAM3工具，交由SAM3工具处理
        if (this.currentTool === 'sam3' && this.sam3Tool && this.sam3Tool.isActive) {
            this.sam3Tool.onMouseUp(e);
            return;
        }
        
        // 根据当前工具类型处理停止绘制
        if (this.currentTool === 'sam3' && this.sam3Tool && this.sam3Tool.isActive) {
            // 如果是SAM3工具，交由SAM3工具处理
            this.sam3Tool.onMouseUp(e);
            return;
        } else if (this.currentTool === 'segment') {
            // 如果正在拖拽点，则停止拖拽
            if (this.segmentationTool.isDraggingPoint) {
                console.log('完成实例分割点拖拽');
                this.segmentationTool.stopDraggingPoint();
                return;
            }
            // 如果正在整体拖动分割区域，则停止拖动
            else if (this.segmentationTool.isDraggingSegment) {
                console.log('完成实例分割整体拖动');
                this.segmentationTool.stopDraggingSegment();
                return;
            }
            // 如果正在绘制，则不在此处完成绘制
            else if (this.segmentationTool.isDrawing) {
                // 对于实例分割工具，我们不在鼠标抬起时完成绘制
                // 而是在双击或满足条件时完成绘制
                console.log('实例分割工具正在绘制中，不在此处完成');
                return;
            }
        } else if (this.currentTool === 'obb' && this.obbTool.isDrawing) {
            console.log('完成旋转框绘制');
            this.obbTool.finishDrawing();
            return;
        } else if (this.obbTool.isRotating) {
            console.log('完成旋转框旋转');
            this.obbTool.finishRotation();
            return;
        } else if (this.currentTool === 'obb' && this.selectedAnnotation && this.selectedAnnotation.hasOwnProperty('angle')) {
            // 对于旋转框，如果在stopDrawing时仍有选中状态，可能是旋转操作
            // 这里不需要额外处理，因为旋转已经在startDrawing中处理过了
            console.log('旋转框工具结束操作');
        } else if (this.currentTool === 'keypoints' && this.keypointsTool.isDraggingKeypoint) {
            console.log('完成关键点拖拽');
            this.keypointsTool.finishDragging();
            return;
        } else if (this.currentTool === 'keypoints' && this.keypointsTool.isDrawingBox) {
            console.log('完成关键点工具矩形框绘制');
            this.keypointsTool.finishBoxDrawing();
            return;
        } else if (this.currentTool === 'keypoints' && this.keypointsTool) {
            // 调用关键点工具的鼠标释放处理
            this.keypointsTool.onMouseUp(e);
        }
        
        if (this.isDrawing) {
            this.isDrawing = false;
            
            if (this.currentBox && this.currentBox.width > 5 && this.currentBox.height > 5) {
                this.annotations.push({
                    class_id: this.selectedClass,
                    ...this.currentBox
                });
                this.updateAnnotationList();
                this.saveAnnotation();
                this.selectedAnnotation = null;
                this.updateAnnotationList();
            } else {
                this.selectedAnnotation = null;
                this.updateAnnotationList();
            }
            
            this.currentBox = null;
            this.redraw();
        } else if (this.isDragging) {
            this.isDragging = false;
            this.saveAnnotation();
            this.justFinishedDragging = true;
        } else if (this.isResizing) {
            this.isResizing = false;
            this.resizeHandle = null;
            this.saveAnnotation();
            this.justFinishedResizing = true;
        } else if (this.isPanning) {
            this.isPanning = false;
            this.canvas.style.cursor = this.isPanReady ? 'grab' : 'crosshair';
        }
        
        this.selectedByClick = false;
    }
    
    getResizeHandle(annotation, x, y) {
        const handleSize = 8;
        const right = annotation.x + annotation.width;
        const bottom = annotation.y + annotation.height;
        
        // 四个角落控制点（优先级最高）
        // 左上角
        if (x >= annotation.x - handleSize && x <= annotation.x + handleSize &&
            y >= annotation.y - handleSize && y <= annotation.y + handleSize) {
            return 'top-left';
        }
        
        // 右上角
        if (x >= right - handleSize && x <= right + handleSize &&
            y >= annotation.y - handleSize && y <= annotation.y + handleSize) {
            return 'top-right';
        }
        
        // 左下角
        if (x >= annotation.x - handleSize && x <= annotation.x + handleSize &&
            y >= bottom - handleSize && y <= bottom + handleSize) {
            return 'bottom-left';
        }
        
        // 右下角
        if (x >= right - handleSize && x <= right + handleSize &&
            y >= bottom - handleSize && y <= bottom + handleSize) {
            return 'bottom-right';
        }
        
        // 四个边控制点
        // 右侧控制点
        if (x >= right - handleSize && x <= right + handleSize &&
            y >= annotation.y && y <= bottom) {
            return 'right';
        }
        
        // 底部控制点
        if (y >= bottom - handleSize && y <= bottom + handleSize &&
            x >= annotation.x && x <= right) {
            return 'bottom';
        }
        
        // 左侧控制点
        if (x >= annotation.x - handleSize && x <= annotation.x + handleSize &&
            y >= annotation.y && y <= bottom) {
            return 'left';
        }
        
        // 顶部控制点
        if (y >= annotation.y - handleSize && y <= annotation.y + handleSize &&
            x >= annotation.x && x <= right) {
            return 'top';
        }
        
        return null;
    }
    
    redraw() {
        if (!this.currentImage) return;
        
        // 保存当前上下文状态
        this.ctx.save();
        
        // 应用缩放和偏移
        this.ctx.setTransform(1, 0, 0, 1, 0, 0); // 重置变换
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.translate(this.offsetX, this.offsetY);
        this.ctx.scale(this.scale, this.scale);
        
        // 绘制图片
        this.ctx.drawImage(this.currentImage, 0, 0, this.canvas.width, this.canvas.height);
        
        // 绘制辅助线（跟随鼠标移动）
        if (this.showGuidelines) {
            this.drawGuidelines();
        }
        
        // 根据当前工具类型绘制标注
        if (this.currentTool === 'sam3' && this.sam3Tool && this.sam3Tool.isActive) {
            // SAM3工具的绘制
            // 首先绘制已有标注
            this.annotations.forEach((ann, index) => {
                const isSelected = this.selectedAnnotation === ann;
                // 对于分割标注，使用特殊的绘制方法
                if (ann.points) {
                    this.drawSegmentAnnotation(ann, this.getClassColor(ann.class_id), false, index + 1, isSelected);
                } else if (!ann.keypoints && ann.x !== undefined && ann.y !== undefined && ann.width !== undefined && ann.height !== undefined) {
                    // 对于普通矩形框标注，使用drawBox方法
                    this.drawBox(ann, this.getClassColor(ann.class_id), false, index + 1, isSelected);
                }
            });
            
            // 绘制关键点标注（确保在最上层）
            this.annotations.forEach((ann, index) => {
                const isSelected = this.selectedAnnotation === ann;
                if (ann.keypoints) {
                    // 对于关键点标注，使用关键点工具的绘制方法
                    this.keypointsTool.drawKeypoints(ann, this.getClassColor(ann.class_id), false, index + 1, isSelected);
                }
            });
            
            // 绘制当前正在绘制的框
            if (this.currentBox) {
                this.drawBox(this.currentBox, this.getClassColor(this.selectedClass), true);
            }
            
            // 绘制SAM3相关的元素
            this.sam3Tool.drawSAM3Elements();
        } else if (this.currentTool === 'segment') {
            this.segmentationTool.redraw();
        } else if (this.currentTool === 'obb') {
            this.obbTool.redraw();
        } else if (this.currentTool === 'keypoints') {
            this.keypointsTool.redraw();
        } else {
            // 绘制已有标注
            // 首先绘制非关键点标注（矩形框、分割等）
            this.annotations.forEach((ann, index) => {
                const isSelected = this.selectedAnnotation === ann;
                // 对于分割标注，使用特殊的绘制方法
                if (ann.points) {
                    this.drawSegmentAnnotation(ann, this.getClassColor(ann.class_id), false, index + 1, isSelected);
                } else if (!ann.keypoints && ann.x !== undefined && ann.y !== undefined && ann.width !== undefined && ann.height !== undefined) {
                    // 对于普通矩形框标注，使用drawBox方法
                    this.drawBox(ann, this.getClassColor(ann.class_id), false, index + 1, isSelected);
                }
            });
            
            // 然后绘制关键点标注（确保在最上层）
            this.annotations.forEach((ann, index) => {
                const isSelected = this.selectedAnnotation === ann;
                if (ann.keypoints) {
                    // 对于关键点标注，使用关键点工具的绘制方法
                    this.keypointsTool.drawKeypoints(ann, this.getClassColor(ann.class_id), false, index + 1, isSelected);
                }
            });
            
            // 绘制当前正在绘制的框
            if (this.currentBox) {
                this.drawBox(this.currentBox, this.getClassColor(this.selectedClass), true);
            }
        }
        
        // 恢复上下文状态
        this.ctx.restore();
    }
    
    drawGuidelines() {
        this.ctx.save();
        this.ctx.strokeStyle = this.guidelineColor; // 使用自定义颜色
        this.ctx.lineWidth = 1;
        this.ctx.setLineDash([5, 5]);
        
        // 绘制鼠标位置的垂直线
        if (this.mouseX !== undefined && this.mouseY !== undefined) {
            // 转换鼠标坐标到画布坐标（考虑缩放和偏移）
            const canvasX = (this.mouseX - this.offsetX) / this.scale;
            const canvasY = (this.mouseY - this.offsetY) / this.scale;
            
            // 垂直线（从顶部到底部）
            this.ctx.beginPath();
            this.ctx.moveTo(canvasX, 0);
            this.ctx.lineTo(canvasX, this.canvas.height);
            this.ctx.stroke();
            
            // 水平线（从左侧到右侧）
            this.ctx.beginPath();
            this.ctx.moveTo(0, canvasY);
            this.ctx.lineTo(this.canvas.width, canvasY);
            this.ctx.stroke();
            
            // 显示鼠标坐标
            this.ctx.fillStyle = this.guidelineColor; // 使用自定义颜色
            this.ctx.font = '12px Arial';
            this.ctx.fillText(`(${Math.round(canvasX)}, ${Math.round(canvasY)})`, canvasX + 5, canvasY - 5);
        }
        
        this.ctx.restore();
    }
    
    drawBox(box, color, isDrawing = false, index = null, isSelected = false) {
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
        
        this.ctx.strokeStyle = borderColor;
        this.ctx.lineWidth = isSelected ? 3 : (isDrawing ? 3 : 2);
        
        // 不填充矩形内部（保持透明）
        // 只绘制边框
        this.ctx.strokeRect(box.x, box.y, box.width, box.height);
        
        // 绘制序号和类别标签
        if (!isDrawing) {
            const className = this.projectData.classes[box.class_id] || '未知';
            let label = className;
            if (index !== null) {
                label = `${index}. ${className}`;
            }
            
            // 标签背景使用半透明颜色
            if (isSelected) {
                this.ctx.fillStyle = 'rgba(68, 255, 68, 0.7)'; // 半透明绿色
            } else {
                // 将颜色转换为半透明格式
                if (color.startsWith('#')) {
                    const r = parseInt(color.substr(1, 2), 16);
                    const g = parseInt(color.substr(3, 2), 16);
                    const b = parseInt(color.substr(5, 2), 16);
                    this.ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.7)`;
                } else {
                    // 如果不是十六进制颜色，使用默认半透明白色背景
                    this.ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                }
            }
            this.ctx.fillRect(box.x, box.y - 20, this.ctx.measureText(label).width + 10, 20);
            this.ctx.fillStyle = 'white';
            this.ctx.font = '12px Arial';
            this.ctx.fillText(label, box.x + 5, box.y - 5);
        }
        
        // 如果是选中的标注框，绘制控制点
        if (isSelected && !isDrawing) {
            this.drawResizeHandles(box);
        }
    }
    
    // 绘制分割标注
    drawSegmentAnnotation(segment, color, isDrawing = false, index = null, isSelected = false) {
        if (!segment.points || segment.points.length < 3) return;
        
        this.ctx.save();
        
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
        this.ctx.fillStyle = borderColor;
        this.ctx.beginPath();
        this.ctx.moveTo(segment.points[0][0], segment.points[0][1]);
        for (let i = 1; i < segment.points.length; i++) {
            this.ctx.lineTo(segment.points[i][0], segment.points[i][1]);
        }
        this.ctx.closePath();
        this.ctx.fill();
        
        // 绘制边框
        this.ctx.strokeStyle = isSelected ? 'rgba(68, 255, 68, 0.7)' : '#FFFFFF';
        this.ctx.lineWidth = isSelected ? 3 : 2;
        this.ctx.stroke();
        
        // 绘制点
        segment.points.forEach((point, i) => {
            this.ctx.fillStyle = isSelected ? 'rgba(68, 255, 68, 0.7)' : '#FFFFFF';
            this.ctx.beginPath();
            this.ctx.arc(point[0], point[1], 4, 0, Math.PI * 2);
            this.ctx.fill();
            
            // 绘制序号
            if (!isDrawing) {
                this.ctx.fillStyle = '#FFFFFF';
                this.ctx.font = '12px Arial';
                this.ctx.fillText(i + 1, point[0] + 5, point[1] - 5);
            }
        });
        
        // 绘制序号和类别标签
        if (!isDrawing) {
            const className = this.projectData.classes[segment.class_id] || '未知';
            let label = className;
            if (index !== null) {
                label = `${index}. ${className}`;
            }
            
            // 标签背景使用半透明颜色
            if (isSelected) {
                this.ctx.fillStyle = 'rgba(68, 255, 68, 0.7)'; // 半透明绿色
            } else {
                // 将颜色转换为半透明格式
                if (color.startsWith('#')) {
                    const r = parseInt(color.substr(1, 2), 16);
                    const g = parseInt(color.substr(3, 2), 16);
                    const b = parseInt(color.substr(5, 2), 16);
                    this.ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.7)`;
                } else {
                    // 如果不是十六进制颜色，使用默认半透明白色背景
                    this.ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                }
            }
            
            const textWidth = this.ctx.measureText(label).width;
            const textX = segment.points[0][0];
            const textY = segment.points[0][1] - 25;
            
            this.ctx.fillRect(textX, textY - 15, textWidth + 10, 20);
            this.ctx.fillStyle = 'black';
            this.ctx.font = '12px Arial';
            this.ctx.fillText(label, textX + 5, textY);
        }
        
        this.ctx.restore();
    }
    
    drawResizeHandles(box) {
        const handleSize = 6;
        const right = box.x + box.width;
        const bottom = box.y + box.height;
        
        this.ctx.fillStyle = '#44FF44';
        
        // 右侧控制点
        this.ctx.fillRect(right - handleSize/2, box.y + box.height/2 - handleSize/2, handleSize, handleSize);
        
        // 底部控制点
        this.ctx.fillRect(box.x + box.width/2 - handleSize/2, bottom - handleSize/2, handleSize, handleSize);
        
        // 左侧控制点
        this.ctx.fillRect(box.x - handleSize/2, box.y + box.height/2 - handleSize/2, handleSize, handleSize);
        
        // 顶部控制点
        this.ctx.fillRect(box.x + box.width/2 - handleSize/2, box.y - handleSize/2, handleSize, handleSize);
    }
    
    getClassColor(classId) {
        const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff', '#ffa500', '#800080'];
        return colors[classId % colors.length];
    }
    
    removeAnnotation(index) {
        // 根据当前工具类型处理删除操作
        if (this.currentTool === 'segment') {
            this.segmentationTool.removeSegment(index);
            return;
        } else if (this.currentTool === 'obb') {
            this.obbTool.removeOBB(index);
            return;
        } else if (this.currentTool === 'keypoints') {
            this.keypointsTool.removeKeypoints(index);
            return;
        }
        
        this.annotations.splice(index, 1);
        this.updateAnnotationList();
        this.redraw();
        // 实时保存
        this.saveAnnotation();
    }
    
    clearAllAnnotations() {
        if (confirm('确定要清除所有标注吗？')) {
            this.annotations = [];
            this.updateAnnotationList();
            this.redraw();
            // 实时保存
            this.saveAnnotation();
        }
    }
    
    async markCompleted() {
        if (!this.currentImageData) return;
        
        try {
            const response = await fetch(`/api/annotation/images/${this.currentImageData.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    is_completed: true
                })
            });
            
            if (response.ok) {
                this.currentImageData.is_completed = true;
                // 同步更新imageList中的状态
                if (this.imageList && this.imageList[this.currentImageIndex]) {
                    this.imageList[this.currentImageIndex].is_completed = true;
                }
                this.updateImageList();
                this.showMessage('标记完成成功', 'success');
                await this.loadProjectStats();
            }
            
        } catch (error) {
            console.error('标记完成失败:', error);
        }
    }
    
    async markAllCompleted() {
        // 统计有标注和无标注的图片数量
        const annotatedCount = this.imageList.filter(img => img.annotations && img.annotations.length > 0).length;
        const unannotatedCount = this.imageList.filter(img => !img.annotations || img.annotations.length === 0).length;
        
        const message = `将标记所有 ${this.imageList.length} 张图片为已完成：\n\n` +
                       `有标注的图片：${annotatedCount} 张\n` +
                       `无标注的图片：${unannotatedCount} 张\n\n` +
                       `确定要继续吗？`;
        
        if (!confirm(message)) return;
        
        try {
            const response = await fetch(`/api/annotation/projects/${this.projectId}/mark-all-completed`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                // 更新本地数据
                this.imageList.forEach(img => {
                    img.is_completed = true;
                });
                this.updateImageList();
                await this.loadProjectStats();
                this.showMessage('所有图片已标记为完成', 'success');
            } else {
                this.showMessage('标记失败', 'error');
            }
            
        } catch (error) {
            console.error('一键标记完成失败:', error);
            this.showMessage('标记失败: ' + error.message, 'error');
        }
    }
    
    async loadProjectStats() {
        try {
            const response = await fetch(`/api/annotation/projects/${this.projectId}/stats`);
            const stats = await response.json();
            
            document.getElementById('progress-text').textContent = `${stats.completed_images}/${stats.total_images}`;
            document.getElementById('progress-bar').style.width = `${stats.progress_percentage}%`;
            
        } catch (error) {
            console.error('加载统计信息失败:', error);
        }
    }
    
    prevImage() {
        if (this.currentImageIndex > 0) {
            this.loadImage(this.currentImageIndex - 1);
        }
    }
    
    nextImage() {
        if (this.currentImageIndex < this.imageList.length - 1) {
            this.loadImage(this.currentImageIndex + 1);
        }
    }
    

    
    // 处理按键按下事件（整合所有键盘快捷键）
    handleKeyDown(e) {
        // 防止在输入框中触发快捷键
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        // 空格键作为抓手工具准备状态
        if (e.key === ' ') {
            e.preventDefault();
            this.isPanReady = true;
            this.canvas.style.cursor = 'grab';
            return;
        }
        
        // 阻止空格键滚动页面
        if (e.key === ' ') {
            e.preventDefault();
        }
        
        const key = e.key.toLowerCase();
        
        // 根据当前工具类型处理特定按键
        if (this.currentTool === 'sam3' && this.sam3Tool && this.sam3Tool.isActive) {
            // 对于切换图片和类别的快捷键，即使在SAM3激活状态下也要处理
            const navigationKeys = ['a', 'd', 'arrowleft', 'arrowright', 'w', 's'];
            const classSelectionKeys = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];
            
            if (navigationKeys.includes(key) || classSelectionKeys.some(num => num === e.key)) {
                // 让基础快捷键正常工作
            } else {
                // 其他快捷键交给SAM3工具处理
                this.sam3Tool.handleKeyDown(e);
                return;
            }
        } else if (this.currentTool === 'segment' && key === 'enter') {
            e.preventDefault();
            this.segmentationTool.finishDrawing();
            return;
        } else if (this.currentTool === 'segment' && key === 'escape') {
            e.preventDefault();
            this.segmentationTool.cancelDrawing();
            return;
        } else if (this.currentTool === 'obb') {
            if (key === 'q') {
                e.preventDefault();
                this.obbTool.adjustRotation(-0.0872665); // 左转5度（弧度）
                return;
            } else if (key === 'e') {
                e.preventDefault();
                this.obbTool.adjustRotation(0.0872665); // 右转5度（弧度）
                return;
            }
        } else if (this.currentTool === 'keypoints' && (key === 'delete' || key === 'backspace')) {
            e.preventDefault();
            // 如果有选中的关键点，则删除该关键点
            if (this.keypointsTool.selectedKeypoint) {
                this.keypointsTool.deleteSelectedKeypoint();
            } else {
                // 如果没有选中的关键点，但有选中的标注，则删除整个标注
                this.deleteSelectedAnnotation();
            }
            return;
        }
        
        // 如果是实例分割项目且SAM3已启用，处理Q键切换
        const sam3Switch = document.getElementById('enable-sam3-switch');
        if (this.projectData && this.projectData.project_type === 'segmentation' && 
            sam3Switch && sam3Switch.checked) {
            if (key === 'q') {
                e.preventDefault();
                // 切换到SAM3分割模式
                if (this.currentTool !== 'sam3') {
                    if (this.sam3Tool) {
                        this.setTool('sam3');
                    }
                } else {
                    // 如果当前已经是SAM3模式，切换回segment模式
                    this.setTool('segment');
                }
                return;
            }
        }
        
        // 处理Q和E键的快捷键（用于关键点工具模式切换）
        if (this.currentTool === 'keypoints') {
            if (key === 'q') {
                e.preventDefault();
                // 切换到矩形框模式
                this.keypointsTool.setMode('box');
                this.updateKeypointsModeButtons();
                return;
            } else if (key === 'e') {
                e.preventDefault();
                // 切换到关键点模式
                this.keypointsTool.setMode('keypoints');
                this.updateKeypointsModeButtons();
                return;
            } else if (key === 'v') {
                e.preventDefault();
                // 切换选中关键点的可见性
                if (this.keypointsTool.selectedKeypoint) {
                    this.keypointsTool.toggleKeypointVisibility();
                }
                return;
            }
        }
        
        switch(key) {
            case 'a':
            case 'arrowleft':
                e.preventDefault();
                this.prevImage();
                break;
            case 'd':
            case 'arrowright':
                e.preventDefault();
                this.nextImage();
                break;
            case 'w':
                e.preventDefault();
                this.prevClass();
                break;
            case 's':
                if (e.ctrlKey) {
                    e.preventDefault();
                    this.saveAnnotation();
                } else {
                    e.preventDefault();
                    this.nextClass();
                }
                break;
            case 'delete':
            case 'backspace':
                e.preventDefault();
                // 避免重复处理删除操作，因为关键点工具的删除已在上面处理
                // 如果不是关键点工具或没有选中的关键点，才执行通用删除
                if (this.currentTool !== 'keypoints' || !this.keypointsTool.selectedKeypoint) {
                    this.deleteSelectedAnnotation();
                }
                break;
            case 'g':
                e.preventDefault();
                this.toggleGuidelines();
                break;
            case '+':
            case '=':
                e.preventDefault();
                this.zoom(1.2);
                break;
            case '-':
                e.preventDefault();
                this.zoom(0.8);
                break;
            case '0':
                e.preventDefault();
                this.resetZoom();
                break;
        }
        
        // 数字键选择类别（1-9对应类别0-8）
        const num = parseInt(e.key);
        if (!isNaN(num) && num >= 1 && num <= this.projectData.classes.length && num <= 9) {
            e.preventDefault();
            const classIndex = num - 1;
            this.selectClass(classIndex, this.projectData.classes[classIndex]);
        }
    }
    
    handleKeyUp(e) {
        if (e.key === ' ') {
            this.isPanReady = false;
            this.isPanning = false;
            this.canvas.style.cursor = 'crosshair';
        }
    }
    
    handleWheel(e) {
        e.preventDefault();
        
        // 根据滚轮方向确定缩放因子
        const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
        
        // 调用缩放方法
        this.zoom(zoomFactor);
    }
    

    
    deleteSelectedAnnotation() {
        if (this.selectedAnnotation) {
            const index = this.annotations.indexOf(this.selectedAnnotation);
            if (index > -1) {
                this.annotations.splice(index, 1);
                this.selectedAnnotation = null;
                this.updateAnnotationList();
                this.redraw();
                // 实时保存
                this.saveAnnotation();
            }
        }
    }
    
    filterImages() {
        const searchTerm = document.getElementById('image-search').value.toLowerCase();
        const imageItems = document.querySelectorAll('#image-list .annotation-item');
        
        imageItems.forEach((item, index) => {
            const imageName = this.imageList[index].image_name.toLowerCase();
            item.style.display = imageName.includes(searchTerm) ? 'block' : 'none';
        });
    }
    
    showMessage(message, type) {
        // 简单的消息提示
        const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        alertDiv.style.top = '20px';
        alertDiv.style.right = '20px';
        alertDiv.style.zIndex = '9999';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alertDiv);
        
        setTimeout(() => {
            alertDiv.remove();
        }, 3000);
    }
    
    // 上一个类别
    prevClass() {
        if (this.projectData.classes.length === 0) return;
        const newIndex = this.selectedClass > 0 ? this.selectedClass - 1 : this.projectData.classes.length - 1;
        this.selectClass(newIndex, this.projectData.classes[newIndex]);
    }
    
    // 下一个类别
    nextClass() {
        if (this.projectData.classes.length === 0) return;
        const newIndex = this.selectedClass < this.projectData.classes.length - 1 ? this.selectedClass + 1 : 0;
        this.selectClass(newIndex, this.projectData.classes[newIndex]);
    }
    
    // 加载可用模型列表
    async loadAvailableModels() {
        try {
            const response = await fetch('/api/models/');
            this.availableModels = await response.json();
        } catch (error) {
            console.error('加载模型列表失败:', error);
            this.availableModels = [];
        }
    }
    
    // 显示自动标注模态框
    showAutoAnnotateModal() {
        if (this.availableModels.length === 0) {
            alert('没有可用的模型，请先上传模型文件');
            return;
        }
        
        const modalHtml = `
            <div class="modal fade" id="autoAnnotateModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">AI自动标注（仅适用目标检测）</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label for="auto-annotate-model" class="form-label">选择模型</label>
                                <div class="input-group">
                                    <select class="form-select" id="auto-annotate-model" required>
                                        <option value="">请选择模型</option>
                                        ${this.availableModels.map(model => 
                                            `<option value="${model.id}">${model.name} (${model.type})</option>`
                                        ).join('')}
                                    </select>
                                    <button class="btn btn-outline-info" type="button" id="view-model-classes">查看此模型类别</button>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label for="auto-annotate-conf" class="form-label">置信度阈值: <span id="auto-annotate-conf-value">0.25</span></label>
                                <input type="range" class="form-range" id="auto-annotate-conf" min="0.1" max="1.0" step="0.05" value="0.25">
                            </div>
                            <div class="mb-3">
                                <label for="auto-annotate-iou" class="form-label">IoU阈值: <span id="auto-annotate-iou-value">0.45</span></label>
                                <input type="range" class="form-range" id="auto-annotate-iou" min="0.1" max="1.0" step="0.05" value="0.45">
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="auto-annotate-overwrite" checked>
                                <label class="form-check-label" for="auto-annotate-overwrite">
                                    覆盖现有标注
                                </label>
                            </div>
                            <div class="alert alert-info mt-3">
                                <i class="fas fa-info-circle"></i> 系统将使用选定的模型对所有未完成的图片进行自动标注。您可以随时停止并手动调整结果。
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-primary" id="start-auto-annotate">开始标注</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 添加模态框到页面
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        const modal = new bootstrap.Modal(document.getElementById('autoAnnotateModal'));
        
        // 绑定事件
        document.getElementById('auto-annotate-conf').addEventListener('input', (e) => {
            document.getElementById('auto-annotate-conf-value').textContent = e.target.value;
        });
        
        document.getElementById('auto-annotate-iou').addEventListener('input', (e) => {
            document.getElementById('auto-annotate-iou-value').textContent = e.target.value;
        });
        
        document.getElementById('view-model-classes').addEventListener('click', () => {
            const modelId = document.getElementById('auto-annotate-model').value;
            if (modelId) {
                this.showModelClasses(modelId);
            } else {
                alert('请先选择模型');
            }
        });
        
        document.getElementById('start-auto-annotate').addEventListener('click', () => {
            const modelId = document.getElementById('auto-annotate-model').value;
            const confidence = parseFloat(document.getElementById('auto-annotate-conf').value);
            const iou = parseFloat(document.getElementById('auto-annotate-iou').value);
            const overwrite = document.getElementById('auto-annotate-overwrite').checked;
            
            if (!modelId) {
                alert('请选择模型');
                return;
            }
            
            modal.hide();
            this.startAutoAnnotate(modelId, confidence, iou, overwrite);
        });
        
        // 模态框关闭时清理DOM
        document.getElementById('autoAnnotateModal').addEventListener('hidden.bs.modal', () => {
            document.getElementById('autoAnnotateModal').remove();
        });
        
        modal.show();
    }
    
    // 开始自动标注
    async startAutoAnnotate(modelId, confidence, iou, overwrite) {
        this.isAutoAnnotating = true;
        this.autoAnnotateAbortController = new AbortController();
        
        // 更新UI
        document.getElementById('ai-auto-annotate').style.display = 'none';
        document.getElementById('stop-auto-annotate').style.display = 'inline-block';
        
        try {
            // 获取未完成的图片列表
            const uncompletedImages = this.imageList.filter(img => !img.is_completed);
            
            if (uncompletedImages.length === 0) {
                this.showMessage('所有图片已完成标注', 'info');
                this.stopAutoAnnotate();
                return;
            }
            
            this.showMessage(`开始自动标注 ${uncompletedImages.length} 张图片...`, 'info');
            
            for (let i = 0; i < uncompletedImages.length; i++) {
                if (!this.isAutoAnnotating) break;
                
                const imageData = uncompletedImages[i];
                const imageIndex = this.imageList.findIndex(img => img.id === imageData.id);
                
                // 切换到当前图片
                await this.loadImage(imageIndex);
                
                // 调用AI标注API
                await this.annotateImageWithAI(imageData.id, modelId, confidence, iou, overwrite);
                
                // 更新进度
                const progress = Math.round(((i + 1) / uncompletedImages.length) * 100);
                this.showMessage(`标注进度: ${progress}% (${i + 1}/${uncompletedImages.length})`, 'info');
                
                // 等待一小段时间避免过快请求
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            
            if (this.isAutoAnnotating) {
                this.showMessage('自动标注完成', 'success');
            }
            
        } catch (error) {
            console.error('自动标注失败:', error);
            this.showMessage('自动标注失败: ' + error.message, 'error');
        } finally {
            this.stopAutoAnnotate();
        }
    }
    
    // 停止自动标注
    stopAutoAnnotate() {
        this.isAutoAnnotating = false;
        if (this.autoAnnotateAbortController) {
            this.autoAnnotateAbortController.abort();
            this.autoAnnotateAbortController = null;
        }
        
        // 更新UI
        document.getElementById('ai-auto-annotate').style.display = 'inline-block';
        document.getElementById('stop-auto-annotate').style.display = 'none';
    }
    
    // 显示模型类别
    async showModelClasses(modelId) {
        try {
            const response = await fetch(`/api/models/${modelId}/classes`);
            const data = await response.json();
            
            if (data.classes) {
                this.showEditableClassesModal(data.classes);
            }
        } catch (error) {
            console.error('获取模型类别失败:', error);
            alert('获取模型类别失败');
        }
    }
    
    // 显示可编辑类别模态框
    showEditableClassesModal(classes) {
        const modalHtml = `
            <div class="modal fade" id="editClassesModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">模型类别列表</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle"></i> 可以修改类别名称，但不会改变类别顺序
                            </div>
                            <div id="editable-classes-list">
                                ${classes.map((className, index) => `
                                    <div class="mb-2">
                                        <div class="input-group input-group-sm">
                                            <span class="input-group-text">${index}</span>
                                            <input type="text" class="form-control" value="${className}" data-class-index="${index}">
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                            <button type="button" class="btn btn-primary" id="save-model-classes">保存到项目</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('editClassesModal'));
        
        document.getElementById('save-model-classes').addEventListener('click', () => {
            const inputs = document.querySelectorAll('#editable-classes-list input');
            const editedClasses = [];
            inputs.forEach(input => {
                if (input.value.trim()) {
                    editedClasses.push(input.value.trim());
                }
            });
            
            if (editedClasses.length > 0) {
                this.updateProjectClasses(editedClasses);
                modal.hide();
            } else {
                alert('请至少保留一个类别');
            }
        });
        
        document.getElementById('editClassesModal').addEventListener('hidden.bs.modal', () => {
            document.getElementById('editClassesModal').remove();
        });
        
        modal.show();
    }
    
    // 显示编辑项目类别模态框
    showEditProjectClassesModal() {
        const modalHtml = `
            <div class="modal fade" id="editProjectClassesModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">编辑项目类别</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="project-classes-list">
                                ${this.projectData.classes.map((className, index) => `
                                    <div class="mb-2 class-item" data-index="${index}">
                                        <div class="input-group input-group-sm">
                                            <span class="input-group-text">${index + 1}</span>
                                            <input type="text" class="form-control" value="${className}">
                                            <button class="btn btn-outline-danger" type="button" onclick="this.closest('.class-item').remove()">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                            <button class="btn btn-outline-success btn-sm" id="add-class-btn">
                                <i class="fas fa-plus"></i> 添加类别
                            </button>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-primary" id="save-project-classes">保存</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('editProjectClassesModal'));
        
        // 添加类别按钮事件
        document.getElementById('add-class-btn').addEventListener('click', () => {
            const container = document.getElementById('project-classes-list');
            const newIndex = container.children.length;
            const newClassHtml = `
                <div class="mb-2 class-item" data-index="${newIndex}">
                    <div class="input-group input-group-sm">
                        <span class="input-group-text">${newIndex + 1}</span>
                        <input type="text" class="form-control" value="新类别${newIndex + 1}" placeholder="输入类别名称">
                        <button class="btn btn-outline-danger" type="button" onclick="this.closest('.class-item').remove()">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', newClassHtml);
        });
        
        // 保存按钮事件
        document.getElementById('save-project-classes').addEventListener('click', () => {
            const inputs = document.querySelectorAll('#project-classes-list input');
            const newClasses = [];
            inputs.forEach(input => {
                if (input.value.trim()) {
                    newClasses.push(input.value.trim());
                }
            });
            
            if (newClasses.length === 0) {
                alert('请至少保留一个类别');
                return;
            }
            
            this.updateProjectClasses(newClasses);
            modal.hide();
        });
        
        document.getElementById('editProjectClassesModal').addEventListener('hidden.bs.modal', () => {
            document.getElementById('editProjectClassesModal').remove();
        });
        
        modal.show();
    }
    
    // 更新项目类别
    async updateProjectClasses(newClasses) {
        try {
            const response = await fetch(`/api/annotation/projects/${this.projectId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    classes: newClasses
                })
            });
            
            if (response.ok) {
                this.projectData.classes = newClasses;
                this.updateProjectInfo();
                this.loadClasses();
                this.showMessage('项目类别已更新', 'success');
            } else {
                const errorData = await response.json();
                this.showMessage('更新失败: ' + (errorData.detail || '未知错误'), 'error');
            }
        } catch (error) {
            console.error('更新项目类别失败:', error);
            this.showMessage('更新失败: ' + error.message, 'error');
        }
    }
    
    // 使用AI模型标注单张图片
    async annotateImageWithAI(imageId, modelId, confidence, iou, overwrite) {
        try {
            const response = await fetch(`/api/annotation/images/${imageId}/auto-annotate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    model_id: modelId,
                    confidence: confidence,
                    iou: iou,
                    overwrite: overwrite
                }),
                signal: this.autoAnnotateAbortController?.signal
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // 更新当前图片的标注数据
            if (this.currentImageData && this.currentImageData.id === imageId) {
                this.currentImageData.annotations = result.annotations;
                this.loadAnnotations();
                this.redraw();
            }
            
            // 更新图片列表中的数据
            const imageIndex = this.imageList.findIndex(img => img.id === imageId);
            if (imageIndex !== -1) {
                this.imageList[imageIndex].annotations = result.annotations;
                this.updateImageList();
            }
            
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('标注被用户取消');
            } else {
                console.error('自动标注失败:', error);
                throw error;
            }
        }
    }
    
    toggleCompletedFilter() {
        this.showCompleted = !this.showCompleted;
        const btn = document.getElementById('filter-completed');
        if (btn) {
            if (this.showCompleted) {
                btn.classList.remove('btn-outline-success');
                btn.classList.add('btn-success');
            } else {
                btn.classList.remove('btn-success');
                btn.classList.add('btn-outline-success');
            }
        }
        this.updateImageList();
    }
    
    toggleUncompletedFilter() {
        this.showUncompleted = !this.showUncompleted;
        const btn = document.getElementById('filter-uncompleted');
        if (btn) {
            if (this.showUncompleted) {
                btn.classList.remove('btn-outline-warning');
                btn.classList.add('btn-warning');
            } else {
                btn.classList.remove('btn-warning');
                btn.classList.add('btn-outline-warning');
            }
        }
        this.updateImageList();
    }
    
    updateImageListSelection() {
        const imageItems = document.querySelectorAll('#image-list .annotation-item');
        imageItems.forEach((item, index) => {
            // 获取原始索引
            const originalIndex = this.filteredImageIndices[index];
            item.classList.toggle('selected', originalIndex === this.currentImageIndex);
        });
    }
    

    

    

    
    // 显示SAM3操作选项
    showSAM3OperationOptions() {
        // 这个方法现在不再需要，因为使用了固定的SAM3操作工具栏
        // 保持为空实现以维持兼容性
    }
    
    // 隐藏SAM3操作选项
    hideSAM3OperationOptions() {
        // 这个方法现在不再需要，因为使用了固定的SAM3操作工具栏
        // 保持为空实现以维持兼容性
    }
    
    // 显示SAM3提示信息
    showSam3HintInfo() {
        const hintInfo = document.getElementById('sam3-hint-info');
        if (hintInfo) {
            hintInfo.style.display = 'block';
        }
    }
    
    // 处理SAM3开关切换
    handleSam3ToggleChange(event) {
        const isChecked = event.target.checked;
        
        if (isChecked) {
            // 启用SAM3
            if (this.sam3Tool) {
                this.sam3Tool.activate();
            }
        } else {
            // 禁用SAM3
            if (this.sam3Tool && this.sam3Tool.isActive) {
                this.sam3Tool.deactivate();
            }
        }
    }
    
    // 隐藏SAM3提示信息
    hideSam3HintInfo() {
        const hintInfo = document.getElementById('sam3-hint-info');
        if (hintInfo) {
            hintInfo.style.display = 'none';
        }
    }
    
    

}

// 初始化标注工具
let annotationTool;
document.addEventListener('DOMContentLoaded', () => {
    annotationTool = new AnnotationTool();
});