"""流水线错误类型

PipelineError 带一个稳定的错误码（对外接口和 webhook 里原样返回，调用方可据此做自动处理），
message 面向人，说明发生了什么、建议怎么处理。
"""


class PipelineError(Exception):
    def __init__(self, code: str, message: str, details=None, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        # True 表示环境类问题（网络、GPU 被占用等），重试可能成功
        self.retryable = retryable


class RunCancelled(Exception):
    """用户取消了 Run，各阶段在循环中检查到后抛出"""


class RunPaused(Exception):
    """阶段要求暂停 Run（如 VLM 预算用尽），等待人工处理后继续"""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


# 任务级错误码（对外稳定，新增可以，已有的不要改名）
EXTRACT_FAILED = "extract_failed"            # 所有视频都抽帧失败
NO_USABLE_FRAMES = "no_usable_frames"        # 清洗/标注后没有可用于训练的帧
VLM_UNAVAILABLE = "vlm_unavailable"          # 视觉模型接口不可用（未配置、鉴权失败、持续超时）
GATE_FAILED_HARD = "gate_failed_hard"        # 质量闸门出现无法继续的硬失败（如某类别没有任何可用帧）
REJECTED_BY_OPERATOR = "rejected_by_operator"
DATASET_FAILED = "dataset_failed"
TRAIN_FAILED = "train_failed"
EVALUATE_FAILED = "evaluate_failed"
TFLITE_EXPORT_FAILED = "tflite_export_failed"
TFLITE_VERIFY_FAILED = "tflite_verify_failed"
INTERRUPTED = "interrupted"                  # 服务多次重启都没能跑完
INTERNAL = "internal"
