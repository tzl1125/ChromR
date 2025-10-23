import ctypes
from ctypes import (
    c_int, c_double, c_uint, c_ubyte,
    c_ushort, c_uint32, c_uint16, c_uint8,
    Structure, POINTER, pointer, byref
)


# 定义结构体
class PynScanConfigHead(Structure):
    _fields_ = [
        ('scan_type', c_ubyte),
        ('scanConfigIndex', c_ushort),
        ('scanConfig_serial_number', c_ubyte * 8),
        ('config_name', c_ubyte * 40),
        ('num_repeats', c_ushort),
        ('num_sections', c_ubyte)
    ]


class PynScanSection(Structure):
    _fields_ = [
        ('section_scan_type', c_ubyte),
        ('width_px', c_ubyte),
        ('wavelength_start_nm', c_ushort),
        ('wavelength_end_nm', c_ushort),
        ('num_patterns', c_ushort),
        ('exposure_time', c_ushort)
    ]


class PynScanConfig(Structure):
    _fields_ = [
        ('head', PynScanConfigHead),
        ('section', PynScanSection * 5)
    ]


class PynScanResults(Structure):
    _fields_ = [
        ('header_version', c_uint32),
        ('scan_name', c_ubyte * 20),
        ('year', c_ubyte),
        ('month', c_ubyte),
        ('day', c_ubyte),
        ('day_of_week', c_ubyte),
        ('hour', c_ubyte),
        ('minute', c_ubyte),
        ('second', c_ubyte),
        ('system_temp_hundredths', c_ushort),
        ('detector_temp_hundredths', c_ushort),
        ('humidity_hundredths', c_ushort),
        ('lamp_pd', c_ushort),
        ('scanDataIndex', c_uint32),
        ('ShiftVectorCoeffs', c_double * 3),
        ('PixelToWavelengthCoeffs', c_double * 3),
        ('serial_number', c_ubyte * 8),
        ('adc_data_length', c_ushort),
        ('black_pattern_first', c_ubyte),
        ('black_pattern_period', c_ubyte),
        ('pga', c_ubyte),
        ('cfg', PynScanConfig),
        ('wavelength', c_double * 864),
        ('intensity', c_int * 864),
        ('length', c_int)
    ]


# 加载DLL
wrapper = ctypes.CDLL('./NIR/lib/wrapper.dll')

# 定义函数原型

# 初始化usb hid，返回设备数量
wrapper.dlpInitUsb.argtypes = []
wrapper.dlpInitUsb.restype = c_int

# 打开设备
# 参数：deviceIndex，设备索引，从0开始
# 返回值：成功 0，失败(参见错误码) 
wrapper.dlpOpenByUsb.argtypes = [c_int]
wrapper.dlpOpenByUsb.restype = c_int

# 关闭设备
# 参数：deviceIndex，设备索引，从0开始
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpClose.argtypes = [c_int]
wrapper.dlpClose.restype = None

# 获取配置信息
# 参数：config，配置信息结构体指针
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpGetConfigInfo.argtypes = [POINTER(PynScanConfig)]
wrapper.dlpGetConfigInfo.restype = c_int

# 获取扫描结果
# 参数：results，扫描结果结构体指针
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpGetScanResults.argtypes = [POINTER(PynScanResults)]
wrapper.dlpGetScanResults.restype = c_int

# 获取指定长度波长wavelengths
# 参数：wavelengths，波长数组指针，最大数组长度为228
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpGetWavelengths.argtypes = [POINTER(c_double), c_int]
wrapper.dlpGetWavelengths.restype = c_int

# 获取指定长度强度值intensities
# 参数：activeIndex，活动索引，从0开始
# 参数：intensities， 强度数组指针，最大数组长度为228
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpGetIntensities.argtypes = [c_int, POINTER(c_int), c_int]
wrapper.dlpGetIntensities.restype = c_int

# 获取设备指定长度参考强度（设备内置参比值）
# 参数：ref_intensities，参考强度数组指针，最大数组长度为228
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpGetRefIntensityFromDevice.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
wrapper.dlpGetRefIntensityFromDevice.restype = ctypes.c_int

# 设置内置光源开关状态
# 参数：status，开关状态，0 关闭，1 打开
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpSetLampStatus.argtypes = [c_int]
wrapper.dlpSetLampStatus.restype = c_int

# 设置pga增益倍数
# 参数：gain，增益倍数，0-7
# 返回值：设置pga增益。固定模式，增益值gain为 1,2,4,8,16,32,64。自动模式，增益值gain为 0
wrapper.dlpSetPgaGain.argtypes = [c_int]
wrapper.dlpSetPgaGain.restype = c_int

# 获取设备uuid
# 参数：uuid，uuid数组指针
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpGetDeviceUuid.argtypes = [POINTER(c_ubyte)]
wrapper.dlpGetDeviceUuid.restype = c_int

# 获取温湿度
# 参数：temp，温度指针
# 参数：humidity，湿度指针
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpGetHumTemp.argtypes = [POINTER(c_uint32), POINTER(c_int)]
wrapper.dlpGetHumTemp.restype = c_int

# 获取电池信息，包括电池电压和剩余电量
# 参数：voltage，电池电压指针
# 参数：capacity，剩余电量百分比指针
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpGetBatteryInfo.argtypes = [POINTER(c_uint32), POINTER(c_uint32)]
wrapper.dlpGetBatteryInfo.restype = c_int

# 设置平均次数（重复测量次数，输出平均值）
# 参数：avgTimes，平均次数，范围 1-255
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpSetAvgTimes.argtypes = [c_uint16]
wrapper.dlpSetAvgTimes.restype = c_int

# 启用按钮
# 参数：status，启用状态，0 关闭，1 打开
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpEnableButtonPress.argtypes = [c_int]
wrapper.dlpEnableButtonPress.restype = c_int

# 获取按钮状态
# 参数：status 按钮状态指针，0 未按下，1 按下
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpGetButtonPressStatus.argtypes = [POINTER(c_int)]
wrapper.dlpGetButtonPressStatus.restype = c_int

# 设置蓝牙状态
# 参数：status，蓝牙状态，0 关闭，1 打开
# 返回值：成功 0，失败(参见错误码)
wrapper.dlpSetBluetoothStatus.argtypes = [c_int]
wrapper.dlpSetBluetoothStatus.restype = c_int

# 错误代码定义
RetSuccess = 0
RetGetSpecNumError = -1
RetInitError = -2
RetOpenSpecError = -3
RetGetOemSpecSerialNumberError = -4
RetSetIntegrateTimeError = -5
RetGetIntegrateTimeError = -6
RetSetAvgTimesError = -7
RetGetAvgTimesError = -8
RetGetWlsError = -9
RetGetSpecValuesError = -10
RetEnumerateError = -11
RetUsbConnectError = -12
RetGetNumScanCfgError = -13
RetGetActiveScanIndexError = -14
RetSetActiveScanIndexError = -15
RetSetCurrentActiveIndexError = -16
RetGetScanCfgError = -17
RetPerformScanError = -18
RetGetFileSizeToReadError = -19
RetGetFileError = -20
RetWlsLengthError = -21
RetGetPgaGainError = -22
RetSetPgaGainError = -230
RetSetFixedPgaGainError = -231
RetSetScanNumRepeatsError = -24
RetSetUARTConnectedError = -25
RetGetSerialNumberError = -26
RetSetSerialNumberError = -27
RetWlsNumIsOverFlow = -28
RetInterpretError = -29
RetInterpReferenceError = -30
RetEnableBleError = -31
RetDisableBleError = -32
RetEnableButtonPressError = -33
RetDisableButtonPressError = -34
