import asyncio
import json
import socket
from contextlib import asynccontextmanager
from typing import Optional
from collections import deque
import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from chrom_sys import ChromSys
from data_model import *


# 获取本机IP地址
def get_local_ip() -> Optional[str]:
    try:
        # 创建socket连接获取本地IP（不实际连接）
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception as e:
        print(f"获取本地IP失败: {e}")
        return None


# 心跳包发送任务
async def heartbeat_task(target_url: str, interval: int = 5):
    """定时向目标后端发送心跳包"""
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                local_ip = get_local_ip()
                if not local_ip:
                    print("无法获取本地IP")
                # 发送心跳包
                async with session.post(
                        target_url,
                        json={"ip": local_ip}
                ):
                    pass
            except Exception:
                pass

            # 等待下一次发送
            await asyncio.sleep(interval)


# 定义 lifespan 函数
@asynccontextmanager
async def lifespan(app: FastAPI):
    chrom_sys = ChromSys()
    # 启动数据收集任务
    data_collection_task = asyncio.create_task(chrom_sys.start_data_collection())

    # 启动心跳包任务
    heartbeat_target = "http://xxxx:8000/heartbeat"
    heartbeat_task_handle = asyncio.create_task(heartbeat_task(heartbeat_target, interval=3))

    # 将 chrom_sys 存储在 app 实例中
    app.state.chrom_sys = chrom_sys
    # 在yield之前的代码会在应用启动时执行（进入上下文）
    # 在yield之后的代码会在应用关闭时执行（退出上下文）
    yield

    # 应用关闭时清理任务
    data_collection_task.cancel()
    heartbeat_task_handle.cancel()
    try:
        await data_collection_task
        await heartbeat_task_handle
    except asyncio.CancelledError:
        pass


# 创建 FastAPI 应用并传入 lifespan 函数
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)


@app.post('/control/system')
async def control_system(system: System):
    chrom_sys = app.state.chrom_sys
    try:
        if system.type == "stop_exp":
            if chrom_sys.running:
                await chrom_sys.stop_chrom_experiment()
        elif system.type == "run_exp":
            if not chrom_sys.running:
                experiment_record = await chrom_sys.get_experiment_record(system.experiment)
                if experiment_record is None:
                    raise ValueError(f"Experiment record not found: {system.experiment}")

                await chrom_sys.run_experiment(experiment_record)
                await chrom_sys.send_log(f"开始运行实验，id：{system.experiment}")
            else:
                raise HTTPException(status_code=400, detail=f"正在运行实验id:{chrom_sys.experiment_id}")
    except Exception as e:
        action = "停止实验" if system.type == "stop_exp" else f"开始运行实验 {system.experiment}"
        await chrom_sys.send_log(f"{action}失败")
        print(e)
        raise HTTPException(status_code=400, detail=f"Something went wrong:{e}")
    return {"result": "操作成功"}


@app.post('/control/uv')
async def control_uv(uv: Uv):
    chrom_sys = app.state.chrom_sys
    try:
        if uv.type == "lamp":
            chrom_sys.uv_controller.enable_lamp(1 if uv.value else 0)
            await chrom_sys.send_log(f"紫外氙灯{'开启' if uv.value else '关闭'}")
        elif uv.type == "average_times":
            chrom_sys.uv_controller.set_average(uv.value)
            await chrom_sys.send_log(f"紫外平均次数设置为{uv.value}")
        elif uv.type == "integration_time":
            chrom_sys.uv_controller.set_integration_time(uv.value * 1000)
            await chrom_sys.send_log(f"紫外积分时间设置为{uv.value}ms")
        elif uv.type == "set_background":
            chrom_sys.uv_controller.set_background()
            await chrom_sys.send_log("紫外暗背景设置成功")
        elif uv.type == "set_reference":
            chrom_sys.uv_controller.set_reference()
            await chrom_sys.send_log("紫外参比设置成功")
    except Exception as e:
        await chrom_sys.send_log("紫外操作失败")
        print(e)
        raise HTTPException(status_code=400, detail=f"Something went wrong:{e}")
    return {"result": "操作成功"}


@app.post('/control/nir')
async def control_nir(nir: Nir):
    chrom_sys = app.state.chrom_sys
    try:
        if nir.type == "average_times":
            chrom_sys.nir_controller.set_avg_times(nir.value)
            await chrom_sys.send_log(f"红外平均次数设置为{nir.value}")
        elif nir.type == "set_background":
            chrom_sys.nir_controller.set_background()
            await chrom_sys.send_log("红外暗背景设置成功")
        elif nir.type == "set_reference":
            chrom_sys.nir_controller.set_reference()
            await chrom_sys.send_log("红外参比设置成功")
    except Exception as e:
        await chrom_sys.send_log("红外操作失败")
        print(e)
        raise HTTPException(status_code=400, detail=f"Something went wrong:{e}")
    return {"result": "操作成功"}


@app.post('/control/pump')
async def control_pump(pump: Pump):
    chrom_sys = app.state.chrom_sys
    log = f"{pump.pump_ids}泵的{pump.type.value}设置为{pump.value}"
    try:
        if pump.type == "alias":
            await chrom_sys.change_hardware_name(name=pump.value, hardware_type='pump', address=pump.pump_ids)
        else:
            if pump.pump_ids == 'all':
                chrom_sys.pump_controller.control_pumps(control_type=pump.type, value=pump.value)
            else:
                chrom_sys.pump_controller.control_pumps(control_type=pump.type, value=pump.value,
                                                        addresses=pump.pump_ids)

        await chrom_sys.send_log(log + "成功")
    except Exception as e:
        await chrom_sys.send_log(log + "失败")
        print(e)
        raise HTTPException(status_code=400, detail=f"Something went wrong:{e}")
    return {"result": "操作成功"}


