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
                                        <button class="btn btn-sm btn-secondary" onclick="onlineAnnotation.showExpandDataModal('${project.id}', '${project.name}')">扩充数据</button>
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
                                        <button class="btn btn-sm btn-secondary" onclick="onlineAnnotation.showExpandDataModal('${project.id}', '${project.name}')">扩充数据</button>
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
        
        const mergeProjectBtn = document.getElementById('merge-annotation-projects-btn');
        if (mergeProjectBtn) {
            mergeProjectBtn.addEventListener('click', () => this.showMergeAnnotationProjectsModal());
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
        
        // 绑定导入原标注开关事件
        this.bindImportOriginalAnnotationsEvent();
        
        // 为初始的项目绑定事件
        document.querySelectorAll('.class-keypoints-item').forEach(item => {
            this.bindKeypointEventsForItem(item);
        });

        modal.show();
        
        // 设置提交按钮文字为确定
        modalSubmit.textContent = '确定';
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
        const importOriginalAnnotations = document.getElementById('import-original-annotations').checked;
        
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
            
            // 如果是上传ZIP且勾选了导入原标注，则不需要类别列表
            if (!(imageSource === 'upload' && importOriginalAnnotations)) {
                classes = classesTextarea.value.split('\n')
                    .map(cls => cls.trim())
                    .filter(cls => cls);
                
                if (classes.length === 0) {
                    alert('请至少输入一个类别');
                    return;
                }
            }
            // 如果勾选了导入原标注且是上传ZIP，则classes将在后端解析
        }
        
        if (imageSource === 'upload') {
            const zipFile = document.getElementById('annotation-images-zip').files[0];
            if (!zipFile) {
                alert('请选择图片ZIP文件');
                return;
            }
            this.createProjectWithImageUpload(name, description, projectType, classes, classKeypoints, zipFile, importOriginalAnnotations);
        } else {
            this.createProjectWithExistingImages(name, description, projectType, classes, classKeypoints, imageSource);
        }
    }

    // 使用上传图片创建项目
    createProjectWithImageUpload(name, description, projectType, classes, classKeypoints, zipFile, importOriginalAnnotations) {
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
        // 只有在未勾选导入原标注时才发送classes
        if (!importOriginalAnnotations) {
            formData.append('classes', JSON.stringify(classes));
        }
        if (classKeypoints) {
            formData.append('class_keypoints', JSON.stringify(classKeypoints));
        }
        formData.append('import_original_annotations', importOriginalAnnotations);
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
                const response = JSON.parse(xhr.responseText);
                statusDiv.textContent = '创建成功！';
                setTimeout(() => {
                    // 重置按钮状态
                    modalSubmit.disabled = false;
                    modalSubmit.textContent = '确定';
                    progressContainer.style.display = 'none';
                    
                    modal.hide();
                    onlineAnnotation.loadAnnotationProjects();
                    
                    // 检查是否有导入结果
                    let successMessage = '标注项目创建成功！';
                    if (response.import_result) {
                        const importResult = response.import_result;
                        successMessage += `\n\n导入结果：`;
                        successMessage += `\n- 发现图片: ${importResult.total_images}`;
                        successMessage += `\n- 成功匹配标注图片: ${importResult.matched_image_count || importResult.matched_annotations || 0}`;
                        successMessage += `\n- 无标注图片: ${importResult.unannotated_images}`;
                        if (importResult.parsed_classes && importResult.parsed_classes.length > 0) {
                            successMessage += `\n- 解析类别: ${importResult.parsed_classes.join(', ')}`;
                        }
                        if (importResult.errors && importResult.errors.length > 0) {
                            successMessage += `\n- 导入错误: ${importResult.errors.length} 项`;
                        }
                        // 如果有总的处理标注数量，也显示
                        if (importResult.total_processed_annotations !== undefined) {
                            successMessage += `\n- 总标注数量: ${importResult.total_processed_annotations}`;
                        }
                    }
                    alert(successMessage);
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
        // 获取导入原标注选项
        const importOriginalAnnotations = document.getElementById('import-original-annotations').checked;
        
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
            requestData.import_original_annotations = importOriginalAnnotations;
        } else if (imageSource === 'directory') {
            const imageDirectory = document.getElementById('annotation-image-directory').value;
            if (!imageDirectory) {
                alert('请选择图片目录');
                return;
            }
            requestData.image_directory = imageDirectory;
            requestData.import_original_annotations = importOriginalAnnotations;
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
            
            // 检查是否有导入结果
            let successMessage = '标注项目创建成功！';
            if (data.import_result) {
                const importResult = data.import_result;
                successMessage += `\n\n导入结果：`;
                successMessage += `\n- 发现图片: ${importResult.total_images}`;
                successMessage += `\n- 成功匹配标注图片: ${importResult.matched_image_count || importResult.matched_annotations || 0}`;
                successMessage += `\n- 无标注图片: ${importResult.unannotated_images}`;
                if (importResult.errors && importResult.errors.length > 0) {
                    successMessage += `\n- 导入错误: ${importResult.errors.length} 项`;
                }
                // 如果有总的处理标注数量，也显示
                if (importResult.total_processed_annotations !== undefined) {
                    successMessage += `\n- 总标注数量: ${importResult.total_processed_annotations}`;
                }
            }
            alert(successMessage);
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
    
    // 绑定导入原标注开关事件
    bindImportOriginalAnnotationsEvent() {
        const importOriginalAnnotationsCheckbox = document.getElementById('import-original-annotations');
        const defaultClassesDiv = document.getElementById('default-classes');
        const annotationClassesTextarea = document.getElementById('annotation-classes');
        const originalClassesInfo = document.getElementById('original-classes-info');
        const imageSourceRadios = document.querySelectorAll('input[name="image-source"]');
        
        if (importOriginalAnnotationsCheckbox) {
            // 更新UI状态的函数
            function updateImportOriginalAnnotationsUI() {
                const isChecked = importOriginalAnnotationsCheckbox.checked;
                const selectedImageSource = document.querySelector('input[name="image-source"]:checked').value;
                
                // 当选择服务器目录时，导入原标注功能不可用
                if (selectedImageSource === 'directory') {
                    importOriginalAnnotationsCheckbox.disabled = true;
                    // 如果当前已勾选，则取消勾选
                    if (isChecked) {
                        importOriginalAnnotationsCheckbox.checked = false;
                    }
                    // 启用类别输入（因为导入原标注不可用）
                    annotationClassesTextarea.disabled = false;
                    annotationClassesTextarea.required = true;
                    defaultClassesDiv.classList.remove('disabled-area');
                    originalClassesInfo.style.display = 'none';
                } else {
                    // 其他情况：上传ZIP或关联数据集
                    importOriginalAnnotationsCheckbox.disabled = false;
                    
                    // 如果勾选了导入原标注且选择了上传ZIP，则禁用类别输入
                    if (isChecked && selectedImageSource === 'upload') {
                        annotationClassesTextarea.disabled = true;
                        annotationClassesTextarea.required = false;
                        defaultClassesDiv.classList.add('disabled-area');
                        originalClassesInfo.style.display = 'block';
                    } else {
                        annotationClassesTextarea.disabled = false;
                        annotationClassesTextarea.required = true;
                        defaultClassesDiv.classList.remove('disabled-area');
                        originalClassesInfo.style.display = 'none';
                    }
                }
            }
            
            // 初始状态检查
            updateImportOriginalAnnotationsUI();
            
            // 监听导入原标注复选框变化
            importOriginalAnnotationsCheckbox.addEventListener('change', function() {
                updateImportOriginalAnnotationsUI();
            });
            
            // 监听图片来源选择的变化
            imageSourceRadios.forEach(radio => {
                radio.addEventListener('change', function() {
                    updateImportOriginalAnnotationsUI();
                });
            });
        }
    }
    
    // 显示合并标注项目模态框
    showMergeAnnotationProjectsModal() {
        const modalTitle = document.querySelector('.modal-title');
        const modalBody = document.querySelector('.modal-body');
        const modalSubmit = document.getElementById('modalSubmit');

        modalTitle.textContent = '合并标注项目';

        // 获取模板内容
        const template = document.getElementById('merge-annotation-projects-template');
        if (!template) {
            console.error('merge-annotation-projects-template not found');
            return;
        }

        modalBody.innerHTML = template.innerHTML;
        
        // 加载项目列表
        this.loadProjectsForMerge();
        
        // 绑定事件
        this.bindMergeProjectsEvents();

        modal.show();
        
        // 确保提交按钮状态正确
        modalSubmit.disabled = false;
        modalSubmit.textContent = '开始合并';
        modalSubmit.onclick = () => this.submitMergeAnnotationProjects();
    }
    
    // 加载用于合并的项目列表
    loadProjectsForMerge(filterType = '') {
        // 存储项目数据以便后续使用
        this.mergedProjectsData = {};
        
        authenticatedFetch(API_URL + '/annotation/projects/')
            .then(response => response.json())
            .then(projects => {
                const projectsList = document.getElementById('projects-list');
                if (!projectsList) {
                    console.error('projects-list element not found');
                    return;
                }

                // 过滤指定类型的项目
                const filteredProjects = filterType ? 
                    projects.filter(p => p.project_type === filterType) : projects;

                projectsList.innerHTML = '';

                if (filteredProjects.length === 0) {
                    projectsList.innerHTML = '<div class="alert alert-info">没有找到符合条件的项目</div>';
                    return;
                }

                // 存储项目数据以便后续获取图片数量
                filteredProjects.forEach(project => {
                    this.mergedProjectsData[project.id] = project;
                });

                // 为每个项目获取统计信息
                const projectPromises = filteredProjects.map(project => {
                    return authenticatedFetch(API_URL + `/annotation/projects/${project.id}/stats`)
                        .then(response => response.json())
                        .catch(error => {
                            // 如果获取统计信息失败，返回默认值
                            console.warn(`Failed to get stats for project ${project.id}:`, error);
                            return { total_images: 0 };
                        });
                });

                Promise.all(projectPromises)
                    .then(statsArray => {
                        filteredProjects.forEach((project, index) => {
                            const stats = statsArray[index];
                            const projectTypeText = this.getProjectTypeText(project.project_type);
                            
                            const projectItem = document.createElement('div');
                            projectItem.className = 'form-check mb-2';
                            projectItem.innerHTML = '<input class="form-check-input project-checkbox" type="checkbox" value="' + project.id + '" id="project-' + project.id + '" data-total-images="' + (stats?.total_images || 0) + '" data-completed-images="' + (stats?.completed_images || 0) + '">' +
                                '<label class="form-check-label d-flex justify-content-between w-100" for="project-' + project.id + '">' +
                                    '<span>' +
                                        '<strong>' + project.name + '</strong> ' +
                                        '<span class="badge bg-info ms-2">' + projectTypeText + '</span>' +
                                    '</span>' +
                                    '<span class="text-muted">' +
                                        project.classes.length + ' 类别, ' + (stats?.total_images || 0) + ' 图片 (' + (stats?.completed_images || 0) + ' 已标注)' +
                                    '</span>' +
                                '</label>';
                            projectsList.appendChild(projectItem);
                        });
                        
                        // 绑定复选框事件
                        this.bindProjectCheckboxes();
                    })
                    .catch(error => {
                        console.error('Error getting project stats:', error);
                        // 即使获取统计信息失败，也要显示项目列表（使用0作为默认值）
                        filteredProjects.forEach(project => {
                            const projectTypeText = this.getProjectTypeText(project.project_type);
                            
                            const projectItem = document.createElement('div');
                            projectItem.className = 'form-check mb-2';
                            projectItem.innerHTML = '<input class="form-check-input project-checkbox" type="checkbox" value="' + project.id + '" id="project-' + project.id + '" data-total-images="0" data-completed-images="0">' +
                                '<label class="form-check-label d-flex justify-content-between w-100" for="project-' + project.id + '">' +
                                    '<span>' +
                                        '<strong>' + project.name + '</strong> ' +
                                        '<span class="badge bg-info ms-2">' + projectTypeText + '</span>' +
                                    '</span>' +
                                    '<span class="text-muted">' +
                                        project.classes.length + ' 类别, 0 图片 (0 已标注)' +
                                    '</span>' +
                                '</label>';
                            projectsList.appendChild(projectItem);
                        });
                        
                        // 绑定复选框事件
                        this.bindProjectCheckboxes();
                    });
            })
            .catch(error => {
                console.error('Error loading projects for merge:', error);
                const projectsList = document.getElementById('projects-list');
                if (projectsList) {
                    projectsList.innerHTML = '<div class="alert alert-danger">加载项目列表失败</div>';
                }
            });
    }
    
    // 绑定项目复选框事件
    bindProjectCheckboxes() {
        const checkboxes = document.querySelectorAll('.project-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.validateProjectSelection();
            });
        });
    }
    
    // 验证项目选择
    validateProjectSelection() {
        const selectedCheckboxes = document.querySelectorAll('.project-checkbox:checked');
        const modalSubmit = document.getElementById('modalSubmit');
        
        if (selectedCheckboxes.length < 2) {
            // 少于2个项目，禁用合并按钮
            if (modalSubmit) {
                modalSubmit.disabled = true;
            }
            this.updateMergeSummary([]);
            return;
        }
        
        // 获取选中项目的类型
        const selectedTypes = [];
        selectedCheckboxes.forEach(checkbox => {
            const label = checkbox.nextElementSibling;
            const typeBadge = label.querySelector('.badge.bg-info');
            if (typeBadge) {
                // 从badge中获取类型文本，然后映射回实际类型
                const typeText = typeBadge.textContent;
                const typeValue = this.getTypeValueFromText(typeText);
                selectedTypes.push(typeValue);
            }
        });
        
        // 检查所有选中项目是否为同一类型
        const isConsistent = selectedTypes.every(type => type === selectedTypes[0]);
        
        if (!isConsistent) {
            alert('警告：所选项目类型不一致，合并项目必须是同一类型！');
            // 类型不一致也禁用按钮
            if (modalSubmit) {
                modalSubmit.disabled = true;
            }
        } else {
            // 类型一致且选中了至少2个项目，启用按钮
            if (modalSubmit) {
                modalSubmit.disabled = false;
            }
        }
        
        // 更新摘要
        this.updateMergeSummary(Array.from(selectedCheckboxes));
    }
    
    // 从显示文本获取实际类型值
    getTypeValueFromText(typeText) {
        const typeMap = {
            '目标检测': 'detection',
            '实例分割': 'segmentation',
            '旋转框': 'obb',
            '关键点/姿态估计': 'pose'
        };
        return typeMap[typeText] || typeText;
    }
    
    // 更新合并摘要
    updateMergeSummary(selectedCheckboxes) {
        if (selectedCheckboxes.length === 0) {
            document.getElementById('merge-summary').style.display = 'none';
            return;
        }
        
        // 计算选中项目的总数和图片数
        let totalProjects = 0;
        let totalImages = 0;
        
        selectedCheckboxes.forEach(checkbox => {
            totalProjects++;
            
            // 获取项目ID
            const projectId = checkbox.value;
            
            // 从存储的数据中获取图片数量，优先使用data属性，然后是存储的项目数据
            let imgCount = parseInt(checkbox.getAttribute('data-total-images')) || 0;
            
            if (imgCount === 0 && this.mergedProjectsData && this.mergedProjectsData[projectId]) {
                // 如果data属性中的数量为0，尝试从存储的项目数据中获取
                imgCount = this.mergedProjectsData[projectId].stats?.total_images || 0;
            }
            
            totalImages += imgCount;
        });
        
        const summaryContent = document.getElementById('merge-summary-content');
        summaryContent.innerHTML = '<p>将合并 <strong>' + totalProjects + '</strong> 个项目</p>' +
            '<p>总计 <strong>' + totalImages + '</strong> 张图片</p>' +
            '<p>新项目名称: <strong>' + (document.getElementById('target-project-name').value || '未设置') + '</strong></p>' +
            '<p>删除源项目: <strong>' + (document.getElementById('delete-source-projects').checked ? '是' : '否') + '</strong></p>';
        
        document.getElementById('merge-summary').style.display = 'block';
    }
    
    // 绑定合并项目相关事件
    bindMergeProjectsEvents() {
        // 类型筛选事件
        const typeFilter = document.getElementById('project-type-filter');
        if (typeFilter) {
            typeFilter.addEventListener('change', (e) => {
                this.loadProjectsForMerge(e.target.value);
            });
        }
        
        // 刷新按钮事件
        const refreshBtn = document.getElementById('refresh-projects-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                const currentFilter = document.getElementById('project-type-filter').value;
                this.loadProjectsForMerge(currentFilter);
            });
        }
        
        // 新项目名称输入事件
        const targetNameInput = document.getElementById('target-project-name');
        if (targetNameInput) {
            targetNameInput.addEventListener('input', () => {
                const selectedCheckboxes = document.querySelectorAll('.project-checkbox:checked');
                this.updateMergeSummary(selectedCheckboxes);
            });
        }
        
        // 删除源项目复选框事件
        const deleteSourceCheckbox = document.getElementById('delete-source-projects');
        if (deleteSourceCheckbox) {
            deleteSourceCheckbox.addEventListener('change', () => {
                const selectedCheckboxes = document.querySelectorAll('.project-checkbox:checked');
                this.updateMergeSummary(selectedCheckboxes);
            });
        }
    }
    
    // 提交合并标注项目
    submitMergeAnnotationProjects() {
        const selectedCheckboxes = document.querySelectorAll('.project-checkbox:checked');
        
        if (selectedCheckboxes.length < 2) {
            alert('请至少选择2个项目进行合并');
            return;
        }
        
        const targetProjectName = document.getElementById('target-project-name').value.trim();
        if (!targetProjectName) {
            alert('请输入新项目名称');
            return;
        }
        
        // 获取选中的项目ID
        const sourceProjectIds = Array.from(selectedCheckboxes).map(cb => cb.value);
        
        // 检查项目类型一致性
        const selectedTypes = [];
        selectedCheckboxes.forEach(checkbox => {
            const label = checkbox.nextElementSibling;
            const typeBadge = label.querySelector('.badge.bg-info');
            if (typeBadge) {
                const typeText = typeBadge.textContent;
                const typeValue = this.getTypeValueFromText(typeText);
                selectedTypes.push(typeValue);
            }
        });
        
        const isConsistent = selectedTypes.every(type => type === selectedTypes[0]);
        if (!isConsistent) {
            alert('错误：所选项目类型不一致，无法合并！');
            return;
        }
        
        const deleteSourceProjects = document.getElementById('delete-source-projects').checked;
        const duplicateHandling = document.getElementById('duplicate-handling').value;
        
        // 发送合并请求
        const mergeData = {
            target_project_name: targetProjectName,
            source_project_ids: sourceProjectIds,
            delete_source_projects: deleteSourceProjects,
            duplicate_handling: duplicateHandling
        };
        
        // 禁用提交按钮
        const modalSubmit = document.getElementById('modalSubmit');
        modalSubmit.disabled = true;
        modalSubmit.textContent = '合并中...';
        
        authenticatedFetch(API_URL + '/annotation/merge-projects', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(mergeData)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || '合并失败'); });
            }
            return response.json();
        })
        .then(result => {
            // 合并成功
            modal.hide();
            
            // 显示结果
            let message = '合并完成！\n';
            message += '- 创建新项目: ' + result.new_project_name + '\n';
            message += '- 合并了 ' + result.merged_projects_count + ' 个项目\n';
            message += '- 总计 ' + result.total_images_count + ' 张图片\n';
            
            if (result.conflicts && result.conflicts.length > 0) {
                message += '\n警告：发现 ' + result.conflicts.length + ' 个文件名冲突，已自动重命名解决冲突。';
            }
            
            if (deleteSourceProjects) {
                message += '\n已删除原始项目。';
            } else {
                message += '\n保留了原始项目。';
            }
            
            alert(message);
            
            // 刷新项目列表
            this.loadAnnotationProjects();
            
            // 重新启用提交按钮（以防万一）
            modalSubmit.disabled = false;
            modalSubmit.textContent = '开始合并';
        })
        .catch(error => {
            console.error('Error merging annotation projects:', error);
            alert('合并标注项目失败: ' + error.message);
            
            // 重新启用提交按钮
            modalSubmit.disabled = false;
            modalSubmit.textContent = '开始合并';
        });
    }
    
    // 显示扩充数据模态框
    showExpandDataModal(projectId, projectName) {
        const modalTitle = document.querySelector('.modal-title');
        const modalBody = document.querySelector('.modal-body');
        const modalSubmit = document.getElementById('modalSubmit');

        modalTitle.textContent = `为项目扩充数据 - ${projectName}`;

        // 创建扩充数据表单HTML
        const expandFormHtml = `
            <form id="expand-data-form">
                <div class="mb-3">
                    <label for="expand-zip-file" class="form-label">上传ZIP文件</label>
                    <input type="file" class="form-control" id="expand-zip-file" accept=".zip" required>
                    <div class="form-text">支持ZIP格式，包含图片和可选的标注文件</div>
                </div>
                
                <div class="mb-3 form-check">
                    <input type="checkbox" class="form-check-input" id="expand-import-original-annotations">
                    <label class="form-check-label" for="expand-import-original-annotations">
                        保留原标注（如果ZIP中包含标注文件）
                    </label>
                </div>
                
                <div class="mb-3">
                    <div class="progress d-none" id="expand-progress-container">
                        <div class="progress-bar" role="progressbar" style="width: 0%" id="expand-progress-bar"></div>
                    </div>
                    <div class="text-center d-none" id="expand-status"></div>
                </div>
            </form>
        `;
        
        modalBody.innerHTML = expandFormHtml;
        
        // 绑定提交事件
        const submitButton = document.getElementById('modalSubmit');
        submitButton.textContent = '开始扩充';
        submitButton.onclick = () => this.expandProjectData(projectId);
        
        // 显示模态框
        const modalElement = document.getElementById('mainModal');
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    }
    
    // 扩展项目数据
    expandProjectData(projectId) {
        const zipFileInput = document.getElementById('expand-zip-file');
        const importOriginalAnnotationsCheckbox = document.getElementById('expand-import-original-annotations');
        const progressContainer = document.getElementById('expand-progress-container');
        const progressBar = document.getElementById('expand-progress-bar');
        const statusDiv = document.getElementById('expand-status');
        const modalSubmit = document.getElementById('modalSubmit');
        
        const zipFile = zipFileInput.files[0];
        const importOriginalAnnotations = importOriginalAnnotationsCheckbox.checked;
        
        if (!zipFile) {
            alert('请选择ZIP文件');
            return;
        }
        
        if (!zipFile.name.toLowerCase().endsWith('.zip')) {
            alert('请选择ZIP格式的文件');
            return;
        }
        
        // 显示进度
        progressContainer.classList.remove('d-none');
        statusDiv.classList.remove('d-none');
        modalSubmit.disabled = true;
        modalSubmit.textContent = '扩充中...';
        
        const formData = new FormData();
        formData.append('zip_file', zipFile);
        formData.append('import_original_annotations', importOriginalAnnotations);
        
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_URL}/annotation/projects/${projectId}/expand-data`, true);
        
        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progressBar.style.width = percentComplete + '%';
                progressBar.textContent = Math.round(percentComplete) + '%';
                statusDiv.textContent = '上传中...';
            }
        };
        
        xhr.onload = function() {
            // 隐藏进度
            progressContainer.classList.add('d-none');
            statusDiv.classList.add('d-none');
            modalSubmit.disabled = false;
            modalSubmit.textContent = '开始扩充';
            
            if (xhr.status === 200) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    alert(response.message || '项目数据扩充成功！');
                    
                    // 关闭模态框
                    const modalElement = document.getElementById('mainModal');
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) {
                        modal.hide();
                    }
                    
                    // 刷新项目列表
                    onlineAnnotation.loadAnnotationProjects();
                } catch (e) {
                    console.error('解析响应失败:', e);
                    alert('扩充成功，但解析响应失败');
                }
            } else {
                try {
                    const error = JSON.parse(xhr.responseText);
                    alert('扩充失败: ' + (error.detail || '未知错误'));
                } catch (e) {
                    alert('扩充失败: ' + xhr.statusText);
                }
            }
        };
        
        xhr.onerror = function() {
            // 隐藏进度
            progressContainer.classList.add('d-none');
            statusDiv.classList.add('d-none');
            modalSubmit.disabled = false;
            modalSubmit.textContent = '开始扩充';
            
            alert('请求失败，请检查网络连接');
        };
        
        xhr.send(formData);
    }
}

// 创建全局实例
window.onlineAnnotation = new OnlineAnnotation();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OnlineAnnotation;
}
