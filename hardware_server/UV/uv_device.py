import time
import threading
from ctypes import byref
import numpy as np
from hardware.UV.wrapper import *


class UVDevice:
    def __init__(self):
        self.integration_time_us = 96 * 1000  # 初始积分时间，单位: 微秒
        self.average_times = 5  # 初始平均次数
        self.m_uiTimeouts = 1000  # 超时，单位: 毫秒
        self.m_dWavelengths = np.zeros(2048, dtype=np.float64)  # 2048 个双精度浮点数，用于存储波长数据
        self.dark_data = np.zeros(2048, dtype=np.float64)  # 2048 个双精度浮点数，用于存储暗底数据
        self.reference_data = np.zeros(2048, dtype=np.float64)  # 2048 个双精度浮点数，用于存储参照数据
        self.absorbance_data = np.zeros(2048, dtype=np.float64)  # 2048 个双精度浮点数，用于存储吸光度mau数据
        self.hd = None  # 设备句柄作为类的属性
        self.lock = threading.Lock()  # 线程锁

        self.uvState = {'lamp': False, 'avg_times': self.average_times,
                        'integration_time': self.integration_time_us/1000}
        if not self.init_uv():
            print("[紫外] 初始化设备失败")
            return

    def get_uv_state(self):
        return self.uvState

    # ========================== 获取设备列表 ============================= #
    def get_device_list(self):
        """
        获取设备列表。

        返回:
        DEVLSTUSB数组或None: 如果成功获取到设备列表，返回DEVLSTUSB数组；否则返回None。
        """
        devlst = (DEVLSTUSB * 10)()  # 假设最多获取10个设备
        devCnts = c_uint32(0)
        ret = modbus_splibex.SPLIBEX_GetDevList(self.hd, devlst, byref(devCnts), 0)
        if devCnts.value <= 0:
            print(f"[紫外] 设备数量: {devCnts.value}")
            return None
        if ret == 0:
            print(f"[紫外] 设备数量: {devCnts.value}")
            for i in range(devCnts.value):
                print(f"[紫外] 设备 {i + 1}:")
                print(f"[紫外]   序列号: {devlst[i].serialnumber.decode()}")
                print(f"[紫外]   描述: {devlst[i].description.decode()}")
        else:
            print("[紫外] [Error] 获取设备列表失败")
        return devlst

    # ========================== 打开设备 ============================= #
    def open_deviceby_name(self, dev_name):
        """
        根据设备名称打开设备。

        参数:
        dev_name (str): 设备名称。

        返回:
        bool: 如果设备成功打开并初始化就绪，返回True；否则返回False。
        """
        ret = modbus_splibex.SPLIBEX_Open(self.hd, dev_name.encode('utf-8'))
        if ret == 0:
            print(f"[紫外] 设备 {dev_name} 打开成功")
            if self.get_integration_time() is not None:
                print("[紫外] 设备初始化并准备就绪")
                return True
            print("[紫外] 读取积分时间失败，关闭设备")
            modbus_splibex.SPLIBEX_Close(self.hd)
            return False
        print(f"[紫外] 设备 {dev_name} 打开失败")
        return False

    # ========================== 初始化 & 关闭 ============================= #
    def init_uv(self):
        """
        初始化紫外设备。

        返回:
        bool: 如果设备初始化并打开成功，返回True；否则返回False。
        """
        integration_time_us = self.integration_time_us
        average_times = self.average_times

        self.hd = SPLIB_HANDLE()
        ret = modbus_splibex.SPLIBEX_Init(byref(self.hd), 0)  # 0 = USB
        if ret != 0:
            return False

        device_list = self.get_device_list()
        if device_list:
            device_opened = False
            for device in device_list:
                serialnumber = device.serialnumber.decode().strip()
                print(f"[紫外] 尝试打开设备：序列号 {serialnumber}")
                if self.open_deviceby_name(serialnumber):
                    print(f"[紫外] [Success] 设备 {serialnumber} 成功打开")
                    device_opened = True
                    break
            if not device_opened:
                print("[紫外] [Error] 所有设备都无法打开")
        else:
            print("[紫外] [Error] 没有可用的设备")

        self.set_integration_time(integration_time_us)
        self.set_average(average_times)
        self.get_Wavelengths()
        self.set_background()
        self.set_reference()
        print("[紫外] 设备初始化并打开成功")
        return True

    def close_device(self):
        """
        关闭设备。
        """
        self.enable_lamp(0)
        modbus_splibex.SPLIBEX_Close(self.hd)
        modbus_splibex.SPLIBEX_DeInit(self.hd)
        print("[紫外] 设备关闭")

    # ========================== 更新超时时间 ============================= #
    def update_timeouts(self):
        """
        更新超时时间。

        根据积分时间和平均次数计算新的超时时间，并更新全局变量m_uiTimeouts。
        """
        self.m_uiTimeouts = int((70 + self.integration_time_us / 1000) * self.average_times + 1000)
        print(f"[紫外] 更新超时: {self.m_uiTimeouts} ms")

    # ========================== 参数设置 ============================= #
    def set_integration_time(self, time_us):
        """
        设置设备的积分时间。

        参数:
        time_us (int): 积分时间，单位为微秒。

        返回:
        None
        """
        ret = modbus_splibex.SPLIBEX_SetIntegrationTime(self.hd, c_uint32(time_us))
        if ret == 0:
            self.integration_time_us = time_us
            self.uvState['integration_time'] = time_us / 1000
            print(f"[紫外] 积分时间设置为: {self.integration_time_us} us")
            self.update_timeouts()
        else:
            print("[紫外] 设置积分时间失败")

    def set_average(self, avg_times):
        """
        设置设备的平均次数。

        参数:
        avg_times (int): 平均次数。

        返回:
        None
        """
        ret = modbus_splibex.SPLIBEX_SetAccAvg(self.hd, c_uint32(avg_times))
        if ret == 0:
            self.average_times = avg_times
            self.uvState['avg_times'] = avg_times
            print(f"[紫外] 平均次数设置为: {self.average_times}")
            self.update_timeouts()
        else:
            print("[紫外] 设置平均次数失败")

    # ========================== 参数读取 ============================= #
    def get_integration_time(self):
        """
        读取设备的积分时间。

        返回:
        int或None: 如果成功读取积分时间，返回积分时间（单位为微秒）；否则返回None。
        """
        integ_time = c_uint32(0)
        ret = modbus_splibex.SPLIBEX_GetIntegrationTime(self.hd, byref(integ_time))
        if ret == 0:
            self.integration_time_us = integ_time.value
            print(f"[紫外] 读取积分时间: {self.integration_time_us} us")
            self.update_timeouts()
            return self.integration_time_us
        print("[紫外] 读取积分时间失败")
        return None

    def get_average(self):
        """
        读取设备的平均次数。

        返回:
        int或None: 如果成功读取平均次数，返回平均次数；否则返回None。
        """
        avg_times = c_uint32(0)
        ret = modbus_splibex.SPLIBEX_GetAccAvg(self.hd, byref(avg_times))
        if ret == 0:
            self.average_times = avg_times.value
            print(f"[紫外] 读取平均次数: {self.average_times}")
            self.update_timeouts()
            return self.average_times
        print("[紫外] 读取平均次数失败")
        return None

    # ========================== 获取设置灯参数 ============================= #
    def set_lamp_pulse(self, low_level, high_level):
        """
        设置灯的脉冲参数。

        参数:
        low_level (int): 灯脉冲的低电平值。
        high_level (int): 灯脉冲的高电平值。

        返回:
        None
        """
        ret = modbus_splibex.SPLIBEX_SetLampPulse(self.hd, c_uint32(low_level), c_uint32(high_level))
        if ret == 0:
            print(f"[紫外] 设置灯脉冲为: {low_level} (低) 和 {high_level} (高)")
        else:
            print("[紫外] 设置灯脉冲失败")

    def get_lamp_pulse(self):
        """
        获取灯的脉冲参数。

        返回:
        tuple或None: 如果成功获取灯脉冲参数，返回一个包含低电平和高电平值的元组；否则返回None。
        """
        low_level = c_uint32(0)
        high_level = c_uint32(0)
        ret = modbus_splibex.SPLIBEX_GetLampPulse(self.hd, byref(low_level), byref(high_level))
        if ret == 0:
            print(f"[紫外] 获取灯脉冲: 低电平 = {low_level.value}, 高电平 = {high_level.value}")
            return low_level.value, high_level.value
        print("[紫外] [Error] 获取灯脉冲失败")
        return None, None

    def enable_lamp(self, on):
        """
        启动或关闭灯。

        参数:
        on (int): 灯的开关状态，1表示开启，0表示关闭。

        返回:
        None
        """
        ret = modbus_splibex.SPLIBEX_LampEnable(self.hd, c_uint32(on))
        if ret == 0:
            print(f"[紫外] 灯 {'开启' if on else '关闭'}")
            self.uvState['lamp'] = True if on else False
        else:
            print("[紫外] 设置灯状态失败")

    def get_lamp_status(self):
        """
        获取灯的当前状态。

        返回:
        int或None: 如果成功获取灯的状态，返回1表示开启，0表示关闭；否则返回None。
        """
        lamp_status = c_uint32(0)
        ret = modbus_splibex.SPLIBEX_LampStatus(self.hd, byref(lamp_status))
        if ret == 0:
            print(f"[紫外] 当前灯状态: {'开启' if lamp_status.value == 1 else '关闭'}")
            return lamp_status.value
        print("[紫外] [Error] 获取灯状态失败")
        return None

    # ========================== 获取波长校准参数 ============================= #
    def get_Wavelengths(self):
        """
        获取波长校准参数并计算波长数据。

        返回:
        numpy.ndarray或None: 如果成功获取波长校准参数并计算出波长数据，返回包含波长数据的numpy数组（保留两位小数）；否则返回None。
        """
        if self.m_dWavelengths[0] == 0:
            wave_params = (c_double * 4)()
            ret = modbus_splibex.SPLIBEX_GetWaveCalParams(self.hd, wave_params)
            if ret == 0:
                print(f"[紫外] 获取波长校准参数: {list(wave_params)}")
                pixels = np.arange(2048)
                self.m_dWavelengths[:] = (pixels ** 3 * wave_params[3] + pixels ** 2 * wave_params[2]
                                          + pixels * wave_params[1] + wave_params[0])
                print("[紫外] 波长数据获取成功")
                return np.around(self.m_dWavelengths, decimals=2)
            else:
                print("[紫外] [Error] 获取波长校准参数失败")
                return None
        else:
            return np.around(self.m_dWavelengths, decimals=2)

    # ========================== 数据采集 ============================= #
    def collect_one(self):
        """
        采集一次数据。

        返回:
        numpy.ndarray或None: 如果成功采集到数据，返回包含采集数据的numpy数组；否则返回None。
        """
        self.lock.acquire()  # 获取锁
        try:
            pixel_start = 0
            pixel_stop = 2047
            num_pixels = pixel_stop - pixel_start + 1
            buf_len = num_pixels * 2  # 每个像素2字节
            recv_buf = (ctypes.c_ubyte * buf_len)()
            real_len = c_uint32(0)
            # print(f"[紫外] [Info] 准备采集数据，超时: {self.m_uiTimeouts} ms")
            ret = modbus_splibex.SPLIBEX_CollectionBytes(self.hd, recv_buf, pixel_start, pixel_stop, byref(real_len),
                                                        self.m_uiTimeouts)
            if ret != 0:
                print(f"[紫外] [Error] 采集失败，错误码: {ret}")
                return None
            # print(f"[紫外] [Info] 成功采集 {num_pixels} 个像素的数据")
            data = self.parse_data(recv_buf)
            return data
        finally:
            self.lock.release()  # 确保锁释放

    def parse_data(self, buf):
        """
        解析采集到的数据。

        参数:
        buf (ctypes.c_ubyte数组): 采集到的原始数据缓冲区。

        返回:
        numpy.ndarray: 解析后的数据数组。
        """
        buf = np.frombuffer(buf, dtype=np.uint8)
        # 注意数据截断
        data = (buf[::2].astype(np.uint16) << 8) | buf[1::2].astype(np.uint16)
        return data

    # ========================== 关灯采集一次数据作为暗底数据 ============================= #
    def set_background(self):
        """
        关灯采集一次数据作为暗底数据。

        返回:
        None
        """
        self.enable_lamp(0)
        time.sleep(2)
        data = self.collect_one()
        if data is not None:
            self.dark_data[:] = data.astype(np.float64)
            print(f"[紫外] 设置暗底成功")
        else:
            print("[紫外] 设置暗底失败")

    # ========================== 开灯采集新数据（减去暗底数据）作为参考数据 ============================= #
    def set_reference(self):
        """
        开灯采集新数据（减去暗底数据）作为参考数据。

        返回:
        None
        """
        self.enable_lamp(1)
        time.sleep(2)
        data = self.collect_one()
        if data is not None:
            self.reference_data[:] = data.astype(np.float64) - self.dark_data
            print(f"[紫外] 参比设置成功")
        else:
            print("[紫外] 参比设置失败")

    # ========================== 采集新数据计算吸光度 ============================= #
    def get_absorbance(self):
        """
        采集新数据并计算吸光度。

        返回:
        numpy.ndarray或None: 如果成功采集到数据并计算出吸光度，返回包含吸光度数据的numpy数组；否则返回None。
        """
        data = self.collect_one()
        if data is not None:
            signal = data.astype(np.float64) - self.dark_data
            valid_mask = (signal > 0) & (self.reference_data > 0)
            self.absorbance_data[valid_mask] = 1000 * np.log10(self.reference_data[valid_mask] / signal[valid_mask])
            self.absorbance_data[~valid_mask] = 0.0
            return self.absorbance_data
        else:
            print("[紫外] [Error] 没有采集到数据")
            return None

    # ========================== 主函数 ============================= #
    def main(self):
        """
        主函数，用于初始化设备、进行设备操作和数据采集，并最终关闭设备。
        """
        try:
            self.get_integration_time()
            self.get_average()
            self.get_Wavelengths()
            self.set_lamp_pulse(1500000, 10000)
            self.get_lamp_pulse()
            self.set_integration_time(15100 * 5)
            self.set_average(20)
            self.set_background()
            self.set_reference()
            self.get_absorbance()

        finally:
            self.close_device()


if __name__ == "__main__":
    uv_device = UVDevice()
    uv_device.main()