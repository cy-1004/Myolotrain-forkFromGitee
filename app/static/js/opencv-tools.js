// OpenCV工具模块
class OpenCVTools {
    constructor() {
        // OpenCV工具相关属性
    }

    // 加载 OpenCV 页面
    loadOpenCVPage() {
        console.log('Loading OpenCV page...');

        // 加载覆盖层已完全移除

        // 确保所有结果区域也是隐藏的
        const resultAreas = [
            'preprocess-result',
            'analyze-result',
            'augment-result'
        ];

        resultAreas.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.style.display = 'none';
            }
        });

        // 加载数据集列表（用于数据增强功能）
        authenticatedFetch(`${API_URL}/datasets/`)
            .then(response => response.json())
            .then(data => {
                console.log('Loaded datasets for OpenCV:', data.length);
                console.log('Dataset data:', data); // 输出数据集数据以进行调试

                const datasetSelect = document.getElementById('dataset-path');
                if (datasetSelect) {
                    // 清空现有选项（除了第一个默认选项）
                    while (datasetSelect.options.length > 1) {
                        datasetSelect.remove(1);
                    }

                    // 添加新选项
                    data.forEach(dataset => {
                        const option = document.createElement('option');
                        // 确保数据集路径存在
                        if (dataset.path) {
                            option.value = dataset.path;
                            option.textContent = dataset.name;
                            datasetSelect.appendChild(option);
                            console.log(`Added dataset option: ${dataset.name} with path: ${dataset.path}`);
                        } else {
                            console.warn(`Dataset ${dataset.name} has no path property`);
                        }
                    });

                    // 如果没有数据集，显示提示
                    if (datasetSelect.options.length <= 1) {
                        const option = document.createElement('option');
                        option.value = "";
                        option.textContent = "没有可用的数据集";
                        option.disabled = true;
                        datasetSelect.appendChild(option);
                    }
                } else {
                    console.error('dataset-path select element not found');
                }
            })
            .catch(error => {
                console.error('加载数据集失败:', error);

                // 在出错时添加错误选项
                const datasetSelect = document.getElementById('dataset-path');
                if (datasetSelect) {
                    const option = document.createElement('option');
                    option.value = "";
                    option.textContent = "加载数据集失败";
                    option.disabled = true;
                    datasetSelect.appendChild(option);
                }
            });
    }

    // 绑定 OpenCV 页面事件
    bindOpenCVEvents() {
        console.log('Binding OpenCV events...');

        // 确保加载覆盖层是隐藏的
        const loadingOverlay = document.getElementById('opencv-loading-overlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }

        // 使用setTimeout确保DOM元素已经加载
        setTimeout(() => {
            console.log('Delayed binding of OpenCV events...');
            this.bindOpenCVEventHandlers();
        }, 500);
    }

    // 实际绑定事件处理程序
    bindOpenCVEventHandlers() {
        // 图像预处理相关脚本
        // 显示/隐藏选项
        const resizeCheck = document.getElementById('resize-check');
        const resizeOptions = document.getElementById('resize-options');
        if (resizeCheck && resizeOptions) {
            resizeCheck.addEventListener('change', function() {
                resizeOptions.style.display = this.checked ? 'block' : 'none';
            });
        }

        const denoiseCheck = document.getElementById('denoise-check');
        const denoiseOptions = document.getElementById('denoise-options');
        if (denoiseCheck && denoiseOptions) {
            denoiseCheck.addEventListener('change', function() {
                denoiseOptions.style.display = this.checked ? 'block' : 'none';
            });
        }

        const brightnessContrastCheck = document.getElementById('brightness-contrast-check');
        const brightnessContrastOptions = document.getElementById('brightness-contrast-options');
        if (brightnessContrastCheck && brightnessContrastOptions) {
            brightnessContrastCheck.addEventListener('change', function() {
                brightnessContrastOptions.style.display = this.checked ? 'block' : 'none';
            });
        }

        const sharpenCheck = document.getElementById('sharpen-check');
        const sharpenOptions = document.getElementById('sharpen-options');
        if (sharpenCheck && sharpenOptions) {
            sharpenCheck.addEventListener('change', function() {
                sharpenOptions.style.display = this.checked ? 'block' : 'none';
            });
        }

        // 更新滑块值显示
        const denoiseStrength = document.getElementById('denoise-strength');
        if (denoiseStrength) {
            denoiseStrength.addEventListener('input', function() {
                document.getElementById('denoise-strength-value').textContent = this.value;
            });
        }

        const brightness = document.getElementById('brightness');
        if (brightness) {
            brightness.addEventListener('input', function() {
                document.getElementById('brightness-value').textContent = this.value;
            });
        }

        const contrast = document.getElementById('contrast');
        if (contrast) {
            contrast.addEventListener('input', function() {
                document.getElementById('contrast-value').textContent = (this.value / 10).toFixed(1);
            });
        }

        const sharpenAmount = document.getElementById('sharpen-amount');
        if (sharpenAmount) {
            sharpenAmount.addEventListener('input', function() {
                document.getElementById('sharpen-amount-value').textContent = (this.value / 10).toFixed(1);
            });
        }

        // 绑定表单提交事件
        // 1. 预处理表单
        const preprocessForm = document.getElementById('preprocess-form');
        if (preprocessForm) {
            preprocessForm.addEventListener('submit', (event) => {
                // 阻止表单的默认提交行为
                event.preventDefault();
                console.log('Process image button clicked');

                const imageFile = document.getElementById('image-upload').files[0];
                if (!imageFile) {
                    alert('请选择图像文件');
                    return;
                }

                // 构建操作列表
                const operations = [];

                if (document.getElementById('resize-check').checked) {
                    operations.push({
                        name: 'resize_image',
                        params: {
                            width: parseInt(document.getElementById('resize-width').value),
                            height: parseInt(document.getElementById('resize-height').value)
                        }
                    });
                }

                if (document.getElementById('denoise-check').checked) {
                    operations.push({
                        name: 'denoise_image',
                        params: {
                            strength: parseInt(document.getElementById('denoise-strength').value)
                        }
                    });
                }

                if (document.getElementById('brightness-contrast-check').checked) {
                    operations.push({
                        name: 'adjust_brightness_contrast',
                        params: {
                            brightness: parseInt(document.getElementById('brightness').value),
                            contrast: parseFloat(document.getElementById('contrast').value) / 10
                        }
                    });
                }

                if (document.getElementById('sharpen-check').checked) {
                    operations.push({
                        name: 'sharpen_image',
                        params: {
                            amount: parseFloat(document.getElementById('sharpen-amount').value) / 10
                        }
                    });
                }

                if (operations.length === 0) {
                    alert('请至少选择一个预处理操作');
                    return;
                }

                // 创建表单数据
                const formData = new FormData();
                formData.append('image', imageFile);
                formData.append('operations', JSON.stringify(operations));

                // 显示原始图像
                const originalImage = document.getElementById('original-image');
                const reader = new FileReader();
                reader.onload = function(e) {
                    originalImage.src = e.target.result;
                };
                reader.readAsDataURL(imageFile);

                // 发送请求
                authenticatedFetch(`${API_URL}/opencv/preprocess`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || '处理图像失败'); });
                    }
                    return response.blob();
                })
                .then(blob => {
                    // 显示处理后的图像
                    const processedImage = document.getElementById('processed-image');
                    const downloadLink = document.getElementById('download-processed');

                    const url = window.memoryManager.createObjectURL(blob);
                    processedImage.src = url;
                    downloadLink.href = url;
                    downloadLink.download = 'processed_' + imageFile.name;
                    
                    // 在图像加载完成后释放旧URL（如果有）
                    processedImage.onload = function() {
                        // 延迟释放，确保图像已加载
                        setTimeout(() => {
                            if (processedImage.dataset.oldUrl) {
                                window.memoryManager.revokeObjectURL(processedImage.dataset.oldUrl);
                            }
                            processedImage.dataset.oldUrl = url;
                        }, 1000);
                    };

                    // 显示结果区域
                    document.getElementById('preprocess-result').style.display = 'block';
                })
                .catch(error => {
                    alert('错误: ' + error.message);
                });
            });
        }

        // 2. 图像分割表单
        const segmentationMethod = document.getElementById('segmentation-method');
        if (segmentationMethod) {
            segmentationMethod.addEventListener('change', function() {
                const numSegmentsContainer = document.getElementById('num-segments-container');
                numSegmentsContainer.style.display = this.value === 'kmeans' ? 'block' : 'none';
            });
        }

        const segmentationForm = document.getElementById('segmentation-form');
        if (segmentationForm) {
            segmentationForm.addEventListener('submit', (event) => {
                // 阻止表单的默认提交行为
                event.preventDefault();
                console.log('Segment image button clicked');

                const imageFile = document.getElementById('segmentation-image-upload').files[0];
                if (!imageFile) {
                    alert('请选择图像文件');
                    return;
                }

                // 创建表单数据
                const formData = new FormData();
                formData.append('image', imageFile);
                formData.append('method', document.getElementById('segmentation-method').value);
                formData.append('num_segments', document.getElementById('num-segments').value);

                // 显示原始图像
                const originalImage = document.getElementById('original-segmentation-image');
                const reader = new FileReader();
                reader.onload = function(e) {
                    originalImage.src = e.target.result;
                };
                reader.readAsDataURL(imageFile);

                // 发送请求
                authenticatedFetch(`${API_URL}/opencv/segment-image`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || '图像分割失败'); });
                    }
                    return response.blob();
                })
                .then(blob => {
                    // 显示分割后的图像
                    const segmentedImage = document.getElementById('segmented-image');
                    const downloadLink = document.getElementById('download-segmented');

                    const url = window.memoryManager.createObjectURL(blob);
                    segmentedImage.src = url;
                    downloadLink.href = url;
                    downloadLink.download = 'segmented_' + imageFile.name;
                    
                    // 在图像加载完成后释放旧URL（如果有）
                    segmentedImage.onload = function() {
                        // 延迟释放，确保图像已加载
                        setTimeout(() => {
                            if (segmentedImage.dataset.oldUrl) {
                                window.memoryManager.revokeObjectURL(segmentedImage.dataset.oldUrl);
                            }
                            segmentedImage.dataset.oldUrl = url;
                        }, 1000);
                    };

                    // 显示结果区域
                    document.getElementById('segmentation-result').style.display = 'block';
                })
                .catch(error => {
                    alert('错误: ' + error.message);
                });
            });
        }

        // 3. 特征提取表单
        const extractFeaturesForm = document.getElementById('extract-features-form');
        if (extractFeaturesForm) {
            extractFeaturesForm.addEventListener('submit', (event) => {
                // 阻止表单的默认提交行为
                event.preventDefault();
                console.log('Extract features button clicked');

                const imageFile = document.getElementById('features-image-upload').files[0];
                if (!imageFile) {
                    alert('请选择图像文件');
                    return;
                }

                // 创建表单数据
                const formData = new FormData();
                formData.append('image', imageFile);
                formData.append('method', document.getElementById('feature-method').value);
                formData.append('max_features', document.getElementById('max-features').value);

                // 发送请求
                authenticatedFetch(`${API_URL}/opencv/extract-features`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || '特征提取失败'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 显示特征提取结果
                    if (data) {
                        document.getElementById('features-image').src = data.result_image || '';
                        document.getElementById('feature-count').textContent = data.feature_count || '0';
                        document.getElementById('feature-method-used').textContent = data.method || '';
                    } else {
                        console.error('特征提取响应数据格式错误:', data);
                    }

                    // 显示结果区域
                    document.getElementById('extract-features-result').style.display = 'block';
                })
                .catch(error => {
                    alert('错误: ' + error.message);
                });
            });
        }

        // 4. 特征匹配表单
        const matchFeaturesForm = document.getElementById('match-features-form');
        if (matchFeaturesForm) {
            matchFeaturesForm.addEventListener('submit', (event) => {
                // 阻止表单的默认提交行为
                event.preventDefault();
                console.log('Match features button clicked');

                const image1File = document.getElementById('match-image1-upload').files[0];
                const image2File = document.getElementById('match-image2-upload').files[0];
                if (!image1File || !image2File) {
                    alert('请选择两张图像文件');
                    return;
                }

                // 创建表单数据
                const formData = new FormData();
                formData.append('image1', image1File);
                formData.append('image2', image2File);
                formData.append('method', document.getElementById('match-feature-method').value);
                formData.append('max_features', document.getElementById('match-max-features').value);
                formData.append('match_method', document.getElementById('match-method').value);

                // 发送请求
                authenticatedFetch(`${API_URL}/opencv/match-features`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || '特征匹配失败'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 显示特征匹配结果
                    if (data) {
                        document.getElementById('matches-image').src = data.result_image || '';
                        document.getElementById('match-count').textContent = data.match_count || '0';
                        document.getElementById('feature-count1').textContent = data.feature_count1 || '0';
                        document.getElementById('feature-count2').textContent = data.feature_count2 || '0';
                        document.getElementById('match-feature-method-used').textContent = data.method || '';
                        document.getElementById('match-method-used').textContent = data.match_method || '';
                    } else {
                        console.error('特征匹配响应数据格式错误:', data);
                    }

                    // 显示结果区域
                    document.getElementById('match-features-result').style.display = 'block';
                })
                .catch(error => {
                    alert('错误: ' + error.message);
                });
            });
        }

        // 5. 数据增强表单
        const augmentForm = document.getElementById('augment-form');
        if (augmentForm) {
            augmentForm.addEventListener('submit', (event) => {
                // 阻止表单的默认提交行为
                event.preventDefault();
                console.log('Augment button clicked');

                const datasetPath = document.getElementById('dataset-path').value;
                if (!datasetPath) {
                    alert('请选择数据集');
                    return;
                }

                // 构建增强选项
                const augmentationOptions = {
                    flip: document.getElementById('flip-check').checked,
                    rotate: document.getElementById('rotate-check').checked ? {
                        angles: [90, 180, 270]
                    } : false,
                    noise: document.getElementById('noise-check').checked ? {
                        types: ['gaussian'],
                        amount: 0.05
                    } : false,
                    brightness_contrast: document.getElementById('brightness-contrast-aug-check').checked ? {
                        brightness: [-20, 20],
                        contrast: [0.8, 1.2]
                    } : false,
                    perspective: document.getElementById('perspective-check').checked,
                    perspective_strength: 0.2
                };

                // 创建表单数据
                const formData = new FormData();
                formData.append('dataset_path', datasetPath);
                formData.append('augmentation_options', JSON.stringify(augmentationOptions));
                formData.append('multiplier', document.getElementById('multiplier').value);

                // 加载提示已禁用
                // document.getElementById('opencv-loading-overlay').style.display = 'block';
                // document.getElementById('opencv-loading-text').textContent = '正在准备数据增强...';
                // document.getElementById('opencv-loading-details').textContent = '请稍候，正在准备数据集并启动增强任务';

                // 发送请求
                authenticatedFetch(`${API_URL}/opencv/augment-dataset`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || '启动数据增强任务失败'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 显示任务信息
                    if (data) {
                        document.getElementById('augmentation-id').textContent = data.augmentation_id || '';
                        document.getElementById('output-dir').textContent = data.output_dir || '';
                    } else {
                        console.error('数据增强响应数据格式错误:', data);
                        document.getElementById('augmentation-id').textContent = '未知';
                        document.getElementById('output-dir').textContent = '未知';
                    }

                    // 显示结果区域
                    document.getElementById('augment-result').style.display = 'block';
                    document.getElementById('augment-stats').style.display = 'none';

                    // 加载提示已禁用
                    // document.getElementById('opencv-loading-overlay').style.display = 'none';

                    // 开始轮询任务状态
                    const augmentationId = data.augmentation_id;
                    const statusInterval = window.memoryManager.setInterval(() => {
                        authenticatedFetch(`${API_URL}/opencv/augmentation-status/${augmentationId}`)
                        .then(response => response.json())
                        .then(statusData => {
                            if (statusData) {
                                document.getElementById('augment-status-text').textContent = statusData.status || '未知';

                                if (statusData.status === 'completed' && statusData.stats) {
                                    window.memoryManager.clearInterval(statusInterval);
                                    document.getElementById('augment-progress').style.width = '100%';

                                    // 显示统计信息
                                    document.getElementById('original-images-count').textContent = statusData.stats.original_images || '0';
                                    document.getElementById('augmented-images-count').textContent = statusData.stats.augmented_images || '0';
                                    document.getElementById('total-images-count').textContent = statusData.stats.total_images || '0';

                                    // 显示应用的增强
                                    const appliedAugmentations = document.getElementById('applied-augmentations');
                                    appliedAugmentations.innerHTML = '';

                                    if (statusData.stats.augmentations_applied) {
                                        for (const [key, value] of Object.entries(statusData.stats.augmentations_applied)) {
                                            const li = document.createElement('li');
                                            li.textContent = `${key}: ${value} 张图像`;
                                            appliedAugmentations.appendChild(li);
                                        }
                                    }

                                    document.getElementById('augment-stats').style.display = 'block';
                                } else if (statusData.status === 'failed') {
                                    window.memoryManager.clearInterval(statusInterval);
                                    document.getElementById('augment-progress').style.width = '100%';
                                    document.getElementById('augment-progress').classList.remove('bg-info');
                                    document.getElementById('augment-progress').classList.add('bg-danger');
                                    document.getElementById('augment-status-text').textContent = '失败: ' + statusData.error;
                                } else {
                                    // 更新进度条
                                    document.getElementById('augment-progress').style.width = '50%';
                                }
                            }
                        })
                        .catch(error => {
                            console.error('获取任务状态失败:', error);
                            // 在多次失败后停止轮询
                            window.memoryManager.clearInterval(statusInterval);
                        });
                    }, 2000);
                })
                .catch(error => {
                    // 加载提示已禁用
                    // document.getElementById('opencv-loading-overlay').style.display = 'none';
                    alert('错误: ' + error.message);
                });
            });
        }

        // 高级数据增强相关事件

        // CutMix Alpha 参数滑块
        const cutmixAlpha = document.getElementById('cutmix-alpha');
        const cutmixAlphaValue = document.getElementById('cutmix-alpha-value');
        if (cutmixAlpha && cutmixAlphaValue) {
            cutmixAlpha.addEventListener('input', function() {
                cutmixAlphaValue.textContent = this.value;
            });
        }

        // MixUp Alpha 参数滑块
        const mixupAlpha = document.getElementById('mixup-alpha');
        const mixupAlphaValue = document.getElementById('mixup-alpha-value');
        if (mixupAlpha && mixupAlphaValue) {
            mixupAlpha.addEventListener('input', function() {
                mixupAlphaValue.textContent = this.value;
            });
        }

        // 天气强度滑块
        const weatherIntensity = document.getElementById('weather-intensity');
        const weatherIntensityValue = document.getElementById('weather-intensity-value');
        if (weatherIntensity && weatherIntensityValue) {
            weatherIntensity.addEventListener('input', function() {
                weatherIntensityValue.textContent = this.value;
            });
        }

        // CutMix 表单提交
        const cutmixForm = document.getElementById('cutmix-form');
        if (cutmixForm) {
            cutmixForm.addEventListener('submit', (event) => {
                event.preventDefault();

                // 获取表单数据
                const formData = new FormData(event.target);

                // 显示原始图像
                const image1 = document.getElementById('cutmix-image1').files[0];
                const image2 = document.getElementById('cutmix-image2').files[0];

                if (!image1 || !image2) {
                    alert('请选择两张图像');
                    return;
                }

                // 显示原始图像预览
                const reader1 = new FileReader();
                reader1.onload = function(e) {
                    document.getElementById('cutmix-original1').src = e.target.result;
                };
                reader1.readAsDataURL(image1);

                const reader2 = new FileReader();
                reader2.onload = function(e) {
                    document.getElementById('cutmix-original2').src = e.target.result;
                };
                reader2.readAsDataURL(image2);

                // 发送请求
                authenticatedFetch(`${API_URL}/opencv/advanced-augmentation`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || 'CutMix 增强失败'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 显示结果
                    document.getElementById('cutmix-result').style.display = 'block';
                    document.getElementById('cutmix-output').src = data.output_path;
                    document.getElementById('download-cutmix').href = data.output_path;
                })
                .catch(error => {
                    alert('错误: ' + error.message);
                });
            });
        }

        // MixUp 表单提交
        const mixupForm = document.getElementById('mixup-form');
        if (mixupForm) {
            mixupForm.addEventListener('submit', (event) => {
                event.preventDefault();

                // 获取表单数据
                const formData = new FormData(event.target);

                // 显示原始图像
                const image1 = document.getElementById('mixup-image1').files[0];
                const image2 = document.getElementById('mixup-image2').files[0];

                if (!image1 || !image2) {
                    alert('请选择两张图像');
                    return;
                }

                // 显示原始图像预览
                const reader1 = new FileReader();
                reader1.onload = function(e) {
                    document.getElementById('mixup-original1').src = e.target.result;
                };
                reader1.readAsDataURL(image1);

                const reader2 = new FileReader();
                reader2.onload = function(e) {
                    document.getElementById('mixup-original2').src = e.target.result;
                };
                reader2.readAsDataURL(image2);

                // 发送请求
                authenticatedFetch(`${API_URL}/opencv/advanced-augmentation`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || 'MixUp 增强失败'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 显示结果
                    document.getElementById('mixup-result').style.display = 'block';
                    document.getElementById('mixup-output').src = data.output_path;
                    document.getElementById('download-mixup').href = data.output_path;
                })
                .catch(error => {
                    alert('错误: ' + error.message);
                });
            });
        }

        // Mosaic 表单提交
        const mosaicForm = document.getElementById('mosaic-form');
        if (mosaicForm) {
            mosaicForm.addEventListener('submit', (event) => {
                event.preventDefault();

                // 获取表单数据
                const formData = new FormData(event.target);

                // 检查是否选择了四张图像
                const image1 = document.getElementById('mosaic-image1').files[0];
                const image2 = document.getElementById('mosaic-image2').files[0];
                const image3 = document.getElementById('mosaic-image3').files[0];
                const image4 = document.getElementById('mosaic-image4').files[0];

                if (!image1 || !image2 || !image3 || !image4) {
                    alert('请选择四张图像');
                    return;
                }

                // 发送请求
                authenticatedFetch(`${API_URL}/opencv/advanced-augmentation`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || 'Mosaic 增强失败'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 显示结果
                    document.getElementById('mosaic-result').style.display = 'block';
                    document.getElementById('mosaic-output').src = data.output_path;
                    document.getElementById('download-mosaic').href = data.output_path;
                })
                .catch(error => {
                    alert('错误: ' + error.message);
                });
            });
        }

        // 天气模拟表单提交
        const weatherForm = document.getElementById('weather-form');
        if (weatherForm) {
            weatherForm.addEventListener('submit', (event) => {
                event.preventDefault();

                // 获取表单数据
                const formData = new FormData(event.target);

                // 显示原始图像
                const image = document.getElementById('weather-image').files[0];

                if (!image) {
                    alert('请选择图像');
                    return;
                }

                // 显示原始图像预览
                const reader = new FileReader();
                reader.onload = function(e) {
                    document.getElementById('weather-original').src = e.target.result;
                };
                reader.readAsDataURL(image);

                // 发送请求
                authenticatedFetch(`${API_URL}/opencv/advanced-augmentation`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || '天气模拟增强失败'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 显示结果
                    document.getElementById('weather-result').style.display = 'block';
                    document.getElementById('weather-output').src = data.output_path;
                    document.getElementById('download-weather').href = data.output_path;
                })
                .catch(error => {
                    alert('错误: ' + error.message);
                });
            });
        }

        console.log('OpenCV events bound successfully');

        // 添加调试信息
        console.log('Process image button:', document.getElementById('process-image-btn'));
        console.log('Segment image button:', document.getElementById('segment-image-btn'));
        console.log('Extract features button:', document.getElementById('extract-features-btn'));
        console.log('Match features button:', document.getElementById('match-features-btn'));
        console.log('Augment button:', document.getElementById('augment-btn'));
    }
}

// 创建全局实例
window.opencvTools = new OpenCVTools();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OpenCVTools;
}