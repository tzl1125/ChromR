import asyncio
import math

from hardware_config import HardwareConfig


class ChromParameters:
    def __init__(self, chromatography_parameters: dict):
        self.feed_flow = chromatography_parameters['feed_flow']  # 上样流量BV/h
        self.feed_time = chromatography_parameters['feed_time'] * 60 * 60  # 上样时间h，转换成秒
        self.wash_flow = chromatography_parameters['wash_flow']  # 洗涤流量BV/h
        self.wash_time = chromatography_parameters['wash_time'] * 60 * 60  # 洗涤时间h，转换成秒
        self.elute_flow = chromatography_parameters['elute_flow']  # 洗脱流量BV/h
        self.elute_time = chromatography_parameters['elute_time'] * 60 * 60  # 洗脱时间h，转换成秒
        self.refresh_flow = chromatography_parameters['refresh_flow']  # 再生流量BV/h
        self.equilibrate_flow = chromatography_parameters['equilibrate_flow']  # 平衡流量BV/h

        self.feed_pump = HardwareConfig.feed['pump']
        self.wash_pump = HardwareConfig.wash['pump']
        self.elute_pump = HardwareConfig.elute['pump']
        self.refresh_pump = HardwareConfig.refresh['pump']
        self.equilibrate_pump = HardwareConfig.equilibrate['pump']
        self.out_pump = HardwareConfig.out['pump']

        self.feed_valve = HardwareConfig.feed['valve']
        self.wash_valve = HardwareConfig.wash['valve']
        self.elute_valve = HardwareConfig.elute['valve']
        self.refresh_valve = HardwareConfig.refresh['valve']
        self.equilibrate_valve = HardwareConfig.equilibrate['valve']
        self.waste_valve = HardwareConfig.out['waste']
        self.fraction_valve = HardwareConfig.out[chromatography_parameters['fraction']]


