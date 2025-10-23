from enum import Enum
from typing import List

from pydantic import BaseModel


class UvType(str, Enum):
    TYPE_A = "lamp"  # 氙灯开关
    TYPE_B = "average_times"  # 平均次数
    TYPE_C = "integration_time"  # 积分时间
    TYPE_D = "set_background"  # 设置暗背景
    TYPE_E = "set_reference"  # 设置参比


class NirType(str, Enum):
    TYPE_A = "average_times"  # 平均次数
    TYPE_B = "set_background"  # 设置暗背景
    TYPE_C = "set_reference"  # 设置参比


class SystemType(str, Enum):
    TYPE_A = "stop_exp"  # 停止实验运行，实验id自动切换为0
    TYPE_B = "run_exp"  # 获取实验id自动化运行


class PumpType(str, Enum):
    TYPE_A = "speed"  # 转速
    TYPE_B = "direction"  # 方向
    TYPE_C = "start_stop"  # 启停
    TYPE_D = "drain"  # 排空
    TYPE_E = "alias"


class ValveType(str, Enum):
    TYPE_A = "opening"  # 开度
    TYPE_B = "alias"


class System(BaseModel):
    type: SystemType
    experiment: int | None = None


class Uv(BaseModel):
    type: UvType
    value: int | bool | None = None


class Nir(BaseModel):
    type: NirType
    value: int | None = None


class Pump(BaseModel):
    type: PumpType
    value: float | bool | str
    pump_ids: List[int] | str


class Valve(BaseModel):
    type: ValveType
    value: float | str
    valve_ids: List[int] | str


class SystemParamsType(str, Enum):
    TYPE_A = "sample_span_run"  # 实验时采样间隔
    TYPE_B = "sample_span_stop"  # 非实验时采样间隔
    TYPE_C = "lc_span"  # 液位控制间隔
    TYPE_D = "equilibrium_check_span"  # 平衡检查窗口
    TYPE_E = "sensor_thresholds"  # 传感器阈值
    TYPE_F = "stage_constraints"  # 阶段约束
    TYPE_G = "spectral_threshold"  # 光谱阈值
    TYPE_H = "pca_components"  # PCA主成分数量


class SystemParams(BaseModel):
    type: SystemParamsType
    value: dict | float | int
