import numpy as np
import threading

from hardware.NIR.wrapper import *


class NIRDevice:
    def __init__(self):
        self.nirState = {'avg_times': 6}
        # 900 - 1700nm设备，共计228个波长点
        self.WLS_NUM = 228
        self.wavelengths = np.zeros(self.WLS_NUM, dtype=np.float64)
        self.deviceIndex = 0
        self.dark_data = np.zeros(self.WLS_NUM, dtype=np.float64)  # 用于存储暗底数据
        self.reference_data = np.zeros(self.WLS_NUM, dtype=np.float64)  # 用于存储参照数据
        self.absorbance_data = np.zeros(self.WLS_NUM, dtype=np.float64)  # 用于存储吸光度mau数据
        self.intensity_data = np.zeros(self.WLS_NUM, dtype=np.float64)  # 用于存储当前强度值
        self.lock = threading.Lock()  # 线程锁

        self.init_nir()

    # 初始化设备
    def init_nir(self):
        """
        初始化USB设备并打开指定设备，获取设备配置信息和波长数据。

        步骤:
        1. 初始化USB设备，返回连接设备数量，并在控制台打印设备序列号和波长范围。
        2. 打开指定设备。
        3. 获取设备配置信息，包括序列号和波长范围。
        4. 获取设备的波长数据。
        """
        # 初始化USB,返回连接设备数量。初始化设备时，会自动在控制台打印设备序列号和波长范围。
        ret = wrapper.dlpInitUsb()
        # 打开设备
        ret = wrapper.dlpOpenByUsb(self.deviceIndex)
        if ret == RetSuccess:
            print("[近红外] Open Device Success.\n")
        else:
            print(f"[近红外] Open Device Failed with code: {ret}")

        # 获取配置信息
        config = PynScanConfig()
        ret = wrapper.dlpGetConfigInfo(ctypes.byref(config))
        if ret == RetSuccess:
            serial = bytes(config.head.scanConfig_serial_number).decode('ascii').strip('\x00')
            print(f"[近红外] Device serial number: {serial}")
            print(
                f"[近红外] Wavelength range: {config.section[0].wavelength_start_nm} - {config.section[0].wavelength_end_nm} nm\n")

        wavelengths = (ctypes.c_double * self.WLS_NUM)()
        wrapper.dlpGetWavelengths(wavelengths, self.WLS_NUM)
        self.wavelengths[:] = np.around(np.ctypeslib.as_array(wavelengths), decimals=2)

        self.set_lamp_status(1)
        self.set_pga_gain(32)
        self.set_avg_times(6)

    def get_nir_state(self):
        return self.nirState

    # 获取扫描结果
    def get_scan_results(self):
        """
        获取扫描结果，包括系统温度、设备湿度和对应强度值。

        返回:
            如果获取成功，返回强度值数组；否则返回None。
        """
        results = PynScanResults()
        ret = wrapper.dlpGetScanResults(ctypes.byref(results))
        if ret >= 0:
            print("[近红外] 获取扫描结果成功")
            print("[近红外] 系统温度: {:.2f}℃".format(results.system_temp_hundredths / 100.0))
            print("[近红外] 设备湿度: {:.2f}%".format(results.humidity_hundredths / 100.0))
            self.intensity_data[:] = np.ctypeslib.as_array(results.intensity)[0:self.WLS_NUM]

            return self.intensity_data
        else:
            print(f"[近红外] 扫描结果失败: {ret}")
            return None

    # 设置暗背景
    def set_background(self):
        """
        设置暗背景数据，调用 get_intensities 函数获取当前强度值并存储到 dark_data 中。
        """
        self.dark_data[:] = self.get_intensities()
        print("[近红外] 已设置暗背景")

    # 设置参比
    def set_reference(self):
        """
        设置参比数据，调用 get_intensities 函数获取当前强度值并存储到 reference_data 中。
        """
        self.reference_data[:] = self.get_intensities() - self.dark_data
        print("[近红外] 已设置参比光谱")

    def get_absorbance(self):
        """
        计算并返回吸光度数据。

        步骤:
        1. 调用 get_intensities 函数获取当前强度值。
        2. 计算信号值（当前强度值减去暗背景值）。
        3. 计算吸光度，仅对信号值和参比值都大于0的波长点进行计算。
        4. 对于不满足条件的波长点，吸光度设为0。

        返回:
            如果采集到数据，返回吸光度数组；否则返回None。
        """
        data = self.get_intensities()
        if data is not None:
            signal = data - self.dark_data
            valid_mask = (signal > 0) & (self.reference_data > 0)
            self.absorbance_data[valid_mask] = 1000 * np.log10(self.reference_data[valid_mask] / signal[valid_mask])
            self.absorbance_data[~valid_mask] = 0.0
            return self.absorbance_data
        else:
            print("[近红外] [Error] 没有采集到数据")
            return None

    # 获取波长值
    def get_wavelengths(self):
        """
        获取228个波长值。

        返回:
            包含228个波长值的数组。
        """
        return self.wavelengths

    # 获取波长对应强度值
    def get_intensities(self, activeIndex=0, num=None):
        """
        获取扫描强度值。 可指定起始波长，和扫描的波长数。

        参数:
            activeIndex (int): 起始波长索引，默认为0。
            num (int): 扫描的波长数，默认为228。

        返回:
            如果获取成功，返回强度值数组；否则返回None。
        """
        self.lock.acquire()  # 获取锁
        try:
            if num is None:
                num = self.WLS_NUM
            intensities = (ctypes.c_int * num)()
            ret = wrapper.dlpGetIntensities(activeIndex, intensities, num)
            if ret >= 0:
                self.intensity_data[:] = np.ctypeslib.as_array(intensities)
                return self.intensity_data
            else:
                print(f"[近红外] 获取强度失败: {ret}")
                return None
        finally:
            self.lock.release()  # 确保锁释放

    # 控制内置光源状态
    def set_lamp_status(self, enable):
        """
        设置内置光源状态（打开或关闭）。(1:on 0:off)。开启后扫描速度更快。

        参数:
            enable (int): 光源状态，1表示打开，0表示关闭。

        输出:
            打印光源状态设置结果。
        """
        ret = wrapper.dlpSetLampStatus(enable)
        print(f"[近红外] 光源状态： {'打开' if enable else '关闭'}" if ret >= 0 else f"[近红外] 设置失败: {ret}")

    # 获取设备uuid
    def get_device_uuid(self):
        """
        获取设备的UUID。

        输出:
            打印设备的UUID，如果获取失败则打印错误信息。

        返回:
            包含设备UUID的字节数组。
        """
        uuid = (ctypes.c_ubyte * 8)()
        ret = wrapper.dlpGetDeviceUuid(uuid)
        if ret >= 0:
            print("[近红外] 设备UUID: " + ":".join(f"{b:02X}" for b in uuid))
        else:
            print(f"[近红外] 获取UUID失败: {ret}")
        return uuid

    # 获取温湿度
    def get_hum_temp(self):
        """
        获取设备的湿度和温度。

        返回:
            如果获取成功，返回湿度和温度的元组；否则返回None。
        """
        humidity = ctypes.c_uint32()
        temperature = ctypes.c_int()
        ret = wrapper.dlpGetHumTemp(ctypes.byref(humidity), ctypes.byref(temperature))
        if ret >= 0:
            print(f"[近红外] 湿度: {humidity.value / 100.0:.2f}%")
            print(f"[近红外] 温度: {temperature.value / 100.0:.2f}摄氏度")
            return humidity.value / 100.0, temperature.value / 100.0
        else:
            print(f"[近红外] Get humidity/temperature failed: {ret}")
            return None

    # 设置PGA增益倍数。固定模式，增益值gain为 1,2,4,8,16,32,64。自动模式，增益值gain为 0。
    def set_pga_gain(self, gain):
        """
        设置PGA增益倍数(1,2,4,8,16,32,64),设置32或者64。

        参数:
            gain (int): 增益倍数。

        输出:
            打印增益设置结果。
        """
        ret = wrapper.dlpSetPgaGain(gain)
        if ret >= 0:
            print(f"[近红外] 增益成功设置为: {gain} \n")
        else:
            print(f"[近红外] 增益设置失败: {ret}\n")

    # 获取当前PGA增益
    def get_pga_gain(self):
        """
        获取当前的PGA增益值。

        返回:
            如果获取成功，返回当前PGA增益值；否则返回None。
        """
        pga_gain = ctypes.c_int()
        ret = wrapper.dlpGetPgaGain(ctypes.byref(pga_gain))
        if ret >= 0:
            print(f"[近红外] 当前PGA增益为: {pga_gain.value}\n")
            return pga_gain.value
        else:
            print(f"[近红外] 获取PGA增益失败: {ret}\n")
            return None

    # 设置平均次数（重复测量次数，输出平均值）
    def set_avg_times(self, avg_times=6):
        """
        设置平均次数。

        参数:
            avg_times (int): 平均次数，默认为6。

        输出:
            打印平均次数设置结果。
        """
        ret = wrapper.dlpSetAvgTimes(avg_times)
        if ret >= 0:
            print(f"[近红外] 平均次数设置为 {avg_times} 成功\n")
            self.nirState['avg_times'] = avg_times
        else:
            print(f"[近红外] 设置失败: {ret} ({RetSetAvgTimesError if ret == -7 else '未知错误'})\n")

    # 主函数
    def main(self):
        """
        主函数，初始化设备并进入命令循环。

        步骤:
        1. 初始化设备。
        2. 进入命令循环，等待用户输入命令。
        3. 根据用户输入的命令调用相应的函数。
        4. 输入 'q' 退出循环并关闭设备。
        """

        while True:
            print("[近红外] 输入 'q' 退出: ", end='')
            cmd = input().strip().lower()

            if cmd == 'q':
                wrapper.dlpClose(self.deviceIndex)
                break

            try:
                if cmd == '1':
                    result = self.get_scan_results()
                    if result is not None:
                        intensity = result
                        print(f"[近红外] 扫描得到的强度值: {intensity}")
                elif cmd == '2':
                    wavelengths = self.get_wavelengths()
                    print(f"[近红外] 获取到的228个波长值: {wavelengths}")
                elif cmd == '3':
                    intensities = self.get_intensities()
                    if intensities is not None:
                        print(f"[近红外] 获取到的波长对应强度值: {intensities}")
                elif cmd == '4':
                    self.set_reference()
                    print("[近红外] 已成功设置参比数据")
                elif cmd == '5':
                    self.set_lamp_status(1)  # 打开光源
                elif cmd == '6':
                    self.get_device_uuid()
                elif cmd == '7':
                    self.get_hum_temp()
                elif cmd == '8':
                    self.set_pga_gain(32)  # 设置增益为32
                elif cmd == '9':
                    self.get_pga_gain()
                elif cmd == 'a':
                    self.set_avg_times()
                elif cmd == 'b':
                    a = self.get_absorbance()
                    if a is not None:
                        print(f"[近红外] 获取到的波长对应吸光度mau: {a}")
                elif cmd == 'c':
                    self.set_background()
                else:
                    print("[近红外] Invalid command\n")

                print("\n")

            except Exception as e:
                print(f"[近红外] Error processing command: {str(e)}")


if __name__ == "__main__":
    nir_device = NIRDevice()
    nir_device.main()