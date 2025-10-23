import itertools
import os
import shutil
from time import time

import numpy as np
import plotly.graph_objects as go
import statsmodels.api as sm
from pandas import read_excel, DataFrame
from toad.selection import stepwise


def Create_terms(X, NEP, NPP):
    interaction = np.zeros((NEP, 0))
    for i in range(NPP - 1):
        for j in range(i + 1, NPP):
            interaction_mid = np.multiply(X[:, i], X[:, j])
            interaction = np.column_stack([interaction, interaction_mid])
    nonlinear = np.square(X)
    X_terms_withconst = np.hstack([np.ones((NEP, 1)), X, interaction, nonlinear])
    return X_terms_withconst.astype(np.float64)


def fit_model(X, exp_results, pval_stepwise, NPP):
    frame = DataFrame(X)
    frame['y'] = exp_results.flatten()
    selected = stepwise(frame, target='y', p_enter=pval_stepwise, p_value_enter=pval_stepwise)

    selected_features = [col for col in selected if col != 'y']
    if 0 not in selected_features:
        selected_features.append(0)

    # 计算特征分区索引
    linear_start = 1  # 一次项起始索引（跳过常数项）
    linear_end = linear_start + NPP
    interaction_start = linear_end
    interaction_count = (NPP * (NPP - 1)) // 2
    interaction_end = interaction_start + interaction_count

    # 检查交叉项依赖
    required_features = set(selected_features)
    for feat in selected_features:
        if interaction_start <= feat < interaction_end:
            k = feat - interaction_start
            i, j = -1, -1
            count = 0
            for a in range(NPP - 1):
                for b in range(a + 1, NPP):
                    if count == k:
                        i, j = a, b
                        break
                    count += 1
                if i != -1:
                    break
            required_features.add(linear_start + i)
            required_features.add(linear_start + j)

    selected_features = list(required_features)
    X_selected = frame.iloc[:, selected_features]

    model = sm.OLS(exp_results, X_selected)
    result = model.fit()
    return result, selected_features


def Cal_compliance(combinations, models, selected_features_list, NPI, NPP,
                   lower_range, upper_range, different_pp, X_term_original):
    '''判断每个参数组合是否达标（所有指标满足范围）'''
    num = combinations.shape[0]
    compliance = np.ones(num, dtype=bool)  # 初始假设都达标

    # 生成所有组合的项矩阵
    X_term = np.tile(X_term_original, (num, 1))
    X_term[:, different_pp] = combinations
    X_terms_withconst = Create_terms(X_term, num, NPP)

    for i in range(NPI):
        # 用第i个指标的模型预测
        model, selected_feats = models[i], selected_features_list[i]
        X_selected = X_terms_withconst[:, selected_feats]
        ypredict = model.predict(X_selected)
        # 判断是否在范围内
        chunk_compliance = (ypredict >= lower_range[i]) & (ypredict <= upper_range[i])
        compliance &= chunk_compliance

    return compliance


def Display_results(result_matrix, columns):
    para_for_figure = result_matrix.shape[1] - 1
    compliant = result_matrix[:, -1].astype(bool)

    if para_for_figure == 3:
        x = result_matrix[:, 0]
        y = result_matrix[:, 1]
        z = result_matrix[:, 2]

        fig = go.Figure()
        fig.add_trace(go.Scatter3d(
            x=x[compliant], y=y[compliant], z=z[compliant],
            mode='markers',
            marker=dict(color='green', size=10, opacity=0.7),
            name='达标'
        ))
        fig.add_trace(go.Scatter3d(
            x=x[~compliant], y=y[~compliant], z=z[~compliant],
            mode='markers',
            marker=dict(color='red', size=10, opacity=0.7),
            name='不达标'
        ))
        fig.update_layout(scene=dict(
            xaxis_title=columns[0],
            yaxis_title=columns[1],
            zaxis_title=columns[2]
        ))

    elif para_for_figure == 2:
        x = result_matrix[:, 0]
        y = result_matrix[:, 1]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x[compliant], y=y[compliant],
            mode='markers',
            marker=dict(color='green', size=10, opacity=0.7),
            name='达标'
        ))
        fig.add_trace(go.Scatter(
            x=x[~compliant], y=y[~compliant],
            mode='markers',
            marker=dict(color='red', size=10, opacity=0.7),
            name='不达标'
        ))
        fig.update_layout(
            xaxis_title=columns[0],
            yaxis_title=columns[1]
        )
    else:
        raise ValueError("不支持的维度。目前仅支持 2D 和 3D 数据。")

    return fig


