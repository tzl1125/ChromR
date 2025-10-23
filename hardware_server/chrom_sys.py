import asyncio
import json
from collections import deque

import numpy as np
from sklearn.decomposition import PCA
from sqlalchemy import text

import NIR
import UV
from chrom_process import ChromProcess
from hardware_config import HardwareConfig
from mysql import AsyncDBSession
from level_control import PIDController, FuzzyController
from pumps import PumpController
from sensors import SensorController
from valves import ValveController


class ChromSys:
    def __init__(self):
        self.experiment_id = 0  # 未启动具体实验默认为0
        self.sampleSpan_run = 5  # 实验时传感器和光谱采样间隔s
        self.sampleSpan_stop = 600  # 不在实验时传感器和光谱采样间隔s
        self.lc_span = 1  # 液位控制时间间隔s
        self.equilibriumCheckSpan = 20  # 检查柱层析流出液是否达到平衡的传感器与光谱数据检查窗口，min
        self.running = False  # 实验运行状态
        self.chrom_process = None  # 柱层析实验对象
        self.chrom_task = None
        self.equilibrium_status = None  # 平衡状态

        # 传感器差异化稳定性阈值 (相对阈值, 绝对阈值, 斜率阈值)
        self.sensor_thresholds = {
            'ph': {'rel': 0.03, 'abs': 0.02, 'slope': 0.005},
            'orp': {'rel': 0.08, 'abs': 5, 'slope': 0.1},
            'conductivity': {'rel': 0.05, 'abs': 1, 'slope': 0.05}
        }
        self.stage_constraints = {
            'equilibrate': {
                'ph': (4.8, 7.5),
                'conductivity': (0, 1)  # 电导率应小于1 mS/cm
            },
            'refresh': {
                'ph': (5, 7.5),
                'conductivity': (0, 1)
            }
        }
        # 光谱稳定性参数
        self.spectral_threshold = 0.001  # 光谱稳定性阈值
        self.pca_components = 5  # PCA主成分数量

        # 初始化设备控制器
        pump_addresses = [0x05, 0x06, 0x07, 0x08, 0x09, 0x0A]
        valve_channels = [1, 2, 3, 4, 5, 8, 9, 10, 11]

        self.uv_controller = UV.UVDevice()
        self.nir_controller = NIR.NIRDevice()
        self.sensor_controller = SensorController(port='com8', conductivity_address=1, ph_address=2, orp_address=3,
                                                  level_address=4)
        self.pump_controller = PumpController(port='com5', pump_addresses=pump_addresses)
        self.valve_controller = ValveController(client=self.pump_controller.get_client(), valve_channels=valve_channels,
                                                slave_address=1)
        self.uv_wavelengths = self.uv_controller.get_Wavelengths()
        self.nir_wavelengths = self.nir_controller.get_wavelengths()

        # 时间窗口中的数据
        self.max_data_points = int(self.equilibriumCheckSpan * 60 / (self.sampleSpan_run + 10))  # 由于延迟采样间隔约10s
        self.sensor_datas = deque(maxlen=self.max_data_points)
        self.uv_datas = deque(maxlen=self.max_data_points)
        self.nir_datas = deque(maxlen=self.max_data_points)

        # 初始化PID控制器
        # # 增大 Kp：加快系统响应速度，但可能引起振荡
        # # 增大 Ki：消除稳态误差，但可能导致过冲和不稳定
        # # 增大 Kd：减少超调和振荡，提高系统稳定性，但对噪声敏感
        # self.level_controller = PIDController(
        #     kp=1.0,
        #     ki=0.05,  # 降低积分增益
        #     kd=0.05,  # 降低微分增益
        #     output_min=0,
        #     output_max=400,
        #     integral_threshold=30,  # 当误差>30时禁用积分
        #     alpha=0.2  # 微分滤波系数
        # )

        # 初始化模糊控制器
        self.level_controller = FuzzyController()

    # 传输光谱数据到数据库
    async def send_spectral(self, wavelengths, absorbance, table):
        keys_list = wavelengths.tolist()
        values_list = absorbance.tolist()
        data_dict = dict(zip(keys_list, values_list))
        json_data = json.dumps(data_dict)

        async with AsyncDBSession() as session:
            try:
                if table == "uv":
                    sql = text("INSERT INTO UVs (data, experiment_id) VALUES (:json_data, :experiment_id)")
                elif table == "nir":
                    sql = text("INSERT INTO NIRs (data, experiment_id) VALUES (:json_data, :experiment_id)")
                else:
                    raise ValueError("Table must be either uv or nir")

                await session.execute(sql, {"json_data": json_data, "experiment_id": self.experiment_id})
                await session.commit()
            except Exception as e:
                print(f"传输光谱数据到数据库错误: {e}")
                await session.rollback()

    # 传输传感器数据到数据库
    async def send_sensor(self, sensor_data):
        json_data = json.dumps(sensor_data, indent=4)
        async with AsyncDBSession() as session:
            try:
                sql = text("INSERT INTO Sensors (data, experiment_id) VALUES (:sensor_data, :experiment_id)")
                await session.execute(sql, {"sensor_data": json_data, "experiment_id": self.experiment_id})
                await session.commit()
            except Exception as e:
                print(f"传输传感器数据到数据库错误: {e}")
                await session.rollback()

    # 采集数据
    async def start_data_collection(self):
        while True:
            try:
                # 并发采集传感器、紫外、近红外数据
                sensor_task = asyncio.to_thread(self.sensor_controller.read_all_sensors)
                uv_task = asyncio.to_thread(self.uv_controller.get_absorbance)
                nir_task = asyncio.to_thread(self.nir_controller.get_absorbance)

                # 等待所有采集任务完成
                sensor_data, uv_absorbance, nir_absorbance = await asyncio.gather(
                    sensor_task,
                    uv_task,
                    nir_task
                )

                # 存储采集数据
                self.sensor_datas.append(sensor_data)
                self.uv_datas.append(uv_absorbance)
                self.nir_datas.append(nir_absorbance)

                # 并发发送数据到数据库
                send_tasks = [
                    self.send_sensor(sensor_data),
                    self.send_spectral(self.uv_wavelengths, uv_absorbance, 'uv'),
                    self.send_spectral(self.nir_wavelengths, nir_absorbance, 'nir')
                ]
                await asyncio.gather(*send_tasks)

            except Exception as e:
                print(f"数据采集发生错误: {e}")
            finally:
                running = self.running
                ssr = self.sampleSpan_run
                sss = self.sampleSpan_stop

                res_time = self.sampleSpan_run if self.running else self.sampleSpan_stop
                while res_time > 0:
                    await asyncio.sleep(1)
                    res_time -= 1
                    if running != self.running or ssr != self.sampleSpan_run or sss != self.sampleSpan_stop:
                        break

    # 根据液面高度，控制出口泵的转速，使得液面维持在一定高度
    async def level_control(self, target_level):
        # self.level_controller.reset()
        self.level_controller.set_target_level(target_level * 10)
        while True:
            if self.running:
                try:
                    # 读取当前液位
                    current_level = await asyncio.to_thread(self.sensor_controller.read_level)
                    # 计算输出
                    # output = self.level_controller.update(
                    #     setpoint=target_level * 10,
                    #     measurement=current_level
                    # )
                    output = self.level_controller.calculate_control(current_level)
                    # 更新泵速
                    self.pump_controller.set_speed(
                        HardwareConfig.out['pump'],
                        output
                    )
                    # # 添加调试输出
                    # print(f"目标: {target_level * 10:.1f} 当前: {current_level:.1f} "
                    #       f"误差: {target_level * 10 - current_level:.1f} "
                    #       f"输出: {output:.1f}")

                except Exception as e:
                    print(f"液位控制错误: {e}")
                finally:
                    await asyncio.sleep(self.lc_span)
            else:
                break

    # 根据传感器数据判断是否平衡
    async def check_equilibrium(self, stage):
        """根据时间窗口中的传感器和光谱数据判断流出液是否达到平衡"""
        # 检查数据点数量是否足够，不足则直接返回
        if not all(len(data) == self.max_data_points for data in [
            self.sensor_datas,
            self.uv_datas,
            self.nir_datas
        ]):
            print("数据点数量不足，无法进行平衡判断")
            return False
        # 提取传感器值
        ph_values = [data['ph']['value'] for data in self.sensor_datas]
        orp_values = [data['orp']['value'] for data in self.sensor_datas]
        conductivity_values = [data['conductivity']['value'] for data in self.sensor_datas]

        # 阶段约束检查（按传感器单独记录）
        sensor_constraint_ok = {}
        sensor_data = self.sensor_datas[-1]  # 取最新传感器数据
        for sensor_type, (min_val, max_val) in self.stage_constraints[stage].items():
            value = sensor_data[sensor_type]['value']
            ok = min_val <= value <= max_val
            sensor_constraint_ok[sensor_type] = ok
            if not ok:
                print(f"{stage}阶段: {sensor_type}值{value}不在范围[{min_val}, {max_val}]内")

        # 传感器稳定性检测
        sensor_stable = {
            'ph': self._check_sensor_stability(ph_values, 'ph'),
            'orp': self._check_sensor_stability(orp_values, 'orp'),
            'conductivity': self._check_sensor_stability(conductivity_values, 'conductivity')
        }

        # 记录传感器状态（合并稳定性和约束检查结果，orp无约束）
        for name, stable in sensor_stable.items():
            if name in sensor_constraint_ok:
                # 对有约束的传感器（ph, conductivity）合并判断
                self.equilibrium_status["sensors"][name] = bool(stable and sensor_constraint_ok[name])
            else:
                # 对无约束的传感器（orp）只看稳定性
                self.equilibrium_status["sensors"][name] = bool(stable)

        # 打印传感器稳定性结果
        logs = "传感器稳定性检测结果:\n"
        for name, stable in self.equilibrium_status["sensors"].items():
            status = "稳定" if stable else "不稳定"
            logs += f"  - {name}: {status}\n"
        print(logs)

        # 光谱稳定性检测
        uv_stable = self._check_spectral_stability(np.array(self.uv_datas), "UV")
        nir_stable = self._check_spectral_stability(np.array(self.nir_datas), "NIR")

        # 记录光谱状态
        self.equilibrium_status["spectra"]["uv"] = bool(uv_stable)
        self.equilibrium_status["spectra"]["nir"] = bool(nir_stable)

        # 打印光谱稳定性结果
        logs = f"光谱稳定性检测结果:\n"
        logs += f"  - UV: {'稳定' if uv_stable else '不稳定'}\n"
        logs += f"  - NIR: {'稳定' if nir_stable else '不稳定'}\n"
        print(logs)

        # 综合判定所有条件
        all_sensors_stable = all(self.equilibrium_status["sensors"].values())
        equilibrium_reached = all_sensors_stable and uv_stable and nir_stable

        print(f"系统平衡状态: {'已达到平衡' if equilibrium_reached else '未达到平衡'}")
        return equilibrium_reached

    def _check_sensor_stability(self, values, sensor_name):
        """检查单个传感器的稳定性"""
        thresholds = self.sensor_thresholds[sensor_name]

        # 计算统计量
        std_val = np.std(values)
        mean_val = np.mean(values)

        # 量程自适应阈值检测
        if abs(mean_val) < 1:
            stable = std_val < thresholds['abs']
        else:
            stable = (std_val / abs(mean_val)) < thresholds['rel']

        # 趋势检测（线性回归斜率）
        if len(values) >= 5:
            slope = self._calculate_slope(values)
            stable = stable and (abs(slope) < thresholds['slope'])

        return stable

    def _check_spectral_stability(self, spectral_data, spectral_type):
        """使用PCA方法检测光谱稳定性"""
        # 数据量检查
        if spectral_data.shape[0] < self.pca_components + 1:
            print(f"{spectral_type}光谱数据不足({spectral_data.shape[0]}点)，无法进行PCA分析")
            return False

        # 创建PCA模型并转换数据
        pca = PCA(n_components=self.pca_components)
        scores = pca.fit_transform(spectral_data)

        for i in range(scores.shape[1]):
            comp_values = scores[:, i]
            mean_val = np.mean(comp_values)
            std_val = np.std(comp_values)

            # 避免除以零
            if abs(mean_val) < 1e-5:
                rsd = std_val
            else:
                rsd = std_val / abs(mean_val)

            if rsd > self.spectral_threshold:
                print(f"{spectral_type}光谱主成分{i + 1}不稳定(RSD={rsd:.4f} > {self.spectral_threshold})")
                return False

        return True

    def _calculate_slope(self, values):
        """计算时间序列的线性趋势斜率"""
        x = np.arange(len(values))
        return np.polyfit(x, values, 1)[0]  # 返回线性系数

    # 发送日志
    async def send_log(self, content):
        async with AsyncDBSession() as session:
            try:
                sql = text("INSERT INTO Logs (content, experiment_id) VALUES (:content, :experiment_id)")
                await session.execute(sql, {"content": content, "experiment_id": self.experiment_id})
                await session.commit()
            except Exception as e:
                print(f"发送日志到数据库错误: {e}")
                await session.rollback()

    # 添加运行实验协程到事件循环
    async def run_experiment(self, experiment_record):
        self.chrom_task = asyncio.create_task(self.execute_chrom_experiment(experiment_record))

    # 运行一个实验
    async def execute_chrom_experiment(self, experiment_record):
        self.experiment_id = experiment_record['id']
        self.chrom_process = ChromProcess(self.uv_controller, self.nir_controller, self.pump_controller,
                                          self.valve_controller, experiment_record, self.sampleSpan_run)
        # 在开始实验前删除该实验ID的相关数据
        await self.delete_experiment_data(self.experiment_id)
        await self.update_experiment_time(None)
        self.running = True
        # 计算控制液位设定值（液位计到液面的距离），cm
        liquid_level = (experiment_record['column_height'] - experiment_record['bed_height']
                        - experiment_record['liquid_height'])
        level_control_task = asyncio.create_task(self.level_control(liquid_level))

        try:
            def reset_es():
                # 初始化当前平衡检查状态
                self.equilibrium_status = {
                    "sensors": {'ph': False, 'orp': False, 'conductivity': False},
                    "spectra": {'uv': False, 'nir': False},
                }

            await self.update_experiment_time(True)  # 更新开始时间
            if await self.chrom_process.execute_process(self.check_equilibrium, self.send_log, reset_es):
                # await self.cal_experiment_index()
                await self.send_log(f"Experiment has been completed")
                await self.update_experiment_time(False)  # 更新结束时间
        except Exception as e:
            await self.update_experiment_time(None)
            await self.send_log(f"Experiment execution error: {e}")
        finally:
            self.running = False
            self.chrom_process = None
            self.experiment_id = 0
            self.equilibrium_status = None
            # 实验结束后取消 level_control 任务
            if not level_control_task.done():
                level_control_task.cancel()
                try:
                    await level_control_task
                except asyncio.CancelledError:
                    pass
            # 泵和阀门自动初始化
            await asyncio.to_thread(self.pump_controller.initialize_pumps)
            await asyncio.to_thread(self.valve_controller.set_multiple_valve_opening, 0)

    # 跳过当前柱层析阶段
    async def skip_current_stage(self):
        if not self.running:
            return "没有实验在运行"

        if self.chrom_process.current_stage in ["equilibrate", "feed", "wash", "elute", "refresh"]:
            await self.send_log(f"用户强制跳过 {self.chrom_process.current_stage} 阶段")
            self.chrom_process.skip_stage = True  # 设置跳过标志
            return "已跳过当前阶段"

        return "当前阶段不可跳过"

    # 停止实验，实验id设置为默认值0
    async def stop_chrom_experiment(self):
        if self.chrom_task is not None:
            # 暂停实验
            if not self.chrom_task.done():
                await self.update_experiment_time(None)
                await self.send_log(f"实验已强制停止")
                self.chrom_task.cancel()
                try:
                    await self.chrom_task
                except asyncio.CancelledError:
                    pass
            self.chrom_task = None

    # 计算实验指标
    async def cal_experiment_index(self):
        pass

    # 写入实验指标
    async def save_experiment_index(self, product_quality, product_yield, product_productivity):
        """
        在线保存实验的产品指标数据

        Args:
            product_quality: 产品质量（指标）
            product_yield: 产品收率（%）
            product_productivity: 产品产率（如g/h）
        """
        sql = """
        UPDATE ExperimentRecords
        SET product_quality = :quality,
            product_yield = :yield_,
            product_productivity = :productivity
        WHERE ID = :id
        """

        async with AsyncDBSession() as session:
            try:
                await session.execute(
                    text(sql),
                    {
                        "quality": product_quality,
                        "yield_": product_yield,
                        "productivity": product_productivity,
                        "id": self.experiment_id
                    }
                )
                await session.commit()
            except Exception as e:
                print(f"更新实验{self.experiment_id}的产品指标错误: {e}")
                await session.rollback()

    # 从数据库获取实验记录
    async def get_experiment_record(self, experiment_id: int):
        async with AsyncDBSession() as session:
            sql = """
                SELECT 
                    ID, start_time, end_time, control_command, feed_number,
                    phase_wash, phase_elute, phase_refresh, phase_equilibrate,
                    resin, column_height, column_inner_diameter, bed_height, liquid_height
                FROM ExperimentRecords 
                WHERE ID = :id
            """
            result = await session.execute(text(sql), {"id": experiment_id})
            record = result.mappings().first()

            if not record:
                return None  # 记录不存在时返回None

            return {
                "id": record["ID"],
                "start_time": record["start_time"].isoformat() if record["start_time"] else None,
                "end_time": record["end_time"].isoformat() if record["end_time"] else None,
                "control_command": json.loads(record["control_command"])
                if isinstance(record["control_command"], str) else record["control_command"],
                "feed_number": record["feed_number"],
                "phase_wash": record["phase_wash"],
                "phase_elute": record["phase_elute"],
                "phase_refresh": record["phase_refresh"],
                "phase_equilibrate": record["phase_equilibrate"],
                "resin": record["resin"],
                "column_height": record["column_height"],
                "column_inner_diameter": record["column_inner_diameter"],
                "bed_height": record["bed_height"],
                "liquid_height": record["liquid_height"],
            }

    # 删除指定实验ID的相关数据
    async def delete_experiment_data(self, experiment_id):
        tables = ['Sensors', 'UVs', 'NIRs', 'Logs']
        async with AsyncDBSession() as session:
            try:
                for table in tables:
                    sql = text(f"DELETE FROM {table} WHERE experiment_id = :experiment_id")
                    await session.execute(sql, {"experiment_id": experiment_id})
                await session.commit()
            except Exception as e:
                print(f"删除实验 {experiment_id} 相关数据时出错: {e}")
                await session.rollback()

    # 更新实验记录的开始或结束时间为当前时间
    async def update_experiment_time(self, state: bool | None = True):
        """
        更新实验记录的开始或结束时间为当前时间，或设置开始时间为空

        Args:
            state:
                True - 设置开始时间为当前时间（默认）
                False - 设置结束时间为当前时间
                None - 设置开始时间为空
        """
        if state is None:
            # 设置开始和结束时间为空
            sql = """
            UPDATE ExperimentRecords
            SET start_time = NULL, end_time = NULL
            WHERE ID = :id
            """
        else:
            # 设置开始或结束时间为当前时间
            time_field = "start_time" if state else "end_time"
            sql = f"""
            UPDATE ExperimentRecords
            SET {time_field} = CURRENT_TIMESTAMP
            WHERE ID = :id
            """

        async with AsyncDBSession() as session:
            try:
                await session.execute(text(sql), {"id": self.experiment_id})
                await session.commit()
            except Exception as e:
                print(f"更新实验{self.experiment_id}的时间字段错误: {e}")
                await session.rollback()

    # 硬件状态返回
    async def get_hardware_state(self):
        state = {
            "pump": self.pump_controller.get_pump_states(),
            "valve": self.valve_controller.get_valve_states(),
            'uv': self.uv_controller.get_uv_state(),
            "nir": self.nir_controller.get_nir_state(),
            "experiment_id": self.experiment_id,
            "current_stage": self.chrom_process.current_stage if self.chrom_process is not None else None,
            "equilibrium_status": self.equilibrium_status
        }
        return state

    # 给硬件添加名字
    async def change_hardware_name(self, name: str, hardware_type: str, address):
        if hardware_type == "pump":
            self.pump_controller.set_pump_name(pump_name=name, address=None if address == "all" else address)
        elif hardware_type == "valve":
            self.valve_controller.set_valve_name(valve_name=name, channel=None if address == "all" else address)