class ChromProcess(ChromParameters):
    def __init__(self, uv_controller, nir_controller, pump_controller,
                 valve_controller, experiment_record: dict, sample_span):
        super().__init__(experiment_record['control_command'])
        self.uv_controller = uv_controller
        self.nir_controller = nir_controller
        self.pump_controller = pump_controller
        self.valve_controller = valve_controller
        self.sampleSpan = sample_span
        self.current_stage = None  # 当前实验阶段
        self.skip_stage = False  # 跳过当前阶段的标志

        # 计算柱体积，mL
        self.bv = math.pi * pow(experiment_record['column_inner_diameter'] / 2, 2) * experiment_record['bed_height']
        # 流量转换为转速
        self.feed_speed = (self.bv * (self.feed_flow / 60) *
                           HardwareConfig.pump_factor[f'{self.feed_pump}'])
        self.wash_speed = (self.bv * (self.wash_flow / 60) *
                           HardwareConfig.pump_factor[f'{self.wash_pump}'])
        self.elute_speed = (self.bv * (self.elute_flow / 60) *
                            HardwareConfig.pump_factor[f'{self.elute_pump}'])
        self.refresh_speed = (self.bv * (self.refresh_flow / 60) *
                              HardwareConfig.pump_factor[f'{self.refresh_pump}'])
        self.equilibrate_speed = (self.bv * (self.equilibrate_flow / 60) *
                                  HardwareConfig.pump_factor[f'{self.equilibrate_pump}'])

    def switch_mode(self, mode):
        mode_config = {
            'feed': (self.feed_pump, self.feed_speed, self.feed_valve),
            'wash': (self.wash_pump, self.wash_speed, self.wash_valve),
            'elute': (self.elute_pump, self.elute_speed, self.elute_valve),
            'refresh': (self.refresh_pump, self.refresh_speed, self.refresh_valve),
            'equilibrate': (self.equilibrate_pump, self.equilibrate_speed, self.equilibrate_valve)
        }
        pump, speed, valve = mode_config[mode]

        all_valves = [
            self.feed_valve,
            self.wash_valve,
            self.elute_valve,
            self.refresh_valve,
            self.equilibrate_valve
        ]
        valves_to_close = [v for v in all_valves if v != valve]

        self.valve_controller.set_multiple_valve_opening(0, valves_to_close)
        self.valve_controller.set_valve_opening(valve, 100)

        all_pumps = [
            self.feed_pump,
            self.wash_pump,
            self.elute_pump,
            self.refresh_pump,
            self.equilibrate_pump
        ]
        pumps_to_close = [p for p in all_pumps if p != pump]

        self.pump_controller.control_pumps('start_stop', False, pumps_to_close)
        self.pump_controller.set_speed(pump, speed)
        self.pump_controller.control_single(pump, 'start_stop', True)

    # 根据各类传感器的值，判断是否达到稳定
    async def reach_equilibration(self, check_equilibrium, flow, stage):
        # 至少上1.5个柱体积
        await self.wait(1.5 * 60 * 60 / flow)
        while True:
            if self.skip_stage or await check_equilibrium(stage):
                break
            else:
                await self.wait(self.sampleSpan + 10)

    # 计算函数
    async def wait(self, total_time):
        rest_time = total_time  # 剩下的时间
        while rest_time > 0:
            if self.skip_stage:
                break
            await asyncio.sleep(1)
            rest_time -= 1

    # 执行柱层析过程
    async def execute_process(self, check_equilibrium, send_log, reset_es):
        await send_log("正在初始化硬件设备...")
        self.current_stage = "initializing"
        reset_es()
        # 初始化所有阀门和泵
        await asyncio.to_thread(self.pump_controller.initialize_pumps)
        await asyncio.to_thread(self.valve_controller.set_multiple_valve_opening, 0)
        await asyncio.sleep(5)
        await send_log("初始化硬件设备已完成。")

        # 实验开始
        await send_log("打开废液阀门和出口泵...")
        self.valve_controller.set_valve_opening(self.waste_valve, 100)  # 废液阀门开
        self.pump_controller.control_single(self.out_pump, 'start_stop', True)  # 出口泵开
        # 开始平衡阶段
        await send_log("平衡阶段开始，切换到平衡模式...")
        self.current_stage = "equilibrate"
        await asyncio.to_thread(self.switch_mode, 'equilibrate')
        await send_log("已切换到平衡模式，开始等待达到平衡状态...")
        await self.reach_equilibration(check_equilibrium, self.equilibrate_flow, 'equilibrate')
        self.skip_stage = False
        await send_log("平衡阶段结束，已达到平衡状态。")

        # 设置光谱参考值
        await send_log("正在设置UV和NIR的参比光谱...")
        await asyncio.to_thread(self.uv_controller.set_reference)
        await asyncio.to_thread(self.nir_controller.set_reference)
        await send_log("UV和NIR的参考值已设置完成。")

        # 开始上样阶段
        await send_log("上样阶段开始，切换到上样模式...")
        self.current_stage = "feed"
        await asyncio.to_thread(self.switch_mode, 'feed')
        await send_log(f"上样模式已开启，开始上样，设定上样时间为 {self.feed_time} 秒。")
        await self.wait(self.feed_time)
        self.skip_stage = False
        await send_log("上样阶段结束。")

        # 开始洗涤阶段
        await send_log("洗涤阶段开始，切换到洗涤模式...")
        self.current_stage = "wash"
        await asyncio.to_thread(self.switch_mode, 'wash')
        await send_log(f"洗涤模式已开启，开始洗涤，设定洗涤时间为 {self.wash_time} 秒。")
        await self.wait(self.wash_time)
        self.skip_stage = False
        await send_log("洗涤阶段结束。")

        # 开始洗脱阶段
        await send_log("洗脱阶段开始，切换到洗脱模式...")
        self.current_stage = "elute"
        self.valve_controller.set_valve_opening(self.waste_valve, 0)  # 废液阀门关
        self.valve_controller.set_valve_opening(self.fraction_valve, 100)  # 馏分阀门开
        await asyncio.to_thread(self.switch_mode, 'elute')
        await send_log(f"洗脱模式已开启，开始洗脱，设定洗脱时间为 {self.elute_time} 秒。")
        await self.wait(self.elute_time)
        self.skip_stage = False
        await send_log("洗脱阶段结束。")

        # 开始再生阶段
        reset_es()
        await send_log("再生阶段开始，切换到再生模式...")
        self.current_stage = "refresh"
        self.valve_controller.set_valve_opening(self.waste_valve, 100)  # 废液阀门开
        self.valve_controller.set_valve_opening(self.fraction_valve, 0)  # 馏分阀门关
        await asyncio.to_thread(self.switch_mode, 'refresh')
        await send_log("已切换到再生模式，开始等待达到平衡状态...")
        await self.reach_equilibration(check_equilibrium, self.refresh_flow, 'refresh')
        self.skip_stage = False
        await send_log("再生阶段结束，已达到平衡状态。")

        # 实验结束
        await send_log("柱层析过程结束")
        self.current_stage = None
        return True