def main(YLimits, ParameterCondition, ExpResults, XLimitsSteps, p, current_dir, task_id):
    limit_raw = read_excel(YLimits).values[:, 1:]
    lower_range = limit_raw[0, :]
    upper_range = limit_raw[1, :]
    NPI = limit_raw.shape[1]

    std_pp = read_excel(ParameterCondition).values
    NEP, NPP = std_pp.shape

    X = Create_terms(std_pp, NEP, NPP)
    exp_results = read_excel(ExpResults).values

    if exp_results.shape[0] != NEP:
        raise ValueError('实验个数和结果个数对不上')
    if exp_results.shape[1] != NPI:
        raise ValueError('指标和优化目标个数对不上')

    pval_stepwise = p
    t1 = time()
    models = []
    selected_features_list = []
    for i in range(NPI):
        model, selected_features = fit_model(X, exp_results[:, i], pval_stepwise, NPP)
        models.append(model)
        selected_features_list.append(selected_features)
    t2 = time()
    print(f'拟合模型用时{t2 - t1:.2f}s')

    xls_xlimits = read_excel(XLimitsSteps)
    ZXLimits_steps = xls_xlimits.values[:, 1:]
    param_columns = xls_xlimits.columns[1:].tolist()  # 获取原始参数列名（排除第一列）
    if ZXLimits_steps.shape[1] != NPP:
        raise ValueError('两次输入的变量总个数对不上')

    x_limit_mid_mat = ZXLimits_steps[0, :] - ZXLimits_steps[1, :]
    different_pp = np.where(x_limit_mid_mat != 0)[0]
    para_for_figure = len(different_pp)

    XLowerRange = ZXLimits_steps[0, :]
    XUpperRange = ZXLimits_steps[1, :]
    XStdStep = ZXLimits_steps[2, :].astype(int)

    X_space = []
    for i in different_pp:
        XRange = np.linspace(XLowerRange[i], XUpperRange[i], XStdStep[i])
        X_space.append(XRange)

    combinations = np.array(list(itertools.product(*X_space)))

    t3 = time()
    all_compliant = Cal_compliance(combinations, models, selected_features_list,
                                   NPI, NPP, lower_range, upper_range,
                                   different_pp, ZXLimits_steps[0, :])
    t4 = time()
    print(f'计算达标情况用时{t4 - t3:.2f}s')

    all_compliant = all_compliant.astype(int)
    result_matrix = np.column_stack((combinations, all_compliant))
    selected_columns = [param_columns[i] for i in different_pp]  # 匹配不同参数的原始列名
    result_df = DataFrame(result_matrix, columns=selected_columns + ['达标'])

    file_dir = f"design-space-noR/{task_id}"
    result_dir = f"{current_dir}/data_files/{file_dir}"
    os.makedirs(result_dir, exist_ok=True)
    if para_for_figure <= 3:
        figure = Display_results(result_matrix, selected_columns)
        figure.write_html(f"{result_dir}/result_plot.html")
    result_df.to_excel(f"{result_dir}/result.xlsx", index=False)

    shutil.make_archive(result_dir, 'zip', result_dir)
    if os.path.exists(result_dir):
        shutil.rmtree(result_dir)

    return file_dir + ".zip"
