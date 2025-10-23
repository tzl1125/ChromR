import os
from enum import Enum
from pathlib import Path

from fastapi import APIRouter
from fastapi import File, UploadFile, Form

from API_APP.celery_config import cal_design_space_task
from API_APP.data_manager import add_task_to_frontend

router = APIRouter(
    prefix="/design-space",
    tags=["design-space"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Not found"}},
)


class DsType(str, Enum):
    type_one = "includeN"
    type_two = "withM"
    type_three = "withoutM"


@router.post("/{ds_type}")
async def design_space_includeN(
        ds_type: DsType,
        mt: int = Form(default=1000, gt=0, description="蒙特卡洛模拟次数"),
        p: float = Form(default=0.1, gt=0, lt=1, description="逐步回归p值"),
        r: float = Form(default=0.1, gt=0, lt=1, description="可接受的风险"),
        YLimits: UploadFile = File(description="Y 轴的范围限制，文件类型 = xlsx"),
        ParameterCondition: UploadFile = File(description="参数条件，文件类型 = xlsx"),
        ExpResults: UploadFile = File(description="实验结果，文件类型 = xlsx"),
        XLimitsSteps: UploadFile = File(description="变量范围和步长，文件类型 = xlsx"),
        MaterialCondition: UploadFile = File(default=None, description="物料属性，文件类型 = xlsx")
):
    if ds_type == "includeN":
        task_name = "设计空间（带噪声参数）"
    elif ds_type == "withM":
        task_name = "设计空间（带物料属性）"
    else:
        task_name = "设计空间（无物料属性）"

    description = f"使用达标概率法计算{task_name}，返回的计算结果为html和xlsx文件，分别为图像和原始数据。\
         计算参数：蒙特卡洛模拟{mt}次，逐步回归p值为{p}，可接受的风险为{r}。"

    files_info = [
        ('YLimits', YLimits),
        ('ParameterCondition', ParameterCondition),
        ('ExpResults', ExpResults),
        ('XLimitsSteps', XLimitsSteps)
    ]
    if ds_type == "withM":
        files_info.append(('MaterialCondition', MaterialCondition))

    current_dir = Path(__file__).resolve().parent.parent
    data_paths = {}
    for key_name, file in files_info:
        data_path = f"{current_dir}/temp_files/{file.filename.replace('./', '')}"
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        with open(data_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
        data_paths[key_name] = data_path

    task = cal_design_space_task.apply_async(args=[data_paths, [mt, p, r], str(current_dir), ds_type])
    add_task_to_frontend(
        task_id=task.id,
        task_name=task_name,
        description=description
    )

    return {"result": f"{task_name}计算任务启动，可在任务运行情况中查看详情"}

@router.post("/noR/{ds_type}")
async def design_space_no_risk(
        ds_type: DsType,
        p: float = Form(default=0.1, gt=0, lt=1, description="逐步回归p值"),
        YLimits: UploadFile = File(description="Y 轴的范围限制，文件类型 = xlsx"),
        ParameterCondition: UploadFile = File(description="参数条件，文件类型 = xlsx"),
        ExpResults: UploadFile = File(description="实验结果，文件类型 = xlsx"),
        XLimitsSteps: UploadFile = File(description="变量范围和步长，文件类型 = xlsx"),
        MaterialCondition: UploadFile = File(default=None, description="物料属性，文件类型 = xlsx")
):
    if ds_type == "includeN":
        task_name = "设计空间（带噪声参数-无概率）"
    elif ds_type == "withM":
        task_name = "设计空间（带物料属性-无概率）"
    else:
        task_name = "设计空间（无物料属性-无概率）"

    description = f"计算{task_name}，直接返回达标和不达标区域，返回的计算结果为html和xlsx文件。\
         计算参数：逐步回归p值为{p}。"

    files_info = [
        ('YLimits', YLimits),
        ('ParameterCondition', ParameterCondition),
        ('ExpResults', ExpResults),
        ('XLimitsSteps', XLimitsSteps)
    ]
    if ds_type == "withM":
        files_info.append(('MaterialCondition', MaterialCondition))

    current_dir = Path(__file__).resolve().parent.parent
    data_paths = {}
    for key_name, file in files_info:
        data_path = f"{current_dir}/temp_files/{file.filename.replace('./', '')}"
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        with open(data_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
        data_paths[key_name] = data_path

    # 传递特殊标识"noR"来区分无概率计算
    task = cal_design_space_task.apply_async(args=[data_paths, [p], str(current_dir), f"{ds_type.value}-noR"])
    add_task_to_frontend(
        task_id=task.id,
        task_name=task_name,
        description=description
    )

    return {"result": f"{task_name}计算任务启动，可在任务运行情况中查看详情"}