@app.post('/control/valve')
async def control_valve(valve: Valve):
    chrom_sys = app.state.chrom_sys
    log = f"{valve.valve_ids}阀门的{valve.type.value}设置为{valve.value}"
    try:
        if valve.type == "alias":
            await chrom_sys.change_hardware_name(name=valve.value, hardware_type='valve', address=valve.valve_ids)
        else:
            if valve.valve_ids == 'all':
                chrom_sys.valve_controller.set_multiple_valve_opening(valve.value)
            else:
                chrom_sys.valve_controller.set_multiple_valve_opening(opening=valve.value, channels=valve.valve_ids)

        await chrom_sys.send_log(log + "成功")
    except Exception as e:
        await chrom_sys.send_log(log + "失败")
        print(e)
        raise HTTPException(status_code=400, detail=f"Something went wrong:{e}")
    return {"result": "操作成功"}


@app.get('/query/params')
async def query_system_params():
    """查询系统参数配置"""
    chrom_sys = app.state.chrom_sys
    # 映射参数类型与chrom_sys中的属性
    param_mapping = {
        SystemParamsType.TYPE_A: chrom_sys.sampleSpan_run,
        SystemParamsType.TYPE_B: chrom_sys.sampleSpan_stop,
        SystemParamsType.TYPE_C: chrom_sys.lc_span,
        SystemParamsType.TYPE_D: chrom_sys.equilibriumCheckSpan,
        SystemParamsType.TYPE_E: chrom_sys.sensor_thresholds,
        SystemParamsType.TYPE_F: chrom_sys.stage_constraints,
        SystemParamsType.TYPE_G: chrom_sys.spectral_threshold,
        SystemParamsType.TYPE_H: chrom_sys.pca_components
    }

    # 构建返回结果，使用枚举的value作为键
    result = {param_type.value: param_value for param_type, param_value in param_mapping.items()}
    return result


@app.post('/control/params')
async def control_params(params: SystemParams):
    chrom_sys = app.state.chrom_sys
    try:
        if params.type == "sample_span_run":
            chrom_sys.sampleSpan_run = params.value
            await chrom_sys.send_log(f"实验时采样间隔设置为 {params.value} 秒")
        elif params.type == "sample_span_stop":
            chrom_sys.sampleSpan_stop = params.value
            await chrom_sys.send_log(f"非实验时采样间隔设置为 {params.value} 秒")
        elif params.type == "lc_span":
            chrom_sys.lc_span = params.value
            await chrom_sys.send_log(f"液位控制间隔设置为 {params.value} 秒")
        elif params.type == "equilibrium_check_span":
            chrom_sys.equilibriumCheckSpan = params.value
            new_max_points = int(params.value * 60 / (chrom_sys.sampleSpan_run + 10))

            # 处理传感器数据队列
            current_sensor = list(chrom_sys.sensor_datas)
            # 根据新长度截断或保留数据
            adjusted_sensor = current_sensor[-new_max_points:] if new_max_points < len(
                current_sensor) else current_sensor
            chrom_sys.sensor_datas = deque(adjusted_sensor, maxlen=new_max_points)

            # 处理UV数据队列
            current_uv = list(chrom_sys.uv_datas)
            adjusted_uv = current_uv[-new_max_points:] if new_max_points < len(current_uv) else current_uv
            chrom_sys.uv_datas = deque(adjusted_uv, maxlen=new_max_points)

            # 处理NIR数据队列
            current_nir = list(chrom_sys.nir_datas)
            adjusted_nir = current_nir[-new_max_points:] if new_max_points < len(current_nir) else current_nir
            chrom_sys.nir_datas = deque(adjusted_nir, maxlen=new_max_points)

            chrom_sys.max_data_points = new_max_points

            await chrom_sys.send_log(f"平衡检查窗口设置为 {params.value} 分钟")
        elif params.type == "sensor_thresholds":
            chrom_sys.sensor_thresholds = params.value
            await chrom_sys.send_log("传感器阈值更新成功")
        elif params.type == "stage_constraints":
            chrom_sys.stage_constraints = params.value
            await chrom_sys.send_log("阶段约束更新成功")
        elif params.type == "spectral_threshold":
            chrom_sys.spectral_threshold = params.value
            await chrom_sys.send_log(f"光谱阈值设置为 {params.value}")
        elif params.type == "pca_components":
            chrom_sys.pca_components = params.value
            await chrom_sys.send_log(f"PCA主成分数量设置为 {params.value}")
    except Exception as e:
        await chrom_sys.send_log(f"参数更新失败: {str(e)}")
        print(e)
        raise HTTPException(status_code=400, detail=f"参数更新失败: {str(e)}")
    return {"result": "参数更新成功"}


@app.post('/control/skip_stage')
async def skip_stage():
    chrom_sys = app.state.chrom_sys
    try:
        result = await chrom_sys.skip_current_stage()
        return {"result": result}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=f"跳过阶段失败: {str(e)}")


async def sse_data_generator():
    # 返回泵和阀门的状态
    chrom_sys = app.state.chrom_sys
    while True:
        await asyncio.sleep(1)
        yield ServerSentEvent(data=json.dumps(await chrom_sys.get_hardware_state()))


@app.get('/sse')
async def sse_endpoint():
    return EventSourceResponse(sse_data_generator())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8100)
