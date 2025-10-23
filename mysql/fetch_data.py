import asyncio
import json
import pandas as pd
from sqlalchemy import text
from connect_mysql import AsyncDBSession
from tqdm.asyncio import tqdm_asyncio


async def export_sensor_data(experiment_id: int, output_path: str, page_size=1000):
    """
    导出指定实验ID的传感器数据到Excel文件（带进度条和分页）
    :param experiment_id: 实验ID
    :param output_path: 输出Excel文件路径
    """
    async with AsyncDBSession() as session:
        # 1. 获取总记录数（用于进度条）
        count_query = text("""
            SELECT COUNT(*) 
            FROM Sensors 
            WHERE experiment_id = :exp_id
        """)
        result = await session.execute(count_query, {"exp_id": experiment_id})
        total_records = result.scalar()

        if total_records == 0:
            print(f"实验ID {experiment_id} 没有找到传感器数据")
            return

        print(f"开始导出传感器数据，共 {total_records} 条记录...")

        # 2. 分页查询数据
        data = []
        progress_bar = tqdm_asyncio(total=total_records, desc="导出传感器数据")

        offset = 0
        while offset < total_records:
            query = text("""
                SELECT time, data 
                FROM Sensors 
                WHERE experiment_id = :exp_id 
                ORDER BY time
                LIMIT :limit OFFSET :offset
            """)
            result = await session.execute(
                query,
                {
                    "exp_id": experiment_id,
                    "limit": page_size,
                    "offset": offset
                }
            )
            rows = result.fetchall()

            # 3. 流式处理每页数据
            for row in rows:
                time_str = row[0].strftime("%Y-%m-%d %H:%M:%S") if row[0] else None
                sensor_data = json.loads(row[1]) if row[1] else {}

                # 提取各传感器值（处理可能的缺失数据）
                ph_value = sensor_data.get('ph', {}).get('value')
                orp_value = sensor_data.get('orp', {}).get('value')
                conductivity_value = sensor_data.get('conductivity', {}).get('value')
                level_value = sensor_data.get('level', {}).get('value')
                # 分别获取各传感器的温度（如果有）
                ph_temperature = sensor_data.get('ph', {}).get('temperature')
                orp_temperature = sensor_data.get('orp', {}).get('temperature')
                conductivity_temperature = sensor_data.get('conductivity', {}).get('temperature')

                data.append({
                    '时间': time_str,
                    'pH传感器温度(℃)': ph_temperature,
                    'ORP传感器温度(℃)': orp_temperature,
                    '电导率传感器温度(℃)': conductivity_temperature,
                    'ORP(mV)': orp_value,
                    '电导率(ms/cm)': conductivity_value,
                    'pH值': ph_value,
                    '液位计mm': level_value
                })

            offset += len(rows)
            progress_bar.update(len(rows))

        progress_bar.close()

        # 4. 写入Excel
        df = pd.DataFrame(data)
        df.to_excel(output_path, index=False)
        print(f"\n传感器数据已导出至 {output_path}")


async def export_spectrum_data(experiment_id: int, spectrum_type: str, output_path: str, page_size=1000):
    """
    导出指定实验ID的紫外或近红外光谱数据到Excel文件（带进度条和分页）
    :param experiment_id: 实验ID
    :param spectrum_type: 光谱类型，'uv' 或 'nir'
    :param output_path: 输出Excel文件路径
    """
    if spectrum_type not in ['uv', 'nir']:
        raise ValueError("spectrum_type must be either 'uv' or 'nir'")

    table_name = "UVs" if spectrum_type == 'uv' else "NIRs"
    spectrum_name = "紫外" if spectrum_type == 'uv' else "近红外"

    async with AsyncDBSession() as session:
        # 1. 获取总记录数
        count_query = text(f"""
            SELECT COUNT(*) 
            FROM {table_name} 
            WHERE experiment_id = :exp_id
        """)
        result = await session.execute(count_query, {"exp_id": experiment_id})
        total_records = result.scalar()

        if total_records == 0:
            print(f"实验ID {experiment_id} 没有找到{spectrum_name}光谱数据")
            return

        print(f"开始导出{spectrum_name}光谱数据，共 {total_records} 条记录...")

        # 2. 分页查询数据
        data = []
        progress_bar = tqdm_asyncio(total=total_records, desc=f"导出{spectrum_name}光谱数据")

        offset = 0
        while offset < total_records:
            query = text(f"""
                SELECT time, data 
                FROM {table_name} 
                WHERE experiment_id = :exp_id 
                ORDER BY time
                LIMIT :limit OFFSET :offset
            """)
            result = await session.execute(
                query,
                {
                    "exp_id": experiment_id,
                    "limit": page_size,
                    "offset": offset
                }
            )
            rows = result.fetchall()

            # 3. 流式处理每页数据
            for row in rows:
                time_str = row[0].strftime("%Y-%m-%d %H:%M:%S") if row[0] else None
                spectrum_data = json.loads(row[1]) if row[1] else {}

                # 构建每行数据（时间 + 各波长吸光度）
                row_data = {'时间': time_str}
                row_data.update(spectrum_data)
                data.append(row_data)

            offset += len(rows)
            progress_bar.update(len(rows))

        progress_bar.close()

        # 4. 写入Excel
        df = pd.DataFrame(data)
        df.to_excel(output_path, index=False)
        print(f"\n{spectrum_name}光谱数据已导出至 {output_path}")


if __name__ == "__main__":
    test_exp_id = 29  # 需要导出的数据的实验ID


    async def main():
        # 并行执行三个导出任务
        await asyncio.gather(
            export_sensor_data(test_exp_id, f"sensor_data_ID={test_exp_id}.xlsx"),
            export_spectrum_data(test_exp_id, "uv", f"uv_data_ID={test_exp_id}.xlsx", 200),
            export_spectrum_data(test_exp_id, "nir", f"nir_data_ID={test_exp_id}.xlsx", 200)
        )


    asyncio.run(main())
