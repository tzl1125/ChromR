from typing import Annotated

from fastapi import File, UploadFile, Form, HTTPException, Body, Query
from fastapi.responses import FileResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
import json
import asyncio

from starlette.staticfiles import StaticFiles

from API_APP.celery_app import celery_app
from API_APP.data_manager import *
from Fp_growth import fg_router
from design_space import design_space_router
from stepwise_regress import sr_router
from multi_optimization import opt_router
from literature_search import scopus_router, arxiv_router, pubmed_router

app = FastAPI()
# 定义路由器列表
routers = [
    fg_router.router,
    design_space_router.router,
    scopus_router.router,
    arxiv_router.router,
    pubmed_router.router,
    sr_router.router,
    opt_router.router,
]
for router in routers:
    app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)
hardware_ip = 'xxxx'  # 硬件服务器ip地址


@app.post("/heartbeat")
async def receive_heartbeat(
        ip: Annotated[str, Body(..., embed=True)],
):
    global hardware_ip
    # 更新硬件ip地址
    hardware_ip = ip
    return {"status": "success", "message": "心跳包已接收"}


@app.get("/hardware-ip")
async def get_hardware_ip():
    global hardware_ip
    return {"result": hardware_ip}


@app.get("/download")
async def download_file(file_name: str):
    headers = {'Content-Disposition': f'attachment; filename="{file_name}"'}
    return FileResponse(path=f'data_files/{file_name}', filename=file_name, headers=headers,
                        media_type='application/octet-stream')


@app.delete("/delete_task/{task_id}")
async def delete_task(task_id: str):
    try:
        # 终止 Celery 任务
        celery_app.control.revoke(
            task_id,
            terminate=True,  # 强制终止正在执行的任务
            signal='SIGTERM',  # 发送终止信号
            timeout=5  # 超时时间
        )
        # 从 Redis 中删除任务
        data = get_frontend_data()  # 从 Redis 获取当前数据
        remaining_tasks = [task for task in data.tasks if task.id != task_id]
        if len(remaining_tasks) == len(data.tasks):
            raise HTTPException(status_code=404, detail="Task not found")

        # 更新数据并保存回 Redis
        data.tasks = remaining_tasks
        save_frontend_data(data)

        from celery.result import AsyncResult
        result = AsyncResult(task_id, app=celery_app)
        result.forget()  # 从结果后端中删除任务结果

        return {"message": f"任务 {task_id} 已终止并删除"}

    except HTTPException as he:
        raise he  # 传递已抛出的404错误
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"删除任务时发生错误: {str(e)}"
        )


@app.post("/create_ExpDesign")
async def create_exp_design(exps: list[ExperimentCreateRequest], description: Annotated[str, Body(...)],
                            exp_designs: Annotated[list, Body(...)]):
    """
    根据实验设计来批量创建实验
    :param exps: 实验创建请求列表，每个元素的值是一个实验创建所需数据的pydantic模型
    :param description: 实验设计描述
    :param exp_designs: 实验设计表，每一个元素是实验设计表中的一个实验
    """
    exp_design_info = {}
    exp_ids = []
    for exp, exp_design in zip(exps, exp_designs):
        exp_id = await create_experiment(exp)
        if exp_id == 0:
            raise HTTPException(status_code=400, detail="Failed to create experiment")
        exp_design_info[f'{exp_id}'] = exp_design
        exp_ids.append(exp_id)
    exp_design_id = await create_experiment_design(exp_design_info, description)

    return {'result': f"实验设计表创建成功,实验设计表id：{exp_design_id}  实验ids：{exp_ids}"}


@app.post('/createExp')
async def create_exp(exp_record: ExperimentCreateRequest):
    try:
        new_exp = await create_experiment(exp_record)
        return {'new_exp': new_exp}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建实验失败: {str(e)}")


@app.delete("/delete_record/{experiment_id}")
async def delete_record(experiment_id: int):
    try:
        await delete_records(experiment_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"删除记录时发生错误: {str(e)}"
        )


@app.get('/sse')
async def sse_state():
    async def sse_state_generator():
        while True:
            await asyncio.sleep(3)
            data = get_frontend_data().model_dump()

            # 封装任务数据
            tasks_data = {
                "type": "tasks",
                "payload": data['tasks']
            }
            yield ServerSentEvent(
                data=json.dumps(tasks_data)
            )
            # 封装日志数据
            logs = await fetch_logs()
            logs_data = {
                "type": "logs",
                "payload": logs
            }
            yield ServerSentEvent(
                data=json.dumps(logs_data)
            )
            # 封装实验记录数据
            records = await fetch_records()
            records_data = {
                "type": "records",
                "payload": records
            }
            yield ServerSentEvent(
                data=json.dumps(records_data)
            )

            # 封装实验设计记录数据
            exp_design_records = await fetch_exp_design()
            exp_design_data = {
                "type": "exp_design",
                "payload": exp_design_records
            }
            yield ServerSentEvent(
                data=json.dumps(exp_design_data)
            )

    return EventSourceResponse(sse_state_generator())


@app.get('/data/{experiment_id}')
async def get_data(experiment_id: int = 0, uv_last_timestamp: str = None,
                   nir_last_timestamp: str = None, sensor_last_timestamp: str = None):
    try:
        # 各个数据库数据
        sensors_result = await fetch_data("Sensors", experiment_id=experiment_id, last_timestamp=sensor_last_timestamp)
        uv_result = await fetch_data("UVs", experiment_id=experiment_id, last_timestamp=uv_last_timestamp)
        nir_result = await fetch_data("NIRs", experiment_id=experiment_id, last_timestamp=nir_last_timestamp)

        data = {
            "sensors": sensors_result,
            "uv": uv_result,
            "nir": nir_result
        }
        return data

    except HTTPException as he:
        # 直接重新抛出或记录
        raise he
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="服务器内部错误")


# # 子 FastAPI 应用（专门处理前端页面和静态文件）
# frontend_app = FastAPI()
#
# # 挂载整个前端目录到子应用的根路径 /
# frontend_app.mount("/", StaticFiles(directory="../frontend", html=True))
#
# @frontend_app.get("/")
# async def read_index():
#     return FileResponse("../frontend/index.html")
#
# app.mount("/chrom-robot", frontend_app) # ../frontend 内文件通过/chrom-robot访问

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
