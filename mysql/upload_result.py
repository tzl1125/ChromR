from typing import List, Dict

import pandas as pd
from sqlalchemy import text

from mysql import AsyncDBSession


def read_excel_data(excel_path: str) -> List[Dict]:
    """
    读取Excel文件数据，返回处理后的字典列表（适配数据库字段）

    Args:
        excel_path: Excel文件路径（如"实验数据.xlsx"）

    Returns:
        处理后的数据列表，每个元素包含：id、合并后的product_quality、product_yield、product_productivity
    """
    # 读取Excel（假设Excel表名为"Sheet1"，可根据实际修改）
    df = pd.read_excel(excel_path, sheet_name="Sheet1", engine="openpyxl")

    # 数据清洗：去除空行、确保必要字段存在
    required_columns = ["id", "总内酯", "总黄酮醇苷", "产品收率", "产品产量"]
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Excel文件缺少必要字段：{', '.join(missing_cols)}")

    # 处理每一行数据，合并产品质量字段
    data_list = []
    for _, row in df.iterrows():
        # 跳过id为空的行
        if pd.isna(row["id"]):
            continue

        # 合并总内酯和总黄酮醇苷为产品质量（保留2位小数，适配百分比格式）
        total_lactone = round(row["总内酯"], 2) if not pd.isna(row["总内酯"]) else 0.0
        total_flavonol_glycoside = round(row["总黄酮醇苷"], 2) if not pd.isna(row["总黄酮醇苷"]) else 0.0
        product_quality = f"总内酯为{total_lactone}% 总黄酮为{total_flavonol_glycoside}%"

        # 提取其他字段（空值填充为0，可根据业务调整）
        product_yield = round(row["产品收率"], 2) if not pd.isna(row["产品收率"]) else 0.0
        product_productivity = round(row["产品产量"], 2) if not pd.isna(row["产品产量"]) else 0.0

        data_list.append({
            "id": int(row["id"]),  # 确保id为整数（匹配数据库ID类型）
            "product_quality": product_quality,
            "product_yield": f"{product_yield}%",
            "product_productivity": f"{product_productivity}g/h"
        })

    return data_list


async def batch_save_experiment_index(data_list: List[Dict]) -> None:
    """
    批量将Excel处理后的数据同步上传至数据库（高效批量更新）

    Args:
        data_list: 经read_excel_data处理后的字典列表
    """
    if not data_list:
        print("无有效数据可同步")
        return

    # 批量更新SQL（一次执行多条更新，提升效率）
    sql = """
    UPDATE ExperimentRecords
    SET product_quality = :quality,
        product_yield = :yield_,
        product_productivity = :productivity
    WHERE ID = :id
    """

    async with AsyncDBSession() as session:
        try:
            # 批量执行更新（传入参数列表，而非单条执行）
            await session.execute(
                text(sql),
                [
                    {
                        "quality": item["product_quality"],
                        "yield_": item["product_yield"],
                        "productivity": item["product_productivity"],
                        "id": item["id"]
                    }
                    for item in data_list
                ]
            )
            await session.commit()
            print(f"成功上传{len(data_list)}条实验数据至数据库")
        except Exception as e:
            await session.rollback()
            print(f"上传实验数据错误: {str(e)}")
            raise


# ------------------- 调用示例 -------------------
async def sync_excel_to_db(excel_path: str):
    """
    完整同步流程：读取Excel → 批量上传数据库
    """
    try:
        data = read_excel_data(excel_path)
        if data:
            await batch_save_experiment_index(data)
    except Exception as e:
        print(f"上传失败：{str(e)}")


if __name__ == "__main__":
    import asyncio

    excel_file_path = "test.xlsx"
    asyncio.run(sync_excel_to_db(excel_file_path))
