import time

import fuzzylite as fl
import numpy as np
from matplotlib import pyplot as plt


class FuzzyController:
    def __init__(self, target_level=500):  # 目标液位默认500mm
        self.engine = fl.Engine(
            name="liquid_level_controller",
            description="液位控制模糊控制器"
        )

        # 创建输入输出变量
        self._create_variables()

        # 创建模糊规则
        self._create_rules()

        # 控制参数
        self.target_level = target_level  # 目标液位(mm)
        self.last_level = None  # 上次液位记录
        self.last_time = None  # 上次记录时间
        self.last_filtered_ec = 0.0  # 上次滤波后的液位变化率
        self.last_speed = 0.0  # 记录上次泵转速，初始为0

    def _create_variables(self):
        # 液位偏差E (当前值-目标值，mm)
        E = fl.InputVariable(
            name="E",
            description="液位偏差",
            enabled=True,
            minimum=-500,
            maximum=500
        )
        # 隶属度函数
        E.terms.append(fl.Trapezoid("NB", -600, -600, -30, -20))  # 负大（液位远低于目标）
        E.terms.append(fl.Triangle("NM", -30, -20, -10))  # 负中（液位较低）
        E.terms.append(fl.Triangle("NS", -15, -8, 0))  # 负小
        E.terms.append(fl.Triangle("Z", -3, 0, 3))  # 零
        E.terms.append(fl.Triangle("PS", 0, 8, 15))  # 正小
        E.terms.append(fl.Triangle("PM", 10, 20, 30))  # 正中
        E.terms.append(fl.Trapezoid("PB", 20, 30, 600, 600))  # 正大（液位远高于目标）
        self.engine.input_variables.append(E)

        # 液位变化率EC (mm/s)
        EC = fl.InputVariable(
            name="EC",
            description="液位变化率",
            enabled=True,
            minimum=-20,
            maximum=20
        )
        # 隶属度函数
        EC.terms.append(fl.Trapezoid("NB", -30, -30, -10, -5))  # 负大（快速下降）
        EC.terms.append(fl.Triangle("NS", -6, -3, 0))  # 负小
        EC.terms.append(fl.Triangle("Z", -1, 0, 1))  # 零
        EC.terms.append(fl.Triangle("PS", 0, 3, 6))  # 正小
        EC.terms.append(fl.Trapezoid("PB", 5, 10, 30, 30))  # 正大（快速上升）
        self.engine.input_variables.append(EC)

        # 输出变量DeltaU
        DeltaU = fl.OutputVariable(
            name="DeltaU",
            description="转速变化量",
            enabled=True,
            minimum=-20,
            maximum=20,
            defuzzifier=fl.Centroid(),
            aggregation=fl.Maximum(),
            lock_previous=False
        )
        # 转速变化量
        DeltaU.terms.append(fl.Trapezoid("LD", -30, -30, -20, -10))  # 大幅减速
        DeltaU.terms.append(fl.Triangle("SD", -15, -8, -2))  # 小幅减速（幅度减小）
        DeltaU.terms.append(fl.Triangle("NC", -3, 0, 3))  # 无变化
        DeltaU.terms.append(fl.Triangle("SI", 2, 8, 15))  # 小幅加速（幅度减小）
        DeltaU.terms.append(fl.Trapezoid("LI", 10, 20, 30, 30))  # 大幅加速
        self.engine.output_variables.append(DeltaU)

    def _create_rules(self):
        self.rule_block = fl.RuleBlock(
            name="rules",
            description="转速控制规则库",
            enabled=True,
            conjunction=fl.Minimum(),
            disjunction=fl.Maximum(),
            implication=fl.Minimum(),
            activation=fl.General()
        )

        # 规则库设计逻辑：
        # 1. E为正（PS/PM/PB）→ 真实液面低于目标→需减速（输出LD/SD），E越大、EC越大（下降越快）→减速越激进
        # 2. E为负（NB/NM/NS）→ 真实液面高于目标→需加速（输出LI/SI），E越负、EC越负（上升越快）→加速越激进
        # 3. 术语严格匹配变量定义（E:7个术语，EC:5个术语，DeltaU:5个术语）
        rules = [
            # E=NB（负大：真实液面远高于目标）→ 优先加速
            "if E is NB and EC is NB then DeltaU is LI",  # 液面快速上升→大幅加速
            "if E is NB and EC is NS then DeltaU is LI",  # 液面缓慢上升→大幅加速
            "if E is NB and EC is Z then DeltaU is SI",  # 液面稳定→小幅加速
            "if E is NB and EC is PS then DeltaU is SI",  # 液面缓慢下降→小幅加速
            "if E is NB and EC is PB then DeltaU is NC",  # 液面快速下降→不调整

            # E=NM（负中：真实液面较高）→ 适度加速
            "if E is NM and EC is NB then DeltaU is LI",  # 液面快速上升→大幅加速
            "if E is NM and EC is NS then DeltaU is SI",  # 液面缓慢上升→小幅加速
            "if E is NM and EC is Z then DeltaU is SI",  # 液面稳定→小幅加速
            "if E is NM and EC is PS then DeltaU is NC",  # 液面缓慢下降→不调整
            "if E is NM and EC is PB then DeltaU is SD",  # 液面快速下降→小幅减速

            # E=NS（负小：真实液面略高于目标）→ 微调或不调整
            "if E is NS and EC is NB then DeltaU is SI",  # 液面快速上升→小幅加速
            "if E is NS and EC is NS then DeltaU is SI",  # 液面缓慢上升→小幅加速
            "if E is NS and EC is Z then DeltaU is NC",  # 液面稳定→不调整
            "if E is NS and EC is PS then DeltaU is NC",  # 液面缓慢下降→不调整
            "if E is NS and EC is PB then DeltaU is SD",  # 液面快速下降→小幅减速

            # E=Z（零：真实液面接近目标）→ 优先稳定
            "if E is Z and EC is NB then DeltaU is SI",  # 液面快速上升→极小加速
            "if E is Z and EC is NS then DeltaU is NC",  # 液面缓慢上升→不调整
            "if E is Z and EC is Z then DeltaU is NC",  # 液面稳定→不调整
            "if E is Z and EC is PS then DeltaU is NC",  # 液面缓慢下降→不调整
            "if E is Z and EC is PB then DeltaU is SD",  # 液面快速下降→极小减速

            # E=PS（正小：真实液面略低于目标）→ 微调或减速
            "if E is PS and EC is NB then DeltaU is NC",  # 液面快速上升→不调整
            "if E is PS and EC is NS then DeltaU is NC",  # 液面缓慢上升→不调整
            "if E is PS and EC is Z then DeltaU is NC",  # 液面稳定→不调整
            "if E is PS and EC is PS then DeltaU is SD",  # 液面缓慢下降→小幅减速
            "if E is PS and EC is PB then DeltaU is LD",  # 液面快速下降→大幅减速

            # E=PM（正中：真实液面较低）→ 适度减速
            "if E is PM and EC is NB then DeltaU is NC",  # 液面快速上升→不调整
            "if E is PM and EC is NS then DeltaU is NC",  # 液面缓慢上升→不调整
            "if E is PM and EC is Z then DeltaU is SD",  # 液面稳定→小幅减速
            "if E is PM and EC is PS then DeltaU is LD",  # 液面缓慢下降→大幅减速
            "if E is PM and EC is PB then DeltaU is LD",  # 液面快速下降→大幅减速

            # E=PB（正大：真实液面远低于目标）→ 优先减速
            "if E is PB and EC is NB then DeltaU is SD",  # 液面快速上升→小幅减速（抑制上升）
            "if E is PB and EC is NS then DeltaU is SD",  # 液面缓慢上升→小幅减速
            "if E is PB and EC is Z then DeltaU is LD",  # 液面稳定→大幅减速
            "if E is PB and EC is PS then DeltaU is LD",  # 液面缓慢下降→大幅减速
            "if E is PB and EC is PB then DeltaU is LD"  # 液面快速下降→大幅减速
        ]

        for rule in rules:
            self.rule_block.rules.append(fl.Rule.create(rule, self.engine))

        self.engine.rule_blocks.append(self.rule_block)

    def set_target_level(self, target_level):
        self.target_level = target_level
        self.last_level = None
        self.last_time = None
        self.last_filtered_ec = 0.0
        self.last_speed = 0.0  # 重置转速记录

    def calculate_control(self, current_level):
        # 计算液位偏差
        e = current_level - self.target_level

        # 计算液位变化率
        current_time = time.time()
        filtered_ec = self.last_filtered_ec

        if self.last_level is not None and self.last_time is not None:
            time_diff = (current_time - self.last_time)
            if time_diff > 0:  # 避免除以零
                delta_e = (current_level - self.last_level) / time_diff
                alpha = 0.3
                filtered_ec = alpha * delta_e + (1 - alpha) * self.last_filtered_ec

        # 更新状态变量
        self.last_level = current_level
        self.last_time = current_time
        self.last_filtered_ec = filtered_ec

        # 设置输入并处理
        self.engine.input_variable("E").value = e
        self.engine.input_variable("EC").value = filtered_ec
        self.engine.process()

        # 获取转速变化量
        delta_u = self.engine.output_variable("DeltaU").value

        # 计算新转速并限制范围
        new_speed = self.last_speed + delta_u
        new_speed = max(0.0, min(150, new_speed))

        # 更新上次转速记录
        self.last_speed = new_speed

        # 调试信息
        # print(f"液位: {current_level}mm, 偏差: {e:.1f}mm, 变化率: {filtered_ec:.2f}mm/s, "
        #       f"调整量: {delta_u:.1f}rpm, 新转速: {new_speed:.1f}rpm")
        return new_speed

    def plot_membership_functions(self):
        def simple_plot(variable, var_name):
            x = np.arange(variable.minimum, variable.maximum + 0.1, 0.1)
            for term in variable.terms:
                y = [term.membership(x_val) for x_val in x]
                plt.plot(x, y, label=term.name)
            plt.title(f"Membership Functions for {var_name}")
            plt.legend()
            plt.grid(True, alpha=0.3)

        plt.figure(figsize=(10, 4))
        simple_plot(self.engine.input_variable("E"), "Liquid Level Error (E, mm)")
        plt.show()

        plt.figure(figsize=(10, 4))
        simple_plot(self.engine.input_variable("EC"), "Liquid Level Change Rate (EC, mm/s)")
        plt.show()

        plt.figure(figsize=(10, 4))
        simple_plot(self.engine.output_variable("DeltaU"), "Speed Change (DeltaU, rpm)")
        plt.show()


if __name__ == "__main__":
    controller = FuzzyController()
    controller.set_target_level(500)  # 目标液位500mm

    # 测试液位序列（包含接近目标的波动）
    test_levels = [490, 495, 498, 499, 500, 501, 500.5, 499.8, 500.2, 499.9, 500.1, 500]

    for level in test_levels:
        time.sleep(1)  # 模拟时间间隔
        controller.calculate_control(level)

    # 绘制隶属度函数
    controller.plot_membership_functions()
