import ast
import os
import types
from typing import List

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.core.problem import Problem
from pymoo.optimize import minimize
from pymoo.util.ref_dirs import get_reference_directions


def safe_eval_function(function_code: str, function_name: str, expected_params: List[str]):
    try:
        tree = ast.parse(function_code)
        if not all(isinstance(node, ast.FunctionDef) for node in tree.body):
            raise ValueError("只允许函数定义")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                raise ValueError("不允许导入模块")
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == '__builtins__':
                raise ValueError("不允许访问内置模块")
        function_def = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                function_def = node
                break
        if function_def is None:
            raise ValueError(f"未找到函数: {function_name}")
        actual_params = [arg.arg for arg in function_def.args.args]
        if sorted(actual_params) != sorted(expected_params):
            missing = [p for p in expected_params if p not in actual_params]
            unexpected = [p for p in actual_params if p not in expected_params]
            error_msg = []
            if missing:
                error_msg.append(f"缺少参数: {', '.join(missing)}")
            if unexpected:
                error_msg.append(f"意外参数: {', '.join(unexpected)}")
            raise ValueError(f"参数名不匹配。{'; '.join(error_msg)}")
        safe_globals = {
            '__builtins__': {
                'range': range,
                'float': float,
                'int': int,
                'abs': abs,
                'max': max,
                'min': min,
                'sum': sum
            },
            'math': __import__('math'),
            'np': np
        }
        exec(compile(tree, filename="<ast>", mode="exec"), safe_globals)
        function = safe_globals[function_name]
        if not isinstance(function, types.FunctionType):
            raise ValueError(f"{function_name} 不是函数")
        return function
    except Exception as e:
        raise ValueError(f"函数解析错误: {str(e)}")


class CustomMOOProblem(Problem):
    def __init__(
            self,
            variable_names: List[str],
            variable_bounds: np.ndarray,
            objective_functions: List[callable],
            objective_ranges: List[dict]
    ):
        n_constr = sum(1 for obj_range in objective_ranges
                       if obj_range.get('min_value') is not None or obj_range.get('max_value') is not None)
        self.variable_names = variable_names
        self.objective_functions = objective_functions
        self.objective_ranges = objective_ranges
        self.n_actual_obj = sum(1 for obj in objective_ranges if obj.get('direction') is not None)
        super().__init__(
            n_var=len(variable_names),
            n_obj=max(1, self.n_actual_obj),
            n_constr=n_constr,
            xl=variable_bounds[:, 0],
            xu=variable_bounds[:, 1]
        )

    def _evaluate(self, X, out, *args, **kwargs):
        F = np.zeros((X.shape[0], self.n_obj))
        G = np.zeros((X.shape[0], self.n_constr))
        for i, x in enumerate(X):
            params = {name: x[j] for j, name in enumerate(self.variable_names)}
            constr_idx = 0
            actual_obj_idx = 0
            for j, func in enumerate(self.objective_functions):
                value = func(**params)
                if self.objective_ranges[j].get('min_value') is not None:
                    G[i, constr_idx] = self.objective_ranges[j].get('min_value') - value
                    constr_idx += 1
                if self.objective_ranges[j].get('max_value') is not None:
                    G[i, constr_idx] = value - self.objective_ranges[j].get('max_value')
                    constr_idx += 1
                if self.objective_ranges[j].get('direction') is not None:
                    if self.objective_ranges[j].get('direction') == "max":
                        F[i, actual_obj_idx] = -value
                    else:
                        F[i, actual_obj_idx] = value
                    actual_obj_idx += 1
        out["F"] = F
        out["G"] = G


def calculation(request: dict, current_dir: str, task_id: str):
    # 提取变量名称和边界
    variable_names = list(request['variables'].keys())
    variable_bounds = np.array([
        [var['lower'], var['upper']] for var in request['variables'].values()
    ])

    population_size = request['population_size']

    # 提取目标范围
    objective_ranges = list(request['objective_ranges'].values())

    # 构建目标函数列表
    objective_functions = [
        safe_eval_function(
            func_code,
            func_name,
            expected_params=variable_names
        )
        for func_name, func_code in request['objective_functions'].items()
    ]

    # from dask.distributed import Client
    # client = Client()
    # client.restart()
    # print("DASK STARTED")
    # runner = DaskParallelization(client)

    # 创建优化问题实例
    problem = CustomMOOProblem(
        variable_names=variable_names,
        variable_bounds=variable_bounds,
        objective_functions=objective_functions,
        objective_ranges=objective_ranges,
    )
    # problem.elementwise_runner = runner

    # 根据请求选择优化算法
    n_actual_obj = problem.n_actual_obj
    algorithm = None
    if request['algorithm'] == "nsga2":
        algorithm = NSGA2(pop_size=population_size)
    elif request['algorithm'] == "nsga3":
        if n_actual_obj > 0:
            ref_dirs = get_reference_directions("das-dennis", n_actual_obj, n_partitions=12)
            algorithm = NSGA3(pop_size=population_size, ref_dirs=ref_dirs)
        else:
            raise ValueError("NSGA3需要至少一个优化目标")

    # 执行优化
    res = minimize(
        problem,
        algorithm,
        ('n_gen', request['generations']),
        seed=1,
        verbose=False
    )

    # client.close()
    # print("DASK SHUTDOWN")
    # 处理优化结果
    if res.F is None:
        raise ValueError("优化未找到可行解")

    optimal_solutions = []
    for idx in range(min(5, len(res.X))):
        x = res.X[idx]
        solution = {
            "optimal_variables": {
                name: float(x[i])
                for i, name in enumerate(variable_names)
            },
            "optimal_objectives": {}
        }
        # 计算所有目标原始值
        params = solution["optimal_variables"]
        for name, func in zip(request['objective_functions'].keys(), objective_functions):
            solution["optimal_objectives"][name] = float(func(**params))
        optimal_solutions.append(solution)

    # 保存结果到文件
    file_name = f"multi-opt/{task_id}.txt"
    save_path = f"{current_dir}/data_files/{file_name}"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "w") as f:
        import json
        f.write(json.dumps(optimal_solutions, indent=4))

    return file_name


