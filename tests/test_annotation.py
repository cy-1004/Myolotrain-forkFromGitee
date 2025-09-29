#!/usr/bin/env python3
"""
测试标注功能的脚本
"""

import requests
import json

# API基础URL
BASE_URL = "http://localhost:8000/api"

def test_annotation_api():
    """测试标注API"""
    
    # 1. 测试获取标注项目列表
    print("1. 测试获取标注项目列表...")
    response = requests.get(f"{BASE_URL}/annotation/projects/")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        projects = response.json()
        print(f"找到 {len(projects)} 个项目")
        for project in projects:
            print(f"  - {project['name']}: {len(project['classes'])} 个类别")
    else:
        print(f"错误: {response.text}")
    
    # 2. 测试获取模型列表
    print("\n2. 测试获取模型列表...")
    response = requests.get(f"{BASE_URL}/models")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        models = response.json()
        print(f"找到 {len(models)} 个模型")
        for model in models:
            print(f"  - {model['name']}: {model['type']}")
    else:
        print(f"错误: {response.text}")
    
    # 3. 测试创建标注项目
    print("\n3. 测试创建标注项目...")
    project_data = {
        "name": "测试项目",
        "description": "这是一个测试项目",
        "classes": ["car", "person", "bike"],
        "image_directory": "datasets_import/汽车道路（小）/train/images"
    }
    
    response = requests.post(
        f"{BASE_URL}/annotation/projects/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(project_data)
    )
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        project = response.json()
        print(f"项目创建成功: {project['name']} (ID: {project['id']})")
        
        # 4. 测试扫描项目图片
        print(f"\n4. 测试扫描项目图片...")
        response = requests.post(f"{BASE_URL}/annotation/projects/{project['id']}/scan")
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"扫描结果: {result['message']}")
        else:
            print(f"错误: {response.text}")
            
    else:
        print(f"错误: {response.text}")

if __name__ == "__main__":
    test_annotation_api()