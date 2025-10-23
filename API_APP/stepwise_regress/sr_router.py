from io import BytesIO

import numpy as np
import pandas as pd
import statsmodels.api as sm
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from toad.selection import stepwise

router = APIRouter(
    prefix="/stepwise-regress",
    tags=["stepwise-regress"],
    responses={404: {"description": "Not found"}},
)


def Create_terms(material_raw, X, X_columns, material_columns, NEP, NPP,
                 include_interaction=True, include_quadratic=True):
    '''
    生成包含常数项以及各个变量一次项、二次项、交叉项的向量
    input：
        material_raw：物料属性的向量，不包含常数项（可为None）
        X：其他变量的向量，不包含常数项
        X_columns：其他变量的列名列表
        material_columns：物料属性的列名列表（可为空）
        NEP：实验数
        NPP：其他因子数（X的列数，不包括物料）
        include_interaction：是否包含交叉项
        include_quadratic：是否包含二次项
    return：DataFrame，包含指定项的向量，列名对应
    '''
    # 初始化各部分数据和列名
    parts = [np.ones((NEP, 1))]  # 常数项
    columns = ['Constant']

    # 添加物料属性（仅一次项）
    if material_raw is not None and material_raw.size > 0:
        parts.append(material_raw)
        columns.extend(material_columns)

    # 添加其他变量一次项
    parts.append(X)
    columns.extend(X_columns)

    # 生成其他变量交叉项（可选）
    interaction_columns = []
    interaction = np.zeros((NEP, 0))
    if include_interaction:
        for i in range(NPP - 1):
            for j in range(i + 1, NPP):
                interaction_mid = np.multiply(X[:, i], X[:, j])
                interaction = np.column_stack([interaction, interaction_mid])
                interaction_columns.append(f'{X_columns[i]}*{X_columns[j]}')
    parts.append(interaction)
    columns.extend(interaction_columns)

    # 生成其他变量二次项（可选）
    nonlinear_columns = []
    nonlinear = np.zeros((NEP, 0))
    if include_quadratic:
        nonlinear_columns = [f'{col}^2' for col in X_columns]
        nonlinear = np.square(X)
    parts.append(nonlinear)
    columns.extend(nonlinear_columns)

    # 合并所有部分并转换为DataFrame
    X_terms_withconst = np.hstack(parts)
    return pd.DataFrame(X_terms_withconst, columns=columns).astype(np.float64)


def get_required_primary_terms(selected_vars, X_columns):
    """提取交叉项和二次项对应的必须保留的一次项"""
    required = set()
    for var in selected_vars:
        # 处理交叉项（格式如"A*B"）
        if '*' in var:
            terms = var.split('*')
            # 验证是否为X_columns中的变量组合
            if all(term in X_columns for term in terms):
                required.update(terms)
        # 处理二次项（格式如"A^2"）
        elif '^2' in var:
            base_term = var.replace('^2', '')
            if base_term in X_columns:
                required.add(base_term)
    return required