if __name__ == "__main__":
    import json
    import os

    # 更新后的请求数据（使用新的生产率计算公式）
    request_str = '''{
        "variables": {
            "sample_time": {"lower": 1.00, "upper": 2.00},
            "sample_flow": {"lower": 0.5, "upper": 1.5},
            "washing_time": {"lower": 0.50, "upper": 1.50},
            "washing_flow": {"lower": 1.5, "upper": 2.5},
            "elution_time": {"lower": 0.50, "upper": 1.50},
            "elution_flow": {"lower": 2.5, "upper": 3.5}
        },
        "objective_functions": {
            "lactone_purity": "def lactone_purity(sample_time, sample_flow, washing_time, washing_flow, elution_time, elution_flow):\\n    return 3.1167 - 10.7425 * 0.5835 + 0.7026 * sample_flow + 3.9301 * washing_time + 1.8364 * washing_flow",
            "flavonol_glycoside_purity": "def flavonol_glycoside_purity(sample_time, sample_flow, washing_time, washing_flow, elution_time, elution_flow):\\n    return 0.4002 - 50.0259 * 0.5835 + 18.7848 * washing_time + 9.5709 * washing_flow + 3.8743 * elution_time + 2.9674 * elution_flow",
            "lactone_productivity": "def lactone_productivity(sample_time, sample_flow, washing_time, washing_flow, elution_time, elution_flow):\\n    return 32.8842 + 17.5758 * (sample_flow * elution_flow) - 2.3691 * sample_time - 23.4526 * sample_flow - 8.2481 * elution_flow - 5.7581 * washing_time - 9.4687 * (sample_flow * washing_time) + 20.6692 * (sample_time * sample_flow)",
            "flavonol_glycoside_productivity": "def flavonol_glycoside_productivity(sample_time, sample_flow, washing_time, washing_flow, elution_time, elution_flow):\\n    return 47.4225 + 49.6461 * (sample_flow * elution_flow) + 13.6240 * sample_time - 18.6213 * sample_flow - 10.5198 * elution_flow - 22.3586 * washing_time - 26.3807 * (sample_flow * washing_time) + 58.9702 * (sample_time * sample_flow)"
        },
        "objective_ranges": {
            "lactone_purity": {"min_value": 6, "max_value": null, "direction": "max"},
            "flavonol_glycoside_purity": {"min_value": 24, "max_value": null, "direction": "max"},
            "lactone_productivity": {"min_value": null, "max_value": null, "direction": "max"},
            "flavonol_glycoside_productivity": {"min_value": null, "max_value": null, "direction": "max"}
        },
        "algorithm": "nsga3",
        "population_size": 2000,
        "generations": 100
    }'''

    try:
        # 解析请求数据
        request = json.loads(request_str)

        # 设置当前目录为脚本所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 测试用任务ID
        task_id = "debug_test_001"

        # 执行计算
        result_file = calculation(request, current_dir, task_id)
        print(f"优化完成，结果已保存至：{os.path.join(current_dir, 'data_files', result_file)}")

        # 读取并打印结果（可选）
        with open(os.path.join(current_dir, 'data_files', result_file), 'r') as f:
            results = json.load(f)
        print("前5个优化解：")
        for i, sol in enumerate(results[:5], 1):  # 只显示前5个解
            print(f"\n解 {i}:")
            print("最优变量：", sol["optimal_variables"])
            print("目标函数值：", sol["optimal_objectives"])
    except json.JSONDecodeError as e:
        print(f"JSON解析错误：{str(e)}")
        print(f"错误位置：行 {e.lineno}, 列 {e.colno}")
    except Exception as e:
        print(f"调试过程中发生错误：{str(e)}")

