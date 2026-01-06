// 在线标注模块
class OnlineAnnotation {
    constructor() {
        this.currentSortField = '';
        this.currentSortDirection = 'asc';
    }

    // 加载标注页面
    loadAnnotationPage() {
        console.log('Loading annotation page...');
        
        // 加载标注项目列表
        this.loadAnnotationProjects();
        
        // 绑定标注页面事件
        this.bindAnnotationEvents();
    }

    // 加载标注项目列表
    loadAnnotationProjects() {
        authenticatedFetch(`${API_URL}/annotation/projects/`)
            .then(response => response.json())
            .then(projects => {
                const tableBody = document.getElementById('annotation-projects-table-body');
                if (!tableBody) {
                    console.error('annotation-projects-table-body element not found');
                    return;
                }

                tableBody.innerHTML = '';

                if (projects.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="8" class="text-center">暂无标注项目</td></tr>';
                    return;
                }

                projects.forEach(project => {
                    const row = document.createElement('tr');
                    
                    // 获取项目统计信息
                    authenticatedFetch(`${API_URL}/annotation/projects/${project.id}/stats`)
                        .then(response => response.json())
                        .then(stats => {
                            const progressPercentage = stats.progress_percentage || 0;
                            
                            // 获取项目类型显示文本
                            const projectTypeText = this.getProjectTypeText(project.project_type);
                            
                            row.innerHTML = `
                                <td>${project.name}</td>
                                <td>${project.description || '-'}</td>
                                <td><span class="badge bg-info">${projectTypeText}</span></td>
                                <td>${project.classes.length}</td>
                                <td>${stats.total_images || 0}</td>
                                <td>${stats.completed_images || 0}</td>
                                <td style="padding-top: 2px;">
                                    <div class="progress" style="width: 100px;">
                                        <div class="progress-bar" role="progressbar" style="width: ${progressPercentage}%" aria-valuenow="${progressPercentage}" aria-valuemin="0" aria-valuemax="100">
                                            ${Math.round(progressPercentage)}%
                                        </div>
                                    </div>
                                </td>
                                <td><span class="badge ${this.getStatusBadgeClass(project.status)}">${this.getStatusText(project.status)}</span></td>
                                <td>
                                    <div class="btn-group">
                                        <a href="/static/annotation.html?project_id=${project.id}" target="_blank" class="btn btn-sm btn-primary">开始标注</a>
                                        <button class="btn btn-sm btn-info" onclick="onlineAnnotation.scanProjectImages('${project.id}')">扫描图片</button>
                                        <button class="btn btn-sm btn-success" onclick="onlineAnnotation.exportAnnotations('${project.id}')">导出标注</button>
                                        <button class="btn btn-sm btn-warning" onclick="onlineAnnotation.exportToDataset('${project.id}')">导出为数据集</button>
                                        <button class="btn btn-sm btn-danger" onclick="onlineAnnotation.deleteAnnotationProject('${project.id}')">删除</button>
                                    </div>
                                </td>
                            `;
                        })
                        .catch(error => {
                            console.error('Error loading project stats:', error);
                            // 获取项目类型显示文本
                            const projectTypeText = this.getProjectTypeText(project.project_type);
                            
                            row.innerHTML = `
                                <td>${project.name}</td>
                                <td>${project.description || '-'}</td>
                                <td><span class="badge bg-info">${projectTypeText}</span></td>
                                <td>${project.classes.length}</td>
                                <td>-</td>
                                <td>-</td>
                                <td>-</td>
                                <td><span class="badge bg-secondary">未知</span></td>
                                <td>
                                    <div class="btn-group">
                                        <a href="/static/annotation.html?project_id=${project.id}" target="_blank" class="btn btn-sm btn-primary">开始标注</a>
                                        <button class="btn btn-sm btn-info" onclick="onlineAnnotation.scanProjectImages('${project.id}')">扫描图片</button>
                                        <button class="btn btn-sm btn-success" onclick="onlineAnnotation.exportAnnotations('${project.id}')">导出</button>
                                        <button class="btn btn-sm btn-warning" onclick="onlineAnnotation.exportToDataset('${project.id}')">导出为数据集</button>
                                        <button class="btn btn-sm btn-danger" onclick="onlineAnnotation.deleteAnnotationProject('${project.id}')">删除</button>
                                    </div>
                                </td>
                            `;
                        });
                    
                    tableBody.appendChild(row);
                });
            })
            .catch(error => {
                console.error('Error loading annotation projects:', error);
                const tableBody = document.getElementById('annotation-projects-table-body');
                if (tableBody) {
                    tableBody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">加载标注项目失败</td></tr>';
                }
            });
    }

