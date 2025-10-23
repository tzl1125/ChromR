def get_path(filesize):
    import os
    # 存储符合条件的文件列表
    matched_files = []
    # 检查 upload_files 文件夹
    upload_dir = '/upload_files'

    # 确保文件夹存在
    if not os.path.exists(upload_dir):
        return {"file_path": "None"}

    # 递归遍历文件夹中的所有文件
    for root, dirs, files in os.walk(upload_dir):
        for filename in files:  # 只处理文件，忽略文件夹
            file_path = os.path.join(root, filename)

            # 获取文件状态信息
            file_stat = os.stat(file_path)

            # 获取文件修改时间
            file_mtime = file_stat.st_mtime

            # 检查文件大小和修改时间是否符合条件
            if file_stat.st_size == filesize:
                matched_files.append((file_path, file_mtime))

    if matched_files:
        # 按修改时间排序，取最新的文件
        newest_file = max(matched_files, key=lambda x: x[1])
        return str(newest_file[0])
    else:
        return "None"


def fp_growth(datas, min_support: int, min_conf: float, server_ip: str) -> dict:
    import requests
    url = f"http://{server_ip}:8000/fp-growth"
    if len(datas) == 0:
        return {"result": "没有上传数据文件"}
    data_size = datas[0]['size']
    data_name = datas[0]['filename']
    dataset = get_path(data_size)
    files = {'data_file': (data_name, open(dataset, 'rb'))}

    payload = {
        'min_support': min_support,
        'min_conf': min_conf
    }
    response = requests.post(url, data=payload, files=files)

    if response.status_code == 200:
        return {"result": f"分析文件：{data_name}\n响应结果：{response.json().get('result')}"}
    else:
        return {
            "result": f'error: 请求失败，状态码: {response.status_code}\ndetail:{response.text}'
        }


def design_space(datas, mt, p, r, server_ip, ds_type, no_risk=False):
    pc_size = 0
    er_size = 0
    yl_size = 0
    xl_size = 0
    mc_size = 0

    pc_file_name = ''
    er_file_name = ''
    yl_file_name = ''
    xl_file_name = ''
    mc_file_name = ''

    # 根据ds_type确定需要的文件列表
    if ds_type == "withM":
        file_names = ['expresults.xlsx', 'parametercondition.xlsx', "xlimitssteps.xlsx", 'ylimits.xlsx',
                      'materialcondition.xlsx']
    else:
        file_names = ['expresults.xlsx', 'parametercondition.xlsx', "xlimitssteps.xlsx", 'ylimits.xlsx']

    # 提取文件信息并验证
    for f in datas:
        lower_name = f['filename'].lower()
        if lower_name == 'expresults.xlsx':
            er_size = f['size']
            er_file_name = f['filename']
            file_names.remove('expresults.xlsx')
        elif lower_name == 'parametercondition.xlsx':
            pc_size = f['size']
            pc_file_name = f['filename']
            file_names.remove('parametercondition.xlsx')
        elif lower_name == 'xlimitssteps.xlsx':
            xl_size = f['size']
            xl_file_name = f['filename']
            file_names.remove('xlimitssteps.xlsx')
        elif lower_name == 'ylimits.xlsx':
            yl_size = f['size']
            yl_file_name = f['filename']
            file_names.remove('ylimits.xlsx')
        if ds_type == "withM" and lower_name == 'materialcondition.xlsx':
            mc_size = f['size']
            mc_file_name = f['filename']
            file_names.remove('materialcondition.xlsx')

    # 检查是否缺少文件
    if ds_type == "withM":
        all_files = pc_size and er_size and yl_size and xl_size and mc_size
    else:
        all_files = pc_size and er_size and yl_size and xl_size

    if not all_files:
        error = '、'.join(file_names)
        return {"result": f'文件名称不对或缺少，请上传{error}'}

    # 获取文件路径
    pc_file = get_path(pc_size)
    er_file = get_path(er_size)
    yl_file = get_path(yl_size)
    xl_file = get_path(xl_size)

    import requests
    # 根据是否为无概率计算构建不同URL
    if no_risk:
        url = f"http://{server_ip}:8000/design-space/noR/{ds_type}"
    else:
        url = f"http://{server_ip}:8000/design-space/{ds_type}"

    # 构建文件上传字典
    files = {
        'YLimits': (yl_file_name, open(yl_file, 'rb')),
        'ParameterCondition': (pc_file_name, open(pc_file, 'rb')),
        'ExpResults': (er_file_name, open(er_file, 'rb')),
        'XLimitsSteps': (xl_file_name, open(xl_file, 'rb'))
    }

    # 如果需要物料属性文件则添加
    if ds_type == "withM":
        mc_file = get_path(mc_size)
        files['MaterialCondition'] = (mc_file_name, open(mc_file, 'rb'))

    # 根据是否为无概率计算构建不同参数
    if no_risk:
        payload = {'p': p}
    else:
        payload = {
            'mt': mt,
            'r': r,
            'p': p,
        }

    # 发送请求
    response = requests.post(url, data=payload, files=files)

    # 处理响应
    if response.status_code == 200:
        return {"result": response.json().get('result')}
    else:
        return {
            "result": f'error: 请求失败，状态码: {response.status_code}\ndetail:{response.text}'
        }


