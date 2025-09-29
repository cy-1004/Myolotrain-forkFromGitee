import requests
import json

# 测试URL
base_url = "http://localhost:8000"

def test_api_endpoints():
    print("测试模型下载API端点...")
    
    try:
        # 首先获取模型列表，查看是否有可用的模型
        response = requests.get(f"{base_url}/api/models/")
        if response.status_code == 200:
            models = response.json()
            print(f"找到{len(models)}个模型")
            
            if models:
                # 使用第一个模型进行测试
                model_id = models[0]['id']
                model_name = models[0]['name']
                print(f"使用模型测试: {model_name} (ID: {model_id})")
                
                # 测试PT模型下载端点
                pt_url = f"{base_url}/api/models/{model_id}/download/pt"
                print(f"测试PT下载URL: {pt_url}")
                try:
                    pt_response = requests.get(pt_url, stream=True, timeout=10)
                    print(f"PT下载端点响应状态码: {pt_response.status_code}")
                    print(f"PT下载端点响应头: {pt_response.headers}")
                    if pt_response.status_code == 200:
                        print(f"PT下载成功，内容类型: {pt_response.headers.get('content-type')}")
                except requests.exceptions.RequestException as e:
                    print(f"PT下载请求异常: {str(e)}")
                
                # 测试ONNX模型下载端点
                onnx_url = f"{base_url}/api/models/{model_id}/download/onnx"
                print(f"测试ONNX下载URL: {onnx_url}")
                try:
                    print("ONNX模型转换可能需要较长时间，请耐心等待...")
                    onnx_response = requests.get(onnx_url, stream=True, timeout=60)  # 增加超时时间到60秒
                    print(f"ONNX下载端点响应状态码: {onnx_response.status_code}")
                    print(f"ONNX下载端点响应头: {onnx_response.headers}")
                    # 查看错误响应的内容
                    if onnx_response.status_code != 200:
                        try:
                            error_content = onnx_response.json()
                            print(f"错误详情: {error_content}")
                        except:
                            print(f"无法解析错误响应: {onnx_response.text}")
                    else:
                        print(f"ONNX下载成功，内容类型: {onnx_response.headers.get('content-type')}")
                except requests.exceptions.RequestException as e:
                    print(f"ONNX下载请求异常: {str(e)}")
            else:
                print("没有找到可用的模型，请先添加模型")
        else:
            print(f"获取模型列表失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            
        # 尝试访问API文档页面
        docs_response = requests.head(f"{base_url}/docs")
        print(f"API文档页面响应状态码: {docs_response.status_code}")
        
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")

if __name__ == "__main__":
    test_api_endpoints()