def analyse(pc_file, er_file, material_file=None, p_value=0.1):
    try:
        # 读取核心数据文件
        para_con = pd.read_excel(pc_file)
        exp_result = pd.read_excel(er_file)
        result_columns = exp_result.columns.tolist()

        # 读取物料属性文件（如果提供）
        material_raw = None
        material_columns = []
        if material_file is not None:
            material_df = pd.read_excel(material_file)
            material_raw = material_df.values
            material_columns = material_df.columns.tolist()

        # 转换为数值矩阵
        para_con_np = para_con.values
        exp_result_np = exp_result.values

        NEP, NPP = para_con_np.shape  # 实验次数，其他因子个数（不含物料）
        NPI = exp_result_np.shape[1]  # 评价指标个数

        # 验证实验次数一致性
        if NEP != exp_result_np.shape[0]:
            raise ValueError(
                f"实验次数不匹配: 因子数据({NEP}行)与结果数据({exp_result_np.shape[0]}行)不一致"
            )

        # 验证物料属性实验次数（如果提供）
        if material_raw is not None and material_raw.shape[0] != NEP:
            raise ValueError(
                f"实验次数不匹配: 物料属性数据({material_raw.shape[0]}行)与因子数据({NEP}行)不一致"
            )

        X_columns = para_con.columns.tolist()
        results = []

        # 对每个评价指标进行分析
        for i in range(NPI):
            target_col = result_columns[i]
            target_data = exp_result_np[:, i].flatten()

            # 固定使用指定的p值进行建模
            current_p = p_value

            # 第一次建模：仅包含一次项
            X_terms_first = Create_terms(
                material_raw=material_raw,
                X=para_con_np,
                X_columns=X_columns,
                material_columns=material_columns,
                NEP=NEP,
                NPP=NPP,
                include_interaction=False,
                include_quadratic=False,
            )
            temp_first = X_terms_first.copy()
            temp_first[target_col] = target_data

            # 第一次逐步回归（使用固定p值）
            selected_first = stepwise(
                temp_first,
                target=target_col,
                estimator='ols',
                direction='both',
                p_enter=current_p,
                p_value_enter=current_p,
            )

            # 计算一次项模型R²（处理无变量选中的情况）
            r2_first = 0.0
            model_first = None
            if len(selected_first.columns) > 1:  # 确保有自变量
                x_first = sm.add_constant(selected_first.drop(columns=[target_col]))
                y_first = selected_first[target_col]
                model_first = sm.OLS(y_first, x_first).fit()
                r2_first = model_first.rsquared

            # 第二次建模：包含一次项、交叉项、二次项（当一次项模型不够好时）
            r2_second = 0.0
            model_second = None
            if r2_first < 0.95:  # 原判断条件保留
                X_terms_second = Create_terms(
                    material_raw=material_raw,
                    X=para_con_np,
                    X_columns=X_columns,
                    material_columns=material_columns,
                    NEP=NEP,
                    NPP=NPP,
                    include_interaction=True,
                    include_quadratic=True,
                )
                temp_second = X_terms_second.copy()
                temp_second[target_col] = target_data

                # 第二次逐步回归（使用固定p值）
                selected_second_stepwise = stepwise(
                    temp_second,
                    target=target_col,
                    estimator='ols',
                    direction='both',
                    p_enter=current_p,
                    p_value_enter=current_p,
                )

                # 提取筛选后的变量（排除目标列）
                selected_vars = [col for col in selected_second_stepwise.columns if col != target_col]
                if selected_vars:  # 确保有自变量
                    # 确定必须保留的一次项
                    required_primary = get_required_primary_terms(selected_vars, X_columns)
                    final_selected_vars = list(set(selected_vars) | required_primary)

                    # 构建最终建模数据
                    final_second_data = temp_second[final_selected_vars + [target_col]]
                    x_second = sm.add_constant(final_second_data.drop(columns=[target_col]))
                    y_second = final_second_data[target_col]
                    model_second = sm.OLS(y_second, x_second).fit()
                    r2_second = model_second.rsquared

            # 比较两个模型
            best_r2 = max(r2_first, r2_second)
            best_model = model_first if r2_first >= r2_second else model_second
            best_model_type = "仅一次项模型" if r2_first >= r2_second else "包含交叉项和二次项的模型"

            # 记录结果
            results.append(
                f"指标 {target_col} 选择{best_model_type} (R²: {best_r2:.4f}, 使用p值: {current_p:.2f})\n{best_model.summary().as_html()}"
            )

        return '\n\n'.join(results)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/")
async def stepwise_regress(
        p: float = Form(default=0.1, gt=0, lt=1, description="p值阈值"),
        er: UploadFile = File(description="实验结果Excel文件（.xls/.xlsx）"),
        pc: UploadFile = File(description="实验因子Excel文件（.xls/.xlsx）"),
        material: UploadFile = File(default=None, description="物料属性Excel文件（可选，.xls/.xlsx）")
):
    # 验证文件类型
    if not er.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail="实验结果文件必须是Excel格式（.xls/.xlsx）")
    if not pc.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail="实验因子文件必须是Excel格式（.xls/.xlsx）")
    if material and not material.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail="物料属性文件必须是Excel格式（.xls/.xlsx）")

    try:
        # 读取上传的文件内容
        er_content = await er.read()
        pc_content = await pc.read()
        material_content = await material.read() if material else None

        # 转换为文件流用于pandas读取
        er_file = BytesIO(er_content)
        pc_file = BytesIO(pc_content)
        material_file = BytesIO(material_content) if material_content else None

        result_html = analyse(
            pc_file=pc_file,
            er_file=er_file,
            material_file=material_file,
            p_value=p
        )
        return {'result': result_html}

    except Exception as e:
        # 处理文件读取和分析过程中的异常
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"处理过程出错: {str(e)}")
    finally:
        # 关闭文件流
        await er.close()
        await pc.close()
        if material:
            await material.close()