import ctypes
from ctypes import c_uint32, c_void_p, c_double

path = './UV/lib'
class DEVLSTUSB(ctypes.Structure):
    _fields_ = [
        ("devnums", ctypes.c_ulong),
        ("serialnumber", ctypes.c_char * 16),
        ("description", ctypes.c_char * 64)
    ]


# DLL 路径
dll_path = f"{path}/myserial64.dll"
myserial = ctypes.cdll.LoadLibrary(dll_path)
dll_path = f"{path}/ftd2xx64.dll"
ftd2xx = ctypes.cdll.LoadLibrary(dll_path)
dll_path = f"{path}/modbus_splib64.dll"
modbus_splib = ctypes.cdll.LoadLibrary(dll_path)
dll_path = f"{path}/modbus_splibEx64.dll"
modbus_splibex = ctypes.cdll.LoadLibrary(dll_path)

# 句柄类型
SPLIB_HANDLE = c_void_p

# ========================== DLL 函数定义 ============================= #

modbus_splibex.SPLIBEX_Init.restype = ctypes.c_int
modbus_splibex.SPLIBEX_Init.argtypes = [ctypes.POINTER(SPLIB_HANDLE), c_uint32]

modbus_splibex.SPLIBEX_DeInit.restype = ctypes.c_int
modbus_splibex.SPLIBEX_DeInit.argtypes = [SPLIB_HANDLE]

modbus_splibex.SPLIBEX_OpenByIndex.restype = ctypes.c_int
modbus_splibex.SPLIBEX_OpenByIndex.argtypes = [SPLIB_HANDLE, c_uint32]

modbus_splibex.SPLIBEX_Close.restype = ctypes.c_int
modbus_splibex.SPLIBEX_Close.argtypes = [SPLIB_HANDLE]

modbus_splibex.SPLIBEX_SetIntegrationTime.restype = ctypes.c_int
modbus_splibex.SPLIBEX_SetIntegrationTime.argtypes = [SPLIB_HANDLE, c_uint32]

modbus_splibex.SPLIBEX_GetIntegrationTime.restype = ctypes.c_int
modbus_splibex.SPLIBEX_GetIntegrationTime.argtypes = [SPLIB_HANDLE, ctypes.POINTER(c_uint32)]

modbus_splibex.SPLIBEX_SetAccAvg.restype = ctypes.c_int
modbus_splibex.SPLIBEX_SetAccAvg.argtypes = [SPLIB_HANDLE, c_uint32]

modbus_splibex.SPLIBEX_GetAccAvg.restype = ctypes.c_int
modbus_splibex.SPLIBEX_GetAccAvg.argtypes = [SPLIB_HANDLE, ctypes.POINTER(c_uint32)]

modbus_splibex.SPLIBEX_CollectionBytes.restype = ctypes.c_int
modbus_splibex.SPLIBEX_CollectionBytes.argtypes = [SPLIB_HANDLE, ctypes.POINTER(ctypes.c_ubyte), c_uint32, c_uint32,
                                                   ctypes.POINTER(c_uint32), c_uint32]

# ========================== 新增函数定义 ============================= #

# 设置灯脉冲
modbus_splibex.SPLIBEX_SetLampPulse.restype = ctypes.c_int
modbus_splibex.SPLIBEX_SetLampPulse.argtypes = [SPLIB_HANDLE, c_uint32, c_uint32]

# 获取灯脉冲
modbus_splibex.SPLIBEX_GetLampPulse.restype = ctypes.c_int
modbus_splibex.SPLIBEX_GetLampPulse.argtypes = [SPLIB_HANDLE, ctypes.POINTER(c_uint32), ctypes.POINTER(c_uint32)]

# 启动或关闭灯
modbus_splibex.SPLIBEX_LampEnable.restype = ctypes.c_int
modbus_splibex.SPLIBEX_LampEnable.argtypes = [SPLIB_HANDLE, c_uint32]

# 获取灯的状态
modbus_splibex.SPLIBEX_LampStatus.restype = ctypes.c_int
modbus_splibex.SPLIBEX_LampStatus.argtypes = [SPLIB_HANDLE, ctypes.POINTER(c_uint32)]

# 获取波长校准参数
modbus_splibex.SPLIBEX_GetWaveCalParams.restype = ctypes.c_int
modbus_splibex.SPLIBEX_GetWaveCalParams.argtypes = [SPLIB_HANDLE, ctypes.POINTER(c_double)]

# 获取设备列表
modbus_splibex.SPLIBEX_GetDevList.restype = ctypes.c_int
modbus_splibex.SPLIBEX_GetDevList.argtypes = [
    ctypes.c_void_p,  # SPLIB_HANDLE hd
    ctypes.POINTER(DEVLSTUSB),  # DEVLSTUSB* devlst
    ctypes.POINTER(ctypes.c_uint32),  # uint32_t& devCnts
    ctypes.c_uint32  # uint32_t uiGetType
]

# 打开设备
modbus_splibex.SPLIBEX_Open.restype = ctypes.c_int
modbus_splibex.SPLIBEX_Open.argtypes = [
    ctypes.c_void_p,  # SPLIB_HANDLE hd
    ctypes.c_char_p  # const char* dev
]
