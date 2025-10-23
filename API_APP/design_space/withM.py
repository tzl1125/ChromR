import itertools
import os
import shutil
from collections import Counter
from time import time

import numpy as np
import plotly.graph_objects as go
import statsmodels.api as sm
from joblib import Parallel, delayed
from pandas import read_excel, DataFrame
from psutil import virtual_memory
from scipy.sparse import csr_matrix
from toad.selection import stepwise


def Create_terms(material_raw, X, NEP, NPP):
    '''
    生成包含常数项以及各个变量一次项、二次项、交叉项的向量
    input：物料属性和其他变量的向量，不包含常数项；实验数NEP，因子数NPP（不包括物料）
    return：向量，包含常数项以及各个变量一次项、二次项、交叉项的向量，常数项在最前面
    '''
    # 生成交叉项
    interaction = np.zeros((NEP, 0))
    for i in range(NPP - 1):
        for j in range(i + 1, NPP):
            interaction_mid = np.multiply(X[:, i], X[:, j])
            interaction = np.column_stack([interaction, interaction_mid])
    # 生成平方项
    nonlinear = np.square(X)
    # 构建 X 矩阵
    X_terms_withconst = np.hstack([np.ones((NEP, 1)), material_raw, X, interaction, nonlinear])
    return X_terms_withconst.astype(np.float64)


def Get_rsd(material_raw, std_pp, NEP, exp_results):
    '''
    根据数据返回重复点的RSD
    input：material_raw:物料属性
        std_pp：各个因子的值
        NEP：实验数
        exp_results：实验结果
    output：rsd：重复点的相对标准偏差
    '''
    # 统计每行出现的次数
    row_counter = Counter(tuple(row) for row in std_pp.tolist())

    # 找出重复次数最多的行
    most_common_rows = np.array([list(row) for row, count in row_counter.items() if count == max(row_counter.values())])
    most_common_rows_indices = np.where((std_pp == most_common_rows).all(axis=1))[0]

    rep_results = exp_results[most_common_rows_indices, :]  # 重复试验结果
    rep_mean = np.mean(rep_results, axis=0)
    rep_std = np.std(rep_results, axis=0, ddof=1)  # 标准偏差
    rep_rsd = rep_std / rep_mean

    return rep_rsd


def Para_forfit(i, RandY, frame, pval_stepwise, num_variables, NPP, NPM=0):
    # 并行拟合系数
    row_vector = np.zeros(num_variables)
    frame['y'] = RandY.flatten()  # 因变量
    selected = stepwise(frame, target='y', p_enter=pval_stepwise, p_value_enter=pval_stepwise)

    selected_features = [col for col in selected if col != 'y']
    if 0 not in selected_features:
        selected_features.append(0)  # 确保常数项保留

    # 计算特征分区索引（根据Create_terms的结构）
    const_col = 1  # 常数项占1列（索引0）
    linear_start = 1 + NPM  # 一次项起始索引（跳过常数项和物料属性）
    linear_end = linear_start + NPP  # 一次项结束索引
    interaction_start = linear_end  # 交叉项起始索引
    interaction_count = (NPP * (NPP - 1)) // 2  # 交叉项总数
    interaction_end = interaction_start + interaction_count  # 交叉项结束索引

    # 检查交叉项并添加依赖的一次项
    required_features = set(selected_features)
    for feat in selected_features:
        if interaction_start <= feat < interaction_end:
            # 计算交叉项对应的原始变量索引
            k = feat - interaction_start  # 交叉项在交互项中的偏移量
            i, j = -1, -1
            count = 0
            # 解析交叉项对应的i和j（i < j）
            for a in range(NPP - 1):
                for b in range(a + 1, NPP):
                    if count == k:
                        i, j = a, b
                        break
                    count += 1
                if i != -1:
                    break
            # 添加对应的一次项
            required_features.add(linear_start + i)
            required_features.add(linear_start + j)

    # 更新选中的特征列表
    selected_features = list(required_features)
    X_selected = frame.iloc[:, selected_features]

    model = sm.OLS(RandY, X_selected)
    result = model.fit()
    B = result.params
    for index, value in B.items():
        row_vector[index] = value

    return row_vector