    // 绑定标注页面事件
    bindAnnotationEvents() {
        const createProjectBtn = document.getElementById('create-annotation-project-btn');
        if (createProjectBtn) {
            createProjectBtn.addEventListener('click', () => this.showCreateAnnotationProjectModal());
        }
        
        const projectSelect = document.getElementById('annotation-project-select');
        if (projectSelect) {
            projectSelect.addEventListener('change', function() {
                if (this.value) {
                    // 这里需要实现加载标注项目功能
                    console.log('Loading annotation project:', this.value);
                }
            });
        }
    }

    // 显示创建标注项目模态框
    showCreateAnnotationProjectModal() {
        const modalTitle = document.querySelector('.modal-title');
        const modalBody = document.querySelector('.modal-body');
        const modalSubmit = document.getElementById('modalSubmit');

        modalTitle.textContent = '创建标注项目';

        // 获取模板内容
        const template = document.getElementById('create-annotation-project-template');
        if (!template) {
            console.error('create-annotation-project-template not found');
            return;
        }

        modalBody.innerHTML = template.innerHTML;

        // 加载数据集选项
        this.loadDatasetOptionsForAnnotation();
        
        // 绑定图片来源选择事件
        this.bindImageSourceEvents();
        
        // 绑定标注类型选择事件
        this.bindAnnotationTypeEvents();
        
        // 绑定类别和关键点配置事件
        this.bindClassKeypointsEvents();
        
        // 为初始的项目绑定事件
        document.querySelectorAll('.class-keypoints-item').forEach(item => {
            this.bindKeypointEventsForItem(item);
        });

        modal.show();

        modalSubmit.onclick = () => this.submitCreateAnnotationProject();
    }

