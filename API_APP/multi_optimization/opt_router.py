from enum import Enum
from pathlib import Path
from typing import Dict, Optional

from fastapi import HTTPException, APIRouter
from pydantic import BaseModel, Field, field_validator

from API_APP.celery_config import cal_multi_opt_task
from API_APP.data_manager import add_task_to_frontend

router = APIRouter(
    prefix="/optimize",
    tags=["optimize"],
    responses={404: {"description": "Not found"}},
)


class VariableRange(BaseModel):
    lower: float
    upper: float

    @field_validator('lower', 'upper')
    def check_bounds(cls, v):
        if not isinstance(v, (int, float)):
            raise ValueError("边界值必须是数字")
        return float(v)


class ObjectiveDirection(str, Enum):
    MAX = "max"
    MIN = "min"


class OptimizationAlgorithm(str, Enum):
    NSGA2 = "nsga2"
    NSGA3 = "nsga3"


class ObjectiveRange(BaseModel):
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    direction: Optional[ObjectiveDirection] = None

    @field_validator('min_value', 'max_value')
    def check_values(cls, value, field_info):
        if field_info.field_name == 'min_value':
            max_value = field_info.data.get('max_value')
            if max_value is not None and value is not None and value > max_value:
                raise ValueError("min_value不能大于max_value")
        return value


class OptimizationRequest(BaseModel):
    variables: Dict[str, VariableRange]
    objective_functions: Dict[str, str]
    objective_ranges: Dict[str, ObjectiveRange]
    algorithm: OptimizationAlgorithm = OptimizationAlgorithm.NSGA2
    population_size: int = Field(500, gt=0)
    generations: int = Field(100, gt=0)

    @field_validator('objective_ranges')
    def check_objective_ranges(cls, value):
        for name, obj_range in value.items():
            if obj_range.direction is None and obj_range.min_value is None and obj_range.max_value is None:
                raise ValueError(f"目标 {name} 必须指定direction或边界约束")
        return value

    @field_validator('objective_ranges')
    def check_at_least_one_direction(cls, value):
        if all(obj_range.direction is None for obj_range in value.values()):
            raise ValueError("至少需要指定一个目标的方向（max或min）")
        return value


@router.post("/")
async def run_optimization(request: OptimizationRequest):
    try:
        if not request.variables:
            raise HTTPException(status_code=400, detail="至少需要定义一个优化变量")
        if set(request.objective_functions.keys()) != set(request.objective_ranges.keys()):
            raise HTTPException(status_code=400, detail="目标函数和目标范围不匹配")
        current_dir = Path(__file__).resolve().parent.parent

        variable_names = list(request.variables.keys())
        opt_target = ", ".join(variable_names)
        description = f"使用全局优化算法 {request.algorithm.value} 进行多目标优化，优化目标为{opt_target}。\
                            计算返回前5个帕累托前沿，具体结果见txt文件。"
        task = cal_multi_opt_task.apply_async(args=[request.model_dump(), str(current_dir)])
        add_task_to_frontend(
            task_id=task.id,
            task_name="多目标优化",
            description=description
        )
        return {"result": "多目标优化任务启动，可在任务运行情况中查看详情"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"启动多目标优化任务发生错误: {str(e)}"
        )
