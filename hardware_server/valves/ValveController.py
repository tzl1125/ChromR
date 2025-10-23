from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


class ValveController:
    """
    4-20mA模拟量，Modbus阀门控制器，支持多阀门管理

    Attributes:
        client (ModbusSerialClient): Modbus RTU客户端
        valve_channels (list): 管理的阀门通道列表
        valve_states (dict): 阀门状态记录（开度等）
    """
    # 寄存器地址映射（根据模拟量输出系列使用手册(RS485版)定义）
    HOLDING_REGISTERS = {
        'valve_setting': {
            1: 0x000A,  # 第1路阀门寄存器地址
            2: 0x000B,
            3: 0x000C,
            4: 0x000D,
            5: 0x000E,
            6: 0x000F,
            7: 0x0010,
            8: 0x0011,
            9: 0x0012,
            10: 0x0013,
            11: 0x0014,
            12: 0x0015
        }
    }

    def __init__(self, valve_channels, port='com5', client=None, slave_address=1, baudrate=9600, bytesize=8, parity='N',
                 stopbits=1):
        """
        初始化阀门控制器

        Args:
            port (str): 串口路径（如'com5'）
            valve_channels (list): 管理的阀门通道列表（取值范围1 - 12）
            slave_address (int): 485转模拟量设备地址，默认为1
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
        self.slave_address = slave_address
        self.valve_channels = valve_channels
        # 初始化状态记录
        self.valve_states = {}
        for channel in valve_channels:
            self.valve_states[channel] = {'opening': 0.0, 'name': '无'}
            # 初始化所有阀门为关闭状态
            self.set_valve_opening(channel, 0.0)

    def __del__(self):
        """
        析构函数，用于在对象销毁时关闭Modbus客户端连接。
        """
        self.client.close()

    def get_client(self):
        return self.client

    def get_valve_states(self):
        return self.valve_states

    def set_valve_name(self, valve_name, channel=None):
        if channel is None:
            channel = self.valve_channels
        for c in channel:
            self.valve_states[c].update({'name': valve_name})

    def set_valve_opening(self, valve_channel, opening):
        """
        设置单个阀门的开度

        Args:
            valve_channel (int): 阀门通道（1 - 12）
            opening (float): 阀门开度，取值范围0 - 100
        """
        if opening < 0 or opening > 100:
            raise ValueError("开度值必须在0到100之间")
        if valve_channel not in self.valve_channels:
            raise ValueError(f"{valve_channel}路没有阀门被注册")
        try:
            # 将开度值转换为4-20mA电流值
            current = 4 + (opening / 100) * (20 - 4)
            # 根据协议，将电流值转换为寄存器值（固定三位小数）
            register_value = int(current * 1000)
            # 写入对应通道的保持寄存器
            result = self.client.write_register(
                address=self.HOLDING_REGISTERS['valve_setting'][valve_channel],
                value=register_value,
                slave=self.slave_address
            )
            if result.isError():
                raise ModbusException(result)
            # 更新状态记录
            self.valve_states[valve_channel]['opening'] = opening
        except ModbusException as e:
            error_msg = f"写入阀门 {valve_channel} 开度时发生错误: {e}"
            print(error_msg)
            raise ModbusException(error_msg)

    def set_multiple_valve_opening(self, opening, channels=None):
        """
        控制多个阀门的开度

        Args:
            opening (float): 阀门开度，取值范围0 - 100
            channels (List[int]): 需要控制的阀门通道列表，默认值为None，即所有阀门
        """
        target = channels if channels is not None else self.valve_channels
        for channel in target:
            self.set_valve_opening(channel, opening)


# 使用示例
if __name__ == "__main__":
    # 初始化控制器（地址根据拨码开关计算）
    valve_group = ValveController(
        port='com1',
        valve_channels=[1, 2]  # 示例地址，假设控制第1和第2个阀门
    )
    # 设置单个阀门开度示例
    valve_group.set_valve_opening(1, 50.0)
    # 同时设置多个阀门开度示例
    valve_group.set_multiple_valve_opening(75.0)