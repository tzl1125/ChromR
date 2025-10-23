import json
from datetime import datetime
from typing import List

import redis
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy import text

from mysql import AsyncDBSession

# 连接Redis
r = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)  # 自动解码为字符串


class Task(BaseModel):
    id: str
    time: str
    name: str
    status: str
    description: str = ''
    result: str = ''


class FrontendData(BaseModel):
    tasks: List[Task]


# 实验记录数据模型
class ExperimentCreateRequest(BaseModel):
    """
    control_command 字段示例
    {
      "feed_flow": 2.5,           // 上样流量 (BV/h)
      "feed_time": 1.0,           // 上样时间 (h)
      "wash_flow": 3.0,           // 洗涤流量 (BV/h)
      "wash_time": 0.5,           // 洗涤时间 (h)
      "elute_flow": 4.0,          // 洗脱流量 (BV/h)
      "elute_time": 2.0,          // 洗脱时间 (h)
      "refresh_flow": 2.0,        // 再生流量 (BV/h)
      "equilibrate_flow": 1.5,    // 平衡流量 (BV/h)
      "fraction": "F1"     // 馏分配置 (对应 HardwareConfig.out 中的 key)
    }
    """
    control_command: dict = Field(..., description="柱层析控制指令")  # 必填
    feed_number: str = Field(..., description="上样液批次", max_length=50)

    phase_wash: str = Field(..., description="洗涤溶剂", max_length=50)
    phase_elute: str = Field(..., description="洗脱溶剂", max_length=50)
    phase_refresh: str = Field(..., description="再生溶剂", max_length=50)
    phase_equilibrate: str = Field(..., description="平衡溶剂", max_length=50)
    resin: str = Field(..., description="树脂型号", max_length=50)

    column_height: float = Field(..., description="柱高 (cm)", gt=0)  # 必填
    column_inner_diameter: float = Field(..., description="柱内径 (cm)", gt=0)
    bed_height: float = Field(..., description="床层高度 (cm)", gt=0)
    liquid_height: float = Field(..., description="液面高度 (cm)", gt=0)


def get_frontend_data() -> FrontendData:
    # 从Redis获取数据并反序列化
    data = r.get("frontend_data")
    if data:
        return FrontendData.model_validate_json(data)
    else:
        return FrontendData(tasks=[])


def save_frontend_data(data: FrontendData):
    # 序列化并保存到Redis
    r.set("frontend_data", data.model_dump_json())


def add_task_to_frontend(task_id: str, task_name: str, description: str):
    data = get_frontend_data()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_task = Task(
        id=task_id,
        time=current_time,
        name=task_name,
        status="进行中",
        description=description,
        result=""
    )
    data.tasks.append(new_task)
    save_frontend_data(data)  # 保存到Redis
    print(f"{current_time}  新增后台任务   任务id：{task_id}  目前任务数：{len(data.tasks)}")


async def fetch_data(table_name, experiment_id=0, limit=100, last_timestamp=None):
    async with AsyncDBSession() as session:
        # 先检查实验是否存在，实验ID为0时跳过检查
        if experiment_id != 0:
            query = text("SELECT * FROM ExperimentRecords WHERE ID = :experiment_id")
            result = await session.execute(query, {"experiment_id": experiment_id})
            experiment = result.mappings().first()
            if not experiment:
                raise HTTPException(status_code=404, detail="实验不存在")

        effective_limit = limit if experiment_id == 0 else None

        if last_timestamp:
            base_sql = f"SELECT time, data FROM {table_name} WHERE experiment_id = :experiment_id AND time > :last_timestamp ORDER BY time DESC"
            params = {"experiment_id": experiment_id, "last_timestamp": last_timestamp}
            if effective_limit is not None:
                sql = base_sql + " LIMIT :limit"
                params["limit"] = effective_limit
            else:
                sql = base_sql
        else:
            base_sql = f"SELECT time, data FROM {table_name} WHERE experiment_id = :experiment_id ORDER BY time DESC"
            params = {"experiment_id": experiment_id}
            if effective_limit is not None:
                sql = base_sql + " LIMIT :limit"
                params["limit"] = effective_limit
            else:
                sql = base_sql

        result = await session.execute(text(sql), params)
        results = result.mappings().all()
        return [
            {
                "time": row["time"].isoformat(sep=' '),
                "data": json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
            }
            for row in results[::-1]
        ]


