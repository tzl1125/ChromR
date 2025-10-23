import os
from pathlib import Path
from fastapi import APIRouter
from fastapi import File, UploadFile, Form
from API_APP.data_manager import add_task_to_frontend
from API_APP.celery_config import cal_fg_task

router = APIRouter(
    prefix="/fp-growth",
    tags=["fp-growth"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Not found"}},
)


@router.post("/")
async def fpgrowth(
        min_support: int = Form(default=25, gt=0),
        min_conf: float = Form(default=0.7, gt=0, le=1),
        data_file: UploadFile = File(description="FP-growth data_files file, file_type = csv or xls")
):
    description = f"使用FP-growth算法进行关联规则挖掘，返回的计算结果为txt文件。\
        数据文件名：{data_file.filename}，最小支持度：{min_support}，最小置信度：{min_conf}。"

    current_dir = Path(__file__).resolve().parent.parent
    data_path = f"{current_dir}/temp_files/{data_file.filename.replace('./', '')}"
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, "wb") as f:
        contents = await data_file.read()
        f.write(contents)

    task = cal_fg_task.apply_async(args=[data_path, str(current_dir), min_support, min_conf])
    add_task_to_frontend(
        task_id=task.id,
        task_name="关联规则挖掘",
        description=description
    )

    return {"result": "关联规则挖掘任务启动，可在任务运行情况中查看详情"}