def scopus(query: str) -> dict:
    import requests
    url = f"http://localhost:8000/scopus"
    payload = {'query': query}
    response = requests.post(url, data=payload)

    if response.status_code == 200:
        return {"result": response.json().get('result')}
    else:
        response.raise_for_status()


def arxiv(query: str) -> dict:
    import requests
    url = f"http://localhost:8000/arxiv"
    payload = {'query': query}
    response = requests.post(url, data=payload)

    if response.status_code == 200:
        return {"result": response.json().get('result')}
    else:
        response.raise_for_status()


def pubmed(query: str) -> dict:
    import requests
    url = f"http://localhost:8000/pubmed"
    payload = {'query': query}
    response = requests.post(url, data=payload)

    if response.status_code == 200:
        return {"result": response.json().get('result')}
    else:
        response.raise_for_status()


def stepwise_regression(datas, p_value, server_ip):
    import requests

    pc_size = 0
    er_size = 0
    mc_size = 0
    pc_file_name = ''
    er_file_name = ''
    mc_file_name = ''
    file_names = ['expresults.xlsx', 'parametercondition.xlsx','materialcondition.xlsx']
    for f in datas:
        if f['filename'].lower() == 'expresults.xlsx':
            er_size = f['size']
            er_file_name = f['filename']
            file_names.remove('expresults.xlsx')
        if f['filename'].lower() == 'parametercondition.xlsx':
            pc_size = f['size']
            pc_file_name = f['filename']
            file_names.remove('parametercondition.xlsx')
        if f['filename'].lower() == 'materialcondition.xlsx':
            mc_size = f['size']
            mc_file_name = f['filename']
            file_names.remove('materialcondition.xlsx')

    if not (pc_size and er_size):
        error = '、'.join(file_names)
        return {"result": f'文件名称不对或缺少，请上传{error}'}

    pc_file_path = get_path(pc_size)
    er_file_path = get_path(er_size)
    mc_file_path = get_path(mc_size) if mc_size else None

    api_url = f"http://{server_ip}:8000/stepwise-regress/"
    # 准备文件数据
    files = {
        'pc': (pc_file_name, open(pc_file_path, 'rb')),
        'er': (er_file_name, open(er_file_path, 'rb'))
    }

    # 如果有物料属性文件，添加到上传文件中
    if mc_size and mc_file_path:
        files['material'] = (mc_file_name, open(mc_file_path, 'rb'))

    data = {
        'p': p_value
    }

    response = requests.post(
        api_url,
        files=files,
        data=data
    )

    if response.status_code == 200:
        response_data = response.json()
        return {
            "result": response_data.get("result", "")
        }
    else:
        return {
            "result": f'error: 请求失败，状态码: {response.status_code}\ndetail:{response.text}'
        }


def optimize():
    import requests
    import inspect
    import textwrap

    # 定义具有明确全局最优解的目标函数
    def objective1(x, y):
        """二次函数1 - 最小化 (全局最小值在(2,3))"""
        return (x - 2) ** 2 + (y - 3) ** 2

    def objective2(x, y):
        """二次函数2 - 最大化 (全局最大值在(4,1))"""
        return -(x - 4) ** 2 - (y - 1) ** 2 + 50

    def constraint(x, y):
        """约束函数 (要求x+y >= 5)"""
        return x + y

    # 准备请求数据
    request_data = {
        "variables": {
            "x": {"lower": 0, "upper": 5},
            "y": {"lower": 0, "upper": 5}
        },
        "objective_functions": {
            "objective1": textwrap.dedent(inspect.getsource(objective1)),
            "objective2": textwrap.dedent(inspect.getsource(objective2)),
            "constraint": textwrap.dedent(inspect.getsource(constraint))
        },
        "objective_ranges": {
            "objective1": {"min_value": None, "max_value": None, "direction": "min"},
            "objective2": {"min_value": None, "max_value": None, "direction": "max"},
            "constraint": {"min_value": 5, "max_value": None, "direction": None}  # 纯约束条件
        },
        "algorithm": "nsga3",
        "population_size": 100,
        "generations": 50
    }

    # 发送请求
    response = requests.post(
        "http://localhost:8000/optimize/",
        json=request_data
    )
    if response.status_code == 200:
        response_data = response.json()
        return {
            "result": response_data.get("result", "")
        }
    else:
        return {
            'error': f"请求失败，状态码: {response.status_code}",
            'detail': response.text
        }