async def fetch_optimization_records(limit=100):
    async with AsyncDBSession() as session:
        sql = (
            "SELECT ID, optimization_introduction, experiment_ids "
            "FROM OptimizationRecords ORDER BY ID LIMIT :limit"
        )
        result = await session.execute(text(sql), {"limit": limit})
        results = result.mappings().all()
        return [
            {
                "id": row["ID"],
                "optimization_introduction": row["optimization_introduction"],
                "experiment_ids": row["experiment_ids"].split(',') if row["experiment_ids"] else []
            }
            for row in results
        ]


async def fetch_records(limit=100):
    async with AsyncDBSession() as session:
        sql = (
            "SELECT ID, start_time, end_time, control_command, feed_number, "
            "phase_wash, phase_elute, phase_refresh, phase_equilibrate, "
            "resin, column_height, column_inner_diameter, bed_height, liquid_height, "
            "product_quality, product_yield, product_productivity "
            "FROM ExperimentRecords ORDER BY ID LIMIT :limit"
        )
        result = await session.execute(text(sql), {"limit": limit})
        results = result.mappings().all()
        return [
            {
                "id": row["ID"],
                "start_time": row["start_time"].isoformat(sep=' ') if row["start_time"] else "未开始",
                "end_time": row["end_time"].isoformat(sep=' ') if row["end_time"] else "未结束",
                "control_command": json.loads(row["control_command"]) if isinstance(row["control_command"], str) else
                row["control_command"],
                "feed_number": row["feed_number"],
                "phase_wash": row["phase_wash"],
                "phase_elute": row["phase_elute"],
                "phase_refresh": row["phase_refresh"],
                "phase_equilibrate": row["phase_equilibrate"],
                "resin": row["resin"],
                "column_height": row["column_height"],
                "column_inner_diameter": row["column_inner_diameter"],
                "bed_height": row["bed_height"],
                "liquid_height": row["liquid_height"],
                "product_quality": row["product_quality"],
                "product_yield": row["product_yield"],
                "product_productivity": row["product_productivity"]
            }
            for row in results
        ]


async def fetch_exp_design(limit=100):
    async with AsyncDBSession() as session:
        sql = (
            "SELECT ID, optimization_introduction, experiment_ids "
            "FROM OptimizationRecords ORDER BY ID LIMIT :limit"
        )
        result = await session.execute(text(sql), {"limit": limit})
        results = result.mappings().all()
        return [
            {
                "id": row["ID"],
                "description": row["optimization_introduction"],
                "design_table": json.loads(row["experiment_ids"]) if isinstance(row["experiment_ids"], str)
                else row["experiment_ids"]
            }
            for row in results
        ]


async def fetch_logs(limit=100):
    async with AsyncDBSession() as session:
        sql = f"SELECT time, content, experiment_id FROM Logs ORDER BY time DESC LIMIT :limit"
        result = await session.execute(text(sql), {"limit": limit})
        results = result.mappings().all()
        return [
            {
                "time": row["time"].isoformat(sep=' '),
                "content": row["content"],
                "experiment_id": row["experiment_id"],
            }
            for row in results
        ]


async def delete_records(experiment_id):
    async with AsyncDBSession() as session:
        delete_query = text("DELETE FROM ExperimentRecords WHERE ID = :experiment_id")
        await session.execute(delete_query, {"experiment_id": experiment_id})
        await session.commit()


# 在数据库中创建一个实验设计
async def create_experiment_design(experiment_ids: dict, optimization_introduction: str):
    experiment_ids_json = json.dumps(experiment_ids, indent=4)
    async with AsyncDBSession() as session:
        try:
            sql = text('''INSERT INTO OptimizationRecords (optimization_introduction, experiment_ids)
                           VALUES (:optimization_introduction, :experiment_ids)''')
            result = await session.execute(sql, {"optimization_introduction": optimization_introduction,
                                                 "experiment_ids": experiment_ids_json})
            await session.commit()
            return result.lastrowid
        except Exception as e:
            print(f"创建实验设计错误: {e}")
            await session.rollback()
            raise HTTPException(status_code=400, detail="Failed to create experiment")


# 在数据库中创建一个实验
async def create_experiment(request: ExperimentCreateRequest) -> int:
    data = request.model_dump()  # 获取所有数据
    data['control_command'] = json.dumps(data['control_command'], indent=4)

    columns = list(data.keys())
    column_str = ", ".join(columns)
    placeholders = ", ".join([f":{key}" for key in data.keys()])

    sql = f"""
    INSERT INTO ExperimentRecords ({column_str})
    VALUES ({placeholders})
    """

    async with AsyncDBSession() as session:
        try:
            result = await session.execute(text(sql), data)
            await session.commit()
            return result.lastrowid

        except Exception as e:
            print(f"实验创建错误: {e}")
            await session.rollback()
            return 0
