import struct

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


def decode_float(value):
    """
    将16位寄存器值转换为32位浮点数。
    Args:
        value (list): 包含两个16位寄存器值的列表。
    Returns:
        float: 转换后的浮点数。
    """
    return struct.unpack('>f', struct.pack('>I', (value[1] << 16) | value[0]))[0]


class SensorController:
    """
    SensorController类用于通过Modbus协议与多个传感器进行通信，读取传感器数据。
    Attributes:
        port (str): 串口设备名称。
        baudrate (int): 串口波特率。
        ph_address (int): pH传感器的Modbus设备地址。
        orp_address (int): ORP传感器的Modbus设备地址。
        conductivity_address (int): 电导率传感器的Modbus设备地址。
        level_address (int): 液位计传感器的Modbus设备地址。
        client (ModbusSerialClient): Modbus串口客户端实例。
    """

    def __init__(self, port='com4', client=None, baudrate=9600, bytesize=8, parity='N', stopbits=1, ph_address=2,
                 orp_address=3,
                 conductivity_address=1, level_address=4):
        """
        初始化SensorController类的实例。
        Args:
            port (str): 串口设备名称，如'COM4'。
            baudrate (int, optional): 串口波特率，默认为9600。
            bytesize (int, optional): 串口数据位，默认为8。
            parity (str, optional): 串口校验位，默认为'N'（无校验）。
            stopbits (int, optional): 串口停止位，默认为1。
            ph_address (int, optional): pH传感器的Modbus设备地址，默认为2。
            orp_address (int, optional): ORP传感器的Modbus设备地址，默认为3。
            conductivity_address (int, optional): 电导率传感器的Modbus设备地址，默认为1。
            level_address (int, optional): 液位计传感器的Modbus设备地址，默认为4。
        """
        self.port = port
        self.baudrate = baudrate
        self.ph_address = ph_address
        self.orp_address = orp_address
        self.conductivity_address = conductivity_address
        self.level_address = level_address
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

    def __del__(self):
        """
        析构函数，用于在对象销毁时关闭Modbus客户端连接。
        """
        self.client.close()

    def get_client(self):
        return self.client

    def read_ph(self):
        """
        读取pH传感器的值。
        Returns:
            float or None: pH值，如果读取失败返回None。
        """
        try:
            result = self.client.read_holding_registers(address=0x0001, count=2, slave=self.ph_address)
            if result.isError():
                raise ModbusException(result)
            return decode_float(result.registers)
        except ModbusException as e:
            error_msg = f"读取pH传感器（地址: {self.ph_address}）的值时发生错误: {e}"
            print(error_msg)
            raise ModbusException(error_msg)

    def read_orp(self):
        """
        读取ORP传感器的值。
        Returns:
            float or None: ORP值，如果读取失败返回None。
        """
        try:
            result = self.client.read_holding_registers(address=0x0001, count=2, slave=self.orp_address)
            if result.isError():
                raise ModbusException(result)
            return decode_float(result.registers)
        except ModbusException as e:
            error_msg = f"读取ORP传感器（地址: {self.orp_address}）的值时发生错误: {e}"
            print(error_msg)
            raise ModbusException(error_msg)

    def read_conductivity(self):
        """
        读取电导率传感器的值。
        Returns:
            float or None: 电导率值ms/cm，如果读取失败返回None。
        """
        try:
            result = self.client.read_holding_registers(address=0x0000, count=2, slave=self.conductivity_address)
            if result.isError():
                raise ModbusException(result)
            return decode_float(result.registers)
        except ModbusException as e:
            error_msg = f"读取电导率传感器（地址: {self.conductivity_address}）的值时发生错误: {e}"
            print(error_msg)
            raise ModbusException(error_msg)

    def read_temperature(self, sensor_type):
        """
        读取指定传感器的温度值。
        Args:
            sensor_type (str): 传感器类型，取值为'ph'、'orp'或'conductivity'。
        Returns:
            float or None: 温度值，如果读取失败返回None。
        """
        if sensor_type == 'ph':
            address = 0x0003
            slave = self.ph_address
        elif sensor_type == 'orp':
            address = 0x0003
            slave = self.orp_address
        elif sensor_type == 'conductivity':
            address = 0x0004
            slave = self.conductivity_address
        else:
            raise ValueError("无效的传感器类型")
        try:
            result = self.client.read_holding_registers(address=address, count=2, slave=slave)
            if result.isError():
                raise ModbusException(result)
            return decode_float(result.registers)
        except ModbusException as e:
            error_msg = f"读取{sensor_type}传感器（地址: {slave}）的温度值时发生错误: {e}"
            print(error_msg)
            raise ModbusException(error_msg)

    def read_level(self):
        """
        读取液位计传感器的值。mm
        Returns:
            int or None: 液位计测量值，如果读取失败返回None。
        """
        try:
            # result = self.client.read_input_registers(address=0x0002, count=1, slave=self.level_address)
            # if result.isError():
            #     raise ModbusException(result)
            # return 0.1 * int(result.registers[0])
            result = self.client.read_holding_registers(address=0x0200, count=1, slave=self.level_address)
            if result.isError():
                raise ModbusException(result)
            return int(result.registers[0])
        except ModbusException as e:
            error_msg = f"读取液位计传感器（地址: {self.level_address}）的值时发生错误: {e}"
            print(error_msg)
            raise ModbusException(error_msg)

    def read_all_sensors(self):
        """
        依次读取所有传感器的值及其温度，液位计无温度，并以JSON格式返回。
        Returns:
            dict: 字典，包含传感器的值及温度。
        """
        data = {
            'ph': {
                'value': self.read_ph(),
                'temperature': self.read_temperature('ph')
            },
            'orp': {
                'value': self.read_orp(),
                'temperature': self.read_temperature('orp')
            },
            'conductivity': {
                'value': self.read_conductivity(),
                'temperature': self.read_temperature('conductivity')
            },
            'level': {
                'value': self.read_level(),
            }
        }
        return data


if __name__ == '__main__':
    sensor_controller = SensorController('COM8')
    print(sensor_controller.read_level())
    # del sensor_controller
