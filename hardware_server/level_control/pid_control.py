class PIDController:
    def __init__(self, kp, ki, kd, output_min=0, output_max=400,
                 integral_threshold=20, alpha=0.3):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_threshold = integral_threshold  # 积分分离阈值
        self.alpha = alpha  # 微分滤波系数

        # 状态变量
        self.prev_error = 0
        self.prev_measurement = 0
        self.integral = 0
        self.derivative_filtered = 0

    def reset(self):
        self.prev_error = 0
        self.prev_measurement = 0
        self.integral = 0
        self.derivative_filtered = 0

    def update(self, setpoint, measurement):
        error = setpoint - measurement

        # P项
        proportional = self.kp * error

        # I项（带积分分离和抗饱和）
        if abs(error) < self.integral_threshold:
            self.integral += error
        else:
            # 大误差时重置积分防止饱和
            self.integral *= 0.9

        integral_term = self.ki * self.integral

        # D项（使用测量值微分 + 低通滤波）
        derivative_raw = measurement - self.prev_measurement
        self.derivative_filtered = (1 - self.alpha) * self.derivative_filtered + self.alpha * derivative_raw
        derivative_term = -self.kd * self.derivative_filtered  # 负号因为使用测量值微分

        # 计算原始输出
        output = proportional + integral_term + derivative_term

        # 抗饱和处理：输出限幅并反向调整积分
        if output > self.output_max:
            output = self.output_max
            if error > 0:  # 仅当误差方向会导致饱和时才反向调整
                self.integral -= error  # 反向调整积分
        elif output < self.output_min:
            output = self.output_min
            if error < 0:
                self.integral -= error

        # 更新状态
        self.prev_error = error
        self.prev_measurement = measurement

        return output