def GET_modlecof(X, NEP, NPI, MCPT,NPP, NPM, rep_rsd, exp_results, pval_stepwise):
    '''
    基于蒙特卡罗，根据RSD值生成随机的Y
    使用numpy.random.normal生成正态分布的随机数
    基于随机的y拟合模型获得X的系数矩阵,为稀疏矩阵csr_matrix形式
    '''
    # 根据蒙特卡罗次数，生成随机Y
    simu_results = np.empty((NEP, MCPT * NPI))

    for i in range(NPI):
        # 先生成均值为1的正态分布，Z=X/u
        std_ind_mat_mid = np.random.normal(1, rep_rsd[i], size=(NEP, MCPT))
        simu_results[:, MCPT * i:MCPT * (i + 1)] = exp_results[:, i].reshape(-1, 1) * std_ind_mat_mid

    # 基于随机的y拟合模型获得X的系数矩阵
    # 将X转换为DataFrame,获得回归系数
    frame = DataFrame(X)
    num_variables = len(frame.columns)
    RegrCoefMat = Parallel(n_jobs=-1, backend='loky')(delayed(Para_forfit)
                                                      (i, simu_results[:, i], frame, pval_stepwise, num_variables, NPP, NPM)
                                                      for i in range(NPI * MCPT))
    # from functools import partial
    # with Pool(processes=1) as pool:
    #     func = partial(parallel_function, simu_results=simu_results, frame=frame, pval_stepwise=pval_stepwise,
    #                    num_variables=num_variables)
    #     RegrCoefMat = pool.map(func, range(NPI * MCPT))

    return csr_matrix(np.array(RegrCoefMat))


def Cal_risks(combinations, RegrCoefMat, MCPT, NPI, NPM, NPP,
              lower_range, upper_range, different_pp, X_term_original):
    # combinations每一行一个坐标
    # 点数
    num = combinations.shape[0]
    # 创建一个空数组，用于存储 Meet_limit
    Meet_limit = np.ones((num, MCPT), dtype=bool)

    # 复制行
    X_term = np.tile(X_term_original, (num, 1))
    # 获得各点处的项
    X_term[:, different_pp] = combinations
    X_terms_withconst = Create_terms(X_term[:, :NPM], X_term[:, NPM:], num, NPP)

    # 获取系统可用内存大小（以字节为单位）
    available_memory = virtual_memory().available * 0.2  # 占用可用内存的20%
    chunk_size = min(num, int(available_memory // (MCPT * 8)))
    # 分区计算
    # 按块处理数据
    for chunk_start in range(0, num, chunk_size):
        chunk_end = min(chunk_start + chunk_size, num)
        # 遍历 NPI，逐步计算 Meet_limit
        for i in range(NPI):
            # 计算预测值
            ypredict = X_terms_withconst[chunk_start: chunk_end, :] @ RegrCoefMat[i * MCPT:(i + 1) * MCPT, :].T

            # 更新 Meet_limit
            Meet_limit[chunk_start:chunk_end] &= ((ypredict >= lower_range[i]) & (ypredict <= upper_range[i]))
            # 计算所有点的达标概率
    probs = np.sum(Meet_limit, axis=1) / MCPT
    risks = 1 - probs

    # 返回计算结果
    return risks


def Display_results(acceptable_risk, para_for_figure, result_matrix):
    # 提取符合条件的数据
    if para_for_figure == 3:
        data = [(x, y, z, risk) for x, y, z, risk in result_matrix if risk <= acceptable_risk]
        if len(data) == 0:
            raise RuntimeError("没有在可接受风险范围内的操作点")
        x, y, z, Risks = zip(*data)
        # 创建 3D 散点图
        fig = go.Figure(data=[go.Scatter3d(
            x=x, y=y, z=z,
            mode='markers',
            marker=dict(
                color=Risks,
                colorscale='jet',
                size=20,
                opacity=0.7
            )
        )])
        # 设置坐标轴标签
        fig.update_layout(scene=dict(
            xaxis_title='X',
            yaxis_title='Y',
            zaxis_title='Z'
        ))
    elif para_for_figure == 2:
        data = [(x, y, risk) for x, y, risk in result_matrix if risk <= acceptable_risk]
        if len(data) == 0:
            raise RuntimeError("没有在可接受风险范围内的操作点")
        x, y, Risks = zip(*data)
        # 创建 2D 散点图
        fig = go.Figure(data=[go.Scatter(
            x=x, y=y,
            mode='markers',
            marker=dict(
                color=Risks,
                colorscale='jet',
                size=20,
                opacity=0.7
            )
        )])
        # 设置坐标轴标签
        fig.update_layout(
            xaxis_title='X',
            yaxis_title='Y'
        )
    else:
        raise ValueError("不支持的维度。目前仅支持 2D 和 3D 数据。")

    # 添加颜色条
    fig.update_traces(marker=dict(colorbar=dict(title='Risk')))
    return fig


def main(YLimits, ParameterCondition, MaterialCondition, ExpResults, XLimitsSteps, mt, r, p, current_dir, task_id):
    print("withM设计空间开始计算")
    # 主函数
    # 设定优化目标
    limit_raw = read_excel(YLimits).values[:, 1:]
    lower_range = limit_raw[0, :]
    upper_range = limit_raw[1, :]
    NPI = limit_raw.shape[1]  # 评价指标个数

    # 读入实验中的工艺条件，不进行标准化
    std_pp = read_excel(ParameterCondition).values
    NEP, NPP = std_pp.shape  # 实验次数，因子个数

    # 读入实验中的原料性质
    material_raw = read_excel(MaterialCondition).values
    _, NPM = material_raw.shape  # 实验次数，原料性质个数

    # 创建包含 X 一次项、交叉项和平方项,常数项的向量，用于拟合获得偏回归系数
    X = Create_terms(material_raw, std_pp, NEP, NPP)

    # 读入实验结果
    exp_results = read_excel(ExpResults).values

    # 数据检验
    if exp_results.shape[0] != NEP:
        raise ValueError('实验个数和结果个数对不上')

    if exp_results.shape[1] != NPI:
        raise ValueError('指标和优化目标个数对不上')

    rep_rsd = Get_rsd(material_raw, std_pp, NEP, exp_results)

    # 蒙特卡罗部分，根据RSD值生成随机的Y
    # 读取Excel文件
    MCPT = int(mt)  # 读取A2单元格
    pval_stepwise = p  # 读取A3单元格
    acceptable_risk = r  # 读取A4单元格

    t1 = time()
    RegrCoefMat = GET_modlecof(X, NEP, NPI, MCPT,NPP, NPM, rep_rsd, exp_results, pval_stepwise)
    t2 = time()
    print(f'拟合系数用时{t2 - t1:.2f}s')
    # 读取X的范围和步长
    ZXLimits_steps = read_excel(XLimitsSteps).values[:, 1:]

    # 判断参数数量是否对应
    if ZXLimits_steps.shape[1] != NPP + NPM:
        raise ValueError('两次输入的变量总个数对不上')

    # 判断哪些参数需要画图
    x_limit_mid_mat = ZXLimits_steps[0, :] - ZXLimits_steps[1, :]
    different_pp = np.where(x_limit_mid_mat != 0)[0]
    para_for_figure = len(different_pp)
    if para_for_figure == 2:
        acceptable_risk = 1

    # 非标准化的上下限和步长
    XLowerRange = ZXLimits_steps[0, :]  # 未标准化后的X下限
    XUpperRange = ZXLimits_steps[1, :]  # 未标准化后的X上限
    XStdStep = ZXLimits_steps[2, :].astype(int)  # 未标准化后的步数

    # 生成X变量空间
    X_space = []
    for i in different_pp:
        XRange = np.linspace(XLowerRange[i], XUpperRange[i], XStdStep[i])
        X_space.append(XRange)

    # 计算预测结果
    # 获取所有点
    combinations = np.array(list(itertools.product(*X_space)))

    t3 = time()
    # 计算所有点的达标风险
    Risks = Cal_risks(combinations, RegrCoefMat, MCPT, NPI, NPM, NPP, lower_range,
                      upper_range, different_pp, ZXLimits_steps[0, :])
    t4 = time()
    print(f'计算风险用时{t4 - t3:.2f}s')
    # 展示结果
    result_matrix = np.concatenate((combinations, Risks.reshape(-1, 1)), axis=1)
    result_df = DataFrame(result_matrix, columns=[f'Parameter_{i}' for i in range(1, para_for_figure + 1)] + ['Risk'])

    file_dir = f"design-space/{task_id}"
    result_dir = f"{current_dir}/data_files/{file_dir}"
    os.makedirs(result_dir, exist_ok=True)
    if para_for_figure <= 3:
        figure = Display_results(acceptable_risk, para_for_figure, result_matrix)
        figure.write_html(f"{result_dir}/result_plot.html")
    result_df.to_excel(f"{result_dir}/result.xlsx", index=False)  # 将结果保存为 Excel 文件

    # 压缩文件夹
    shutil.make_archive(result_dir, 'zip', result_dir)
    # 删除原文件夹
    if os.path.exists(result_dir):
        shutil.rmtree(result_dir)

    return file_dir + ".zip"