def test_design_space_api(
        base_url: str,
        ds_type,
        no_risk: bool = False,
        mt: int = 1000,
        p: float = 0.1,
        r: float = 0.1,
        y_limits_path: str = "",
        parameter_condition_path: str = "",
        exp_results_path: str = "",
        x_limits_steps_path: str = "",
        material_condition_path= None
) -> dict:
    """
    测试设计空间API的客户端函数

    参数:
        base_url: API基础地址（如"http://localhost:8000"）
        ds_type: 设计空间类型，可选值：includeN, withM, withoutM
        no_risk: 是否调用无风险计算接口（/noR/{ds_type}）
        mt: 蒙特卡洛模拟次数（仅非no_risk模式有效）
        p: 逐步回归p值
        r: 可接受的风险（仅非no_risk模式有效）
        y_limits_path: Y轴范围限制文件路径（xlsx）
        parameter_condition_path: 参数条件文件路径（xlsx）
        exp_results_path: 实验结果文件路径（xlsx）
        x_limits_steps_path: 变量范围和步长文件路径（xlsx）
        material_condition_path: 物料属性文件路径（xlsx，仅ds_type为withM时需要）

    返回:
        API响应的JSON数据
    """
    import os
    import requests
    # 构建请求URL
    if no_risk:
        url = f"{base_url}/design-space/noR/{ds_type}"
    else:
        url = f"{base_url}/design-space/{ds_type}"

    # 验证必要文件是否存在
    required_files = [
        y_limits_path,
        parameter_condition_path,
        exp_results_path,
        x_limits_steps_path
    ]
    for file_path in required_files:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"必要文件不存在: {file_path}")

    # 验证物料属性文件（当需要时）
    if ds_type == "withM" and not material_condition_path:
        raise ValueError("ds_type为withM时必须提供material_condition_path")
    if ds_type == "withM" and not os.path.exists(material_condition_path):
        raise FileNotFoundError(f"物料属性文件不存在: {material_condition_path}")

    # 准备表单数据
    form_data = {"p": p}
    if not no_risk:
        form_data.update({"mt": mt, "r": r})

    # 准备文件数据
    files = {
        "YLimits": open(y_limits_path, "rb"),
        "ParameterCondition": open(parameter_condition_path, "rb"),
        "ExpResults": open(exp_results_path, "rb"),
        "XLimitsSteps": open(x_limits_steps_path, "rb")
    }

    # 添加物料属性文件（如果需要）
    if ds_type == "withM" and material_condition_path:
        files["MaterialCondition"] = open(material_condition_path, "rb")

    try:
        # 发送POST请求
        response = requests.post(
            url,
            data=form_data,
            files=files,
            timeout=30  # 30秒超时
        )
        response.raise_for_status()  # 抛出HTTP错误状态码
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "status_code": response.status_code if 'response' in locals() else None}
    finally:
        # 关闭所有文件
        for file in files.values():
            file.close()


if __name__ == '__main__':
    # fp_growth 关联规则挖掘测试
    # print(fp_growth('./groceries.csv', 25, 0.7))

    # 设计空间测试
    ds_type = "withM"  # 可选值: includeN, withM, withoutM
    BASE_URL = "http://localhost:8000"
    TEST_FILES_DIR = f"./design space dataset/{ds_type}"  # 替换为实际测试文件目录

    # result1 = test_design_space_api(
    #     base_url=BASE_URL,
    #     ds_type=ds_type,
    #     no_risk=True,
    #     mt=200,
    #     p=0.1,
    #     r=0.1,
    #     y_limits_path=f"{TEST_FILES_DIR}/YLimits.xlsx",
    #     parameter_condition_path=f"{TEST_FILES_DIR}/ParameterCondition.xlsx",
    #     exp_results_path=f"{TEST_FILES_DIR}/ExpResults.xlsx",
    #     x_limits_steps_path=f"{TEST_FILES_DIR}/XLimitsSteps.xlsx"
    # )
    # print(result1)

    # 测试无风险计算的接口
    result2 = test_design_space_api(
        base_url=BASE_URL,
        ds_type=ds_type,
        no_risk=True,
        p=0.1,
        y_limits_path=f"{TEST_FILES_DIR}/YLimits.xlsx",
        parameter_condition_path=f"{TEST_FILES_DIR}/ParameterCondition.xlsx",
        exp_results_path=f"{TEST_FILES_DIR}/ExpResults.xlsx",
        x_limits_steps_path=f"{TEST_FILES_DIR}/ZXLimitsSteps.xlsx",
        material_condition_path=f"{TEST_FILES_DIR}/MaterialCondition.xlsx"
    )
    print(result2)


    # # scopus测试
    # print(scopus("TITLE ( optimization of chromatography )  AND PUBYEAR > 2025"))
    #
    # # arxiv测试
    # print(arxiv('ti:\"large language model*\" AND cat:q-bio.GN AND submittedDate:[202301010000 TO 202506302359]'))
    #
    # # pubmed测试
    # print(pubmed("\"type 2 diabetes\" AND (drug therapy OR pharmacotherapy)"
    #              " AND \"clinical trial\"[pt] AND \"JAMA\"[ta] AND 2018:2023[dp]"))
    # print(optimize())
