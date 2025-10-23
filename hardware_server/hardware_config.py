class HardwareConfig:
    feed = {'pump': 7, 'valve': 3}
    wash = {'pump': 7, 'valve': 1}
    elute = {'pump': 7, 'valve': 2}
    refresh = {'pump': 7, 'valve': 4}
    equilibrate = {'pump': 7, 'valve': 5}

    out = {'pump': 10, 'waste': 8, 'F1': 9, 'F2': 10, 'F3': 11}

    pump_factor = {'7': 8.25, '10': 8}  # 泵的校正因子,转速（rpm）=校正因子*流量（ml/min）