    // 绑定图片来源选择事件
    bindImageSourceEvents() {
        const imageSourceRadios = document.querySelectorAll('input[name="image-source"]');
        const datasetContainer = document.getElementById('dataset-source-container');
        const directoryContainer = document.getElementById('directory-source-container');
        const uploadContainer = document.getElementById('upload-source-container');
        
        // 保存this引用以在事件处理函数中使用
        const self = this;
        
        imageSourceRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                // 隐藏所有容器
                datasetContainer.style.display = 'none';
                directoryContainer.style.display = 'none';
                uploadContainer.style.display = 'none';
                
                // 显示选中的容器
                if (this.value === 'dataset') {
                    datasetContainer.style.display = 'block';
                } else if (this.value === 'directory') {
                    directoryContainer.style.display = 'block';
                    // 绑定目录浏览按钮
                    self.bindDirectoryBrowseButton();
                } else if (this.value === 'upload') {
                    uploadContainer.style.display = 'block';
                }
            });
        });
        
        // 默认显示上传容器
        uploadContainer.style.display = 'block';
    }

    // 绑定目录浏览按钮
    bindDirectoryBrowseButton() {
        const browseBtn = document.getElementById('browse-image-directory-btn');
        const directoryInput = document.getElementById('annotation-image-directory');
        const scanResultDiv = document.getElementById('directory-scan-result');
        const imageCountSpan = document.getElementById('directory-image-count');
        
        if (browseBtn && !browseBtn.hasAttribute('data-bound')) {
            browseBtn.setAttribute('data-bound', 'true');
            browseBtn.addEventListener('click', function() {
                if (window.directoryBrowser) {
                    window.directoryBrowser.show(function(selectedPath) {
                        directoryInput.value = selectedPath;
                        
                        // 扫描选中目录的图片
                        authenticatedFetch(`/api/annotation/scan-directory-images?directory_path=${encodeURIComponent(selectedPath)}`)
                            .then(response => response.json())
                            .then(data => {
                                imageCountSpan.textContent = data.image_count;
                                scanResultDiv.style.display = 'block';
                                
                                if (data.is_valid) {
                                    scanResultDiv.querySelector('.alert').className = 'alert alert-success';
                                } else {
                                    scanResultDiv.querySelector('.alert').className = 'alert alert-warning';
                                }
                            })
                            .catch(error => {
                                console.error('扫描图片失败:', error);
                                scanResultDiv.style.display = 'none';
                            });
                    });
                } else {
                    alert('目录浏览器未加载，请刷新页面重试');
                }
            });
        }
    }
    
    // 绑定标注类型选择事件
    bindAnnotationTypeEvents() {
        const projectTypeSelect = document.getElementById('annotation-project-type');
        const poseConfigDiv = document.getElementById('pose-configuration');
        const defaultClassesDiv = document.getElementById('default-classes');
        
        projectTypeSelect.addEventListener('change', function() {
            const selectedType = this.value;
            
            if (selectedType === 'pose') {
                poseConfigDiv.style.display = 'block';
                defaultClassesDiv.style.display = 'none';
            } else {
                poseConfigDiv.style.display = 'none';
                defaultClassesDiv.style.display = 'block';
            }
        });
    }
    
    // 绑定类别和关键点配置事件
    bindClassKeypointsEvents() {
        const container = document.getElementById('class-keypoints-container');
        
        // 绑定添加类别和关键点按钮事件
        document.getElementById('add-class-keypoints').addEventListener('click', () => {
            const item = document.createElement('div');
            item.className = 'class-keypoints-item mb-3';
            item.innerHTML = `
                <div class="row">
                    <div class="col-md-4">
                        <input type="text" class="form-control class-name" placeholder="类别名称，如：person">
                    </div>
                    <div class="col-md-8">
                        <div class="keypoints-input-container">
                            <div class="mb-2">
                                <label class="form-label">关键点名称列表</label>
                            </div>
                            <div class="keypoints-list-container">
                                <!-- 关键点输入框将动态生成 -->
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-secondary mt-2 add-keypoint-btn">+ 添加关键点</button>
                        </div>
                    </div>
                </div>
                <div class="row mt-2">
                    <div class="col-md-12 text-end">
                        <button type="button" class="btn btn-sm btn-outline-danger remove-class-keypoints">删除</button>
                    </div>
                </div>
            `;
            container.appendChild(item);
            
            // 为新添加的项绑定事件
            this.bindKeypointEventsForItem(item);
            
            // 绑定删除按钮事件
            item.querySelector('.remove-class-keypoints').addEventListener('click', () => {
                if (document.querySelectorAll('.class-keypoints-item').length > 1) {
                    item.remove();
                } else {
                    alert('至少需要保留一个类别配置');
                }
            });
        });
        
        // 为初始项绑定事件
        document.querySelectorAll('.class-keypoints-item').forEach(item => {
            this.bindKeypointEventsForItem(item);
        });
        
        // 绑定删除按钮事件（对于初始的项目）
        document.querySelectorAll('.remove-class-keypoints').forEach(button => {
            button.addEventListener('click', function() {
                const item = this.closest('.class-keypoints-item');
                if (document.querySelectorAll('.class-keypoints-item').length > 1) {
                    item.remove();
                } else {
                    alert('至少需要保留一个类别配置');
                }
            });
        });
    }
    
    // 为单个项绑定关键点事件
    bindKeypointEventsForItem(item) {
        // 从全局关键点数量获取数量并更新输入框
        const globalKeypointsCountInput = document.getElementById('global-keypoints-count');
        const keypointsListContainer = item.querySelector('.keypoints-list-container');
        const addKeypointBtn = item.querySelector('.add-keypoint-btn');
        
        // 当全局关键点数量改变时，更新所有项的输入框数量
        if (globalKeypointsCountInput) {
            globalKeypointsCountInput.addEventListener('change', () => {
                this.updateKeypointInputs(item);
            });
            
            // 为number输入框添加输入事件，实时更新
            globalKeypointsCountInput.addEventListener('input', () => {
                this.updateKeypointInputs(item);
            });
        }
        
        // 添加关键点按钮事件
        addKeypointBtn.addEventListener('click', () => {
            this.addKeypointInput(item);
        });
        
        // 页面加载时，根据全局值更新关键点输入框
        setTimeout(() => {
            this.updateKeypointInputs(item);
        }, 0);
    }
    
    // 更新关键点输入框数量
    updateKeypointInputs(item) {
        const globalKeypointsCountInput = document.getElementById('global-keypoints-count');
        const keypointsListContainer = item.querySelector('.keypoints-list-container');
        
        if (!globalKeypointsCountInput) {
            return;
        }
        
        const count = parseInt(globalKeypointsCountInput.value) || 0;
        
        if (count <= 0) {
            keypointsListContainer.innerHTML = '';
            return;
        }
        
        // 获取现有的关键点输入框数量
        const existingInputs = keypointsListContainer.querySelectorAll('.keypoint-input');
        const existingCount = existingInputs.length;
        
        // 如果需要增加输入框
        if (count > existingCount) {
            for (let i = existingCount; i < count; i++) {
                const inputGroup = document.createElement('div');
                inputGroup.className = 'keypoint-input-group mb-1';
                inputGroup.innerHTML = `
                    <div class="input-group">
                        <span class="input-group-text">关键点${i + 1}</span>
                        <input type="text" class="form-control keypoint-input" placeholder="如：head" data-index="${i}">
                        <button class="btn btn-outline-danger remove-keypoint" type="button">删除</button>
                    </div>
                `;
                keypointsListContainer.appendChild(inputGroup);
                
                // 绑定删除按钮事件
                inputGroup.querySelector('.remove-keypoint').addEventListener('click', () => {
                    if (keypointsListContainer.querySelectorAll('.keypoint-input').length > 1) {
                        inputGroup.remove();
                        this.updateKeypointIndices(item);
                    } else {
                        alert('至少需要保留一个关键点');
                    }
                });
            }
        }
        // 如果需要减少输入框
        else if (count < existingCount) {
            const inputsToRemove = Array.from(existingInputs).slice(count);
            inputsToRemove.forEach(inputGroup => inputGroup.remove());
        }
        
        // 更新所有输入框的索引
        this.updateKeypointIndices(item);
    }
    
    // 添加单个关键点输入框
    addKeypointInput(item) {
        const globalKeypointsCountInput = document.getElementById('global-keypoints-count');
        const keypointsListContainer = item.querySelector('.keypoints-list-container');
        const existingInputs = keypointsListContainer.querySelectorAll('.keypoint-input');
        
        if (!globalKeypointsCountInput) {
            return;
        }
        
        const maxCount = parseInt(globalKeypointsCountInput.value) || 0;
        if (existingInputs.length >= maxCount) {
            alert(`已达到设定的关键点数量上限（${maxCount}个）！`);
            return;
        }
        
        const nextIndex = existingInputs.length;
        
        const inputGroup = document.createElement('div');
        inputGroup.className = 'keypoint-input-group mb-1';
        inputGroup.innerHTML = `
            <div class="input-group">
                <span class="input-group-text">关键点${nextIndex + 1}</span>
                <input type="text" class="form-control keypoint-input" placeholder="如：head" data-index="${nextIndex}">
                <button class="btn btn-outline-danger remove-keypoint" type="button">删除</button>
            </div>
        `;
        keypointsListContainer.appendChild(inputGroup);
        
        // 绑定删除按钮事件
        inputGroup.querySelector('.remove-keypoint').addEventListener('click', () => {
            if (keypointsListContainer.querySelectorAll('.keypoint-input').length > 1) {
                inputGroup.remove();
                this.updateKeypointIndices(item);
            } else {
                alert('至少需要保留一个关键点');
            }
        });
    }
    
    // 更新关键点输入框索引
    updateKeypointIndices(item) {
        const inputs = item.querySelectorAll('.keypoint-input');
        inputs.forEach((input, index) => {
            input.dataset.index = index;
            // 更新标签文本
            const label = input.closest('.input-group').querySelector('.input-group-text');
            label.textContent = `关键点${index + 1}`;
        });
    }
    
    // 获取类别和关键点配置数据
    getClassKeypointsData() {
        const globalKeypointsCountInput = document.getElementById('global-keypoints-count');
        if (!globalKeypointsCountInput) {
            alert('请设置关键点数量');
            return null;
        }
        
        const globalKeypointsCount = parseInt(globalKeypointsCountInput.value) || 0;
        if (globalKeypointsCount <= 0) {
            alert('关键点数量必须大于0');
            return null;
        }
        
        const items = document.querySelectorAll('.class-keypoints-item');
        const data = [];
        
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            const className = item.querySelector('.class-name').value.trim();
            const keypointsInputs = item.querySelectorAll('.keypoint-input');
            
            if (className) {
                // 检查实际输入的关键点数量是否与全局设定的数量一致
                if (keypointsInputs.length !== globalKeypointsCount) {
                    alert(`类别 "${className}" 设定的关键点数量为 ${globalKeypointsCount}，但实际输入了 ${keypointsInputs.length} 个关键点，请调整数量！`);
                    return null;
                }
                
                // 收集关键点名称
                const keypoints = [];
                let hasEmptyKeypoint = false;
                
                keypointsInputs.forEach((kpInput, index) => {
                    const keypointName = kpInput.value.trim();
                    if (!keypointName) {
                        alert(`类别 "${className}" 的第 ${index + 1} 个关键点不能为空！`);
                        hasEmptyKeypoint = true;
                    }
                    keypoints.push(keypointName);
                });
                
                if (hasEmptyKeypoint) {
                    return null;
                }
                
                data.push({
                    class_name: className,
                    keypoints_count: globalKeypointsCount,  // 使用全局关键点数量
                    keypoints: keypoints
                });
            }
        }
        
        if (data.length === 0) {
            alert('请至少添加一个类别和关键点配置');
            return null;
        }
        
        return data;
    }
    
    // 提交创建标注项目
    submitCreateAnnotationProject() {
        const name = document.getElementById('annotation-project-name').value;
        const description = document.getElementById('annotation-project-description').value;
        const projectType = document.getElementById('annotation-project-type').value;
        const imageSource = document.querySelector('input[name="image-source"]:checked').value;
        
        if (!name) {
            alert('请输入项目名称');
            return;
        }
        
        let classes = [];
        let classKeypoints = null;
        
        if (projectType === 'pose') {
            // 关键点项目：验证全局关键点数量输入
            const globalKeypointsCountInput = document.getElementById('global-keypoints-count');
            if (!globalKeypointsCountInput) {
                alert('关键点数量输入框未找到');
                return;
            }
            
            const globalKeypointsCount = parseInt(globalKeypointsCountInput.value);
            if (isNaN(globalKeypointsCount) || globalKeypointsCount <= 0) {
                alert('请输入有效的大于0的关键点数量');
                return;
            }
            
            // 使用类别和关键点配置
            classKeypoints = this.getClassKeypointsData();
            if (!classKeypoints) {
                // getClassKeypointsData方法会在验证失败时返回null并显示错误信息
                return;
            }
            // 从关键点配置中提取类别列表
            classes = classKeypoints.map(item => item.class_name);
        } else {
            // 非关键点项目：使用默认类别列表
            const classesTextarea = document.getElementById('annotation-classes');
            classes = classesTextarea.value.split('\n')
                .map(cls => cls.trim())
                .filter(cls => cls);
            
            if (classes.length === 0) {
                alert('请至少输入一个类别');
                return;
            }
        }
        
        if (imageSource === 'upload') {
            const zipFile = document.getElementById('annotation-images-zip').files[0];
            if (!zipFile) {
                alert('请选择图片ZIP文件');
                return;
            }
            this.createProjectWithImageUpload(name, description, projectType, classes, classKeypoints, zipFile);
        } else {
            this.createProjectWithExistingImages(name, description, projectType, classes, classKeypoints, imageSource);
        }
    }

    // 使用上传图片创建项目
    createProjectWithImageUpload(name, description, projectType, classes, classKeypoints, zipFile) {
        const progressContainer = document.getElementById('annotation-upload-progress');
        const progressBar = document.getElementById('annotation-progress-bar');
        const statusDiv = document.getElementById('annotation-upload-status');
        const modalSubmit = document.getElementById('modalSubmit');
        
        // 显示进度
        progressContainer.style.display = 'block';
        modalSubmit.disabled = true;
        modalSubmit.textContent = '创建中...';
        
        const formData = new FormData();
        formData.append('name', name);
        formData.append('description', description);
        formData.append('project_type', projectType);
        formData.append('classes', JSON.stringify(classes));
        if (classKeypoints) {
            formData.append('class_keypoints', JSON.stringify(classKeypoints));
        }
        formData.append('images_zip', zipFile);
        
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_URL}/annotation/projects/upload`, true);
        
        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progressBar.style.width = percentComplete + '%';
                progressBar.textContent = Math.round(percentComplete) + '%';
                statusDiv.textContent = '上传中...';
            }
        };
        
        xhr.onload = () => {
            if (xhr.status === 200 || xhr.status === 201) {
                statusDiv.textContent = '创建成功！';
                setTimeout(() => {
                    modal.hide();
                    onlineAnnotation.loadAnnotationProjects();
                    alert('标注项目创建成功！');
                }, 1000);
            } else {
                try {
                    const response = JSON.parse(xhr.responseText);
                    alert('创建失败: ' + (response.detail || '未知错误'));
                } catch (e) {
                    alert('创建失败: ' + xhr.statusText);
                }
                modalSubmit.disabled = false;
                modalSubmit.textContent = '确定';
                progressContainer.style.display = 'none';
            }
        };
        
        xhr.onerror = function() {
            alert('上传失败，请检查网络连接');
            modalSubmit.disabled = false;
            modalSubmit.textContent = '确定';
            progressContainer.style.display = 'none';
        };
        
        xhr.send(formData);
    }

    // 使用现有图片创建项目
    createProjectWithExistingImages(name, description, projectType, classes, classKeypoints, imageSource) {
        const requestData = {
            name: name,
            description: description,
            project_type: projectType,
            classes: classes
        };
        
        // 添加关键点配置（如果存在）
        if (classKeypoints) {
            requestData.class_keypoints = classKeypoints;
        }
        
        let apiEndpoint = `${API_URL}/annotation/projects/`;
        
        if (imageSource === 'dataset') {
            const datasetId = document.getElementById('annotation-dataset-id').value;
            if (!datasetId) {
                alert('请选择数据集');
                return;
            }
            requestData.dataset_id = datasetId;
        } else if (imageSource === 'directory') {
            const imageDirectory = document.getElementById('annotation-image-directory').value;
            if (!imageDirectory) {
                alert('请选择图片目录');
                return;
            }
            requestData.image_directory = imageDirectory;
            apiEndpoint = `${API_URL}/annotation/projects/from-directory`;
        }
        
        authenticatedFetch(apiEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || '创建项目失败'); });
            }
            return response.json();
        })
        .then(data => {
            modal.hide();
            this.loadAnnotationProjects();
            alert('标注项目创建成功！');
        })
        .catch(error => {
            console.error('Error creating annotation project:', error);
            alert('创建标注项目失败: ' + error.message);
        });
    }

    // 加载数据集选项用于标注项目
    loadDatasetOptionsForAnnotation() {
        fetch(`${API_URL}/datasets/`)
            .then(response => response.json())
            .then(datasets => {
                const select = document.getElementById('annotation-dataset-id');
                if (!select) return;
                
                // 清空现有选项（保留第一个默认选项）
                while (select.options.length > 1) {
                    select.remove(1);
                }
                
                datasets.forEach(dataset => {
                    if (dataset.status === 'available') {
                        const option = document.createElement('option');
                        option.value = dataset.id;
                        option.textContent = dataset.name;
                        select.appendChild(option);
                    }
                });
                
                // 绑定数据集选择事件
                select.addEventListener('change', function() {
                    if (this.value) {
                        // 根据选择的数据集自动填充信息
                        const selectedDataset = datasets.find(d => d.id === this.value);
                        if (selectedDataset) {
                            // 自动填充类别
                            const classesTextarea = document.getElementById('annotation-classes');
                            if (classesTextarea && selectedDataset.classes) {
                                classesTextarea.value = selectedDataset.classes.join('\n');
                            }
                            
                            // 自动填充图片目录
                            const imageDirectoryInput = document.getElementById('annotation-image-directory');
                            if (imageDirectoryInput) {
                                imageDirectoryInput.value = `datasets/${selectedDataset.name}/train/images`;
                            }
                        }
                    }
                });
            })
            .catch(error => {
                console.error('Error loading datasets for annotation:', error);
            });
    }

    // 扫描项目图片
    scanProjectImages(projectId) {
        if (!confirm('确定要扫描项目图片吗？这将重新扫描图片目录并更新图片列表。')) {
            return;
        }
        
        authenticatedFetch(`${API_URL}/annotation/projects/${projectId}/scan`, {
            method: 'POST'
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || '扫描失败'); });
            }
            return response.json();
        })
        .then(data => {
            alert(data.message || '图片扫描完成');
            this.loadAnnotationProjects(); // 刷新项目列表
        })
        .catch(error => {
            console.error('Error scanning project images:', error);
            alert('扫描项目图片失败: ' + error.message);
        });
    }

    // 导出标注数据
    exportAnnotations(projectId) {
        const exportRequest = {
            format: 'yolo',
            include_images: true,
            split_data: false
        };
        
        authenticatedFetch(`${API_URL}/annotation/projects/${projectId}/export`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(exportRequest)
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    try {
                        const err = JSON.parse(text);
                        throw new Error(err.detail || '导出失败');
                    } catch (e) {
                        throw new Error('导出失败: ' + response.statusText);
                    }
                });
            }
            
            // 检查响应类型
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/zip')) {
                // 处理ZIP文件下载
                return response.blob().then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `annotations_project_${projectId}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                    return { message: '标注数据导出成功，文件已下载' };
                });
            } else {
                // 处理JSON响应
                return response.json();
            }
        })
        .then(data => {
            alert(data.message || '标注数据导出成功');
            if (data.export_path) {
                console.log('Export path:', data.export_path);
            }
        })
        .catch(error => {
            console.error('Error exporting annotations:', error);
            alert('导出标注数据失败: ' + error.message);
        });
    }

    // 删除标注项目
    deleteAnnotationProject(projectId) {
        if (!confirm('确定要删除这个标注项目吗？这将删除所有相关的标注数据。')) {
            return;
        }
        
        authenticatedFetch(`${API_URL}/annotation/projects/${projectId}`, {
            method: 'DELETE'
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || '删除失败'); });
            }
            return response.json();
        })
        .then(data => {
            alert(data.message || '标注项目删除成功');
            this.loadAnnotationProjects(); // 刷新项目列表
        })
        .catch(error => {
            console.error('Error deleting annotation project:', error);
            alert('删除标注项目失败: ' + error.message);
        });
    }

    // 导出为数据集
    exportToDataset(projectId) {
        const datasetName = prompt('请输入数据集名称:');
        if (!datasetName) {
            return;
        }
        
        const datasetDescription = prompt('请输入数据集描述(可选):') || '';
        
        const formData = new FormData();
        formData.append('dataset_name', datasetName);
        formData.append('dataset_description', datasetDescription);
        
        authenticatedFetch(`${API_URL}/annotation/projects/${projectId}/export-to-dataset`, {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || '导出失败'); });
            }
            return response.json();
        })
        .then(data => {
            alert(data.message || '导出为数据集成功');
            console.log('Dataset ID:', data.dataset_id);
        })
        .catch(error => {
            console.error('Error exporting to dataset:', error);
            alert('导出为数据集失败: ' + error.message);
        });
    }

    // 获取状态文本
    getStatusText(status) {
        switch (status) {
            case 'processing':
                return '处理中';
            case 'available':
                return '可用';
            case 'error':
                return '错误';
            case 'pending':
                return '未训练';
            case 'running':
                return '运行中';
            case 'training':
                return '训练中';
            case 'completed':
                return '已完成';
            case 'failed':
                return '失败';
            case 'cancelled':
                return '已取消';
            case 'active':
                return '进行中';
            case 'inactive':
                return '已完成';
            default:
                return status;
        }
    }

    // 获取状态徽章样式
    getStatusBadgeClass(status) {
        switch (status) {
            case 'processing':
            case 'pending':
                return 'bg-warning';
            case 'available':
            case 'completed':
            case 'inactive':
                return 'bg-success';
            case 'error':
            case 'failed':
                return 'bg-danger';
            case 'running':
            case 'training':
            case 'active':
                return 'bg-primary';
            case 'cancelled':
                return 'bg-secondary';
            default:
                return 'bg-secondary';
        }
    }
    
    // 获取项目类型文本
    getProjectTypeText(projectType) {
        const typeMap = {
            'detection': '目标检测',
            'segmentation': '实例分割',
            'obb': '旋转框',
            'pose': '关键点/姿态估计'
        };
        return typeMap[projectType] || projectType || '目标检测';
    }
}

// 创建全局实例
window.onlineAnnotation = new OnlineAnnotation();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OnlineAnnotation;
}
