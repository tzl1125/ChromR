import struct

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


class PumpController:
    """
    Modbus蠕动泵控制器，支持多泵组管理，泵转速为0-400rpm

    Attributes:
        client (ModbusSerialClient): Modbus RTU客户端
        pump_addresses (list): 管理的泵地址列表
        pump_states (dict): 泵状态记录（启停、方向、转速等）
    """

    # 寄存器地址映射（根据协议文档定义）
    COIL_ADDRESS = {
        'start_stop': 0x1001,  # 启停控制 0停/1启
        'drain': 0x1002,  # 排空控制 0关/1开
        'direction': 0x1003,  # 方向控制 0正/1反
        'enable_485': 0x1004,  # 485使能 0失能/1使能
    }

    HOLDING_REGISTERS = {
        'speed_setting': 0x3001,  # 转速设置（连续两个寄存器：0x3001高16位，0x3002低16位）
        'speed_real': 0x3005  # 实时转速（连续两个寄存器：0x3005高16位，0x3006低16位）
    }

    def __init__(self, pump_addresses, port='com4', client=None, baudrate=9600, bytesize=8, parity='N', stopbits=1):
        """
        初始化泵控制器

        Args:
            port (str): 串口路径（如'com1'）
            pump_addresses (list): 管理的泵地址列表（基于拨码开关计算的地址）
            baudrate (int): 波特率，默认9600
            bytesize (int): 数据位，默认8
            parity (str): 校验位，默认'N'
            stopbits (int): 停止位，默认1
        """
        if client is None:
            self.client = ModbusSerialClient(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits
            )
            self.client.connect()
        else:
            self.client = client
        self.pump_addresses = pump_addresses
        # 初始化状态记录
        self.pump_states = {}
        for addr in pump_addresses:
            self.pump_states[addr] = {'start_stop': False, 'drain': False, 'direction': False, 'speed': 0.0,
                                      'name': '无'}
        self.initialize_pumps()

    def __del__(self):
        """
        析构函数，用于在对象销毁时关闭Modbus客户端连接。
        """
        self.client.close()

    def get_client(self):
        return self.client

    def get_pump_states(self):
        """
        获取当前所有泵的状态

        Returns:
            dict: {"address(int)":{'start_stop': False, 'drain': False, 'direction': False, 'speed': 0.0,
                                      'name': '无'},...}
        """
        return self.pump_states

    def set_pump_name(self, pump_name, address=None):
        if address is None:
            address = self.pump_addresses
        for add in address:
            self.pump_states[add].update({'name': pump_name})

    def initialize_pumps(self):
        """初始化所有泵状态：使能485，设置默认方向"""
        self.control_pumps('enable_485', True)  # 使能485控制
        self.control_pumps('direction', False)  # 默认逆时针
        self.control_pumps('start_stop', False)  # 默认停转
        self.control_pumps('drain', False)  # 排空设置为false
        self.control_pumps('speed', 0.0)  # 转速设置为0

    def control_single(self, address, control_type, value):
        """
        单个泵控制底层函数

        Args:
            address (int): 泵地址
            control_type (str): 控制类型（start_stop/drain/direction/enable_485）
            value (bool): 控制值
        """
        try:
            coil_addr = self.COIL_ADDRESS[control_type]
            result = self.client.write_coil(coil_addr, value, slave=address)
            if result.isError():
                raise ModbusException(result)
            # 更新状态记录
            self.pump_states[address].update({control_type: value})
        except ModbusException as e:
            error_msg = f"写入泵（地址: {address}）的 {control_type} 状态时发生错误: {e}"
            print(error_msg)
            raise ModbusException(error_msg)

    def set_speed(self, address, speed):
        """
        设置单个泵转速（单次写入两个寄存器）

        Args:
            address (int): 泵地址
            speed (float): 目标转速值
        """
        try:
            # 将浮点数转为两个16位寄存器值（大端序）
            float_bytes = struct.pack('!f', speed)
            registers = [
                int.from_bytes(float_bytes[:2], byteorder='big'),  # 高16位
                int.from_bytes(float_bytes[2:], byteorder='big')  # 低16位
            ]

            # 一次性写入两个保持寄存器
            result = self.client.write_registers(
                address=self.HOLDING_REGISTERS['speed_setting'],
                values=registers,
                slave=address
            )
            if result.isError():
                raise ModbusException(result)

            # 更新状态记录
            self.pump_states[address]['speed'] = speed
        except ModbusException as e:
            error_msg = f"写入泵（地址: {address}）的转速时发生错误: {e}"
            print(error_msg)
            raise ModbusException(error_msg)

    def get_real_speed(self, address):
        """
        读取单个泵实时转速（单次读取两个寄存器）

        Args:
            address (int): 泵地址

        Returns:
            float: 实时转速值
        """
        try:
            # 一次性读取两个寄存器
            result = self.client.read_holding_registers(
                address=self.HOLDING_REGISTERS['speed_real'],
                count=2,
                slave=address
            )
            if result.isError():
                raise ModbusException(result)

            # 合并为32位浮点数
            high_word = result.registers[0]
            low_word = result.registers[1]
            float_bytes = high_word.to_bytes(2, 'big') + low_word.to_bytes(2, 'big')
            return struct.unpack('!f', float_bytes)[0]
        except ModbusException as e:
            error_msg = f"读取泵（地址: {address}）的实时转速时发生错误: {e}"
            print(error_msg)
            raise ModbusException(error_msg)

    def control_pumps(self, control_type, value, addresses=None):
        """
        批量控制泵组

        Args:
            control_type (str): 控制类型，可选：
                'start_stop'（启停）, 'drain'（排空）,
                'direction'（方向）, 'speed'（转速）
            value: 控制值，bool类型或float类型（仅speed）
            addresses (list): 目标地址列表，None表示控制全部泵
        """
        targets = self.pump_addresses if addresses is None else addresses
        for addr in targets:
            if control_type == 'speed':
                self.set_speed(addr, value)
            else:
                self.control_single(addr, control_type, value)


# 使用示例
if __name__ == "__main__":
    # 初始化控制器（地址根据拨码开关计算）
    pump_group = PumpController(
        port='com1',
        pump_addresses=[0xC0, 0xC1]  # 示例地址
    )

    # 批量控制示例
    pump_group.control_pumps('start_stop', True)  # 启动所有泵
    pump_group.control_pumps('speed', 15.5, [0xC0])  # 设置地址0xC0的转速

    # 读取实时转速
    print(f"实时转速：{pump_group.get_real_speed(0xC0)} RPM")
