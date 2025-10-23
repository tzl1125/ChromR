import asyncio
from sqlalchemy import text
from connect_mysql import engine


async def create_tables():
    async with engine.begin() as conn:
        try:
            # 打印当前使用的数据库
            result = await conn.execute(text("SELECT DATABASE();"))
            db_name = result.fetchone()[0]
            print(f"Connected to database: {db_name}")

            # 创建上样液属性表
            create_feed_records_table = """
                        CREATE TABLE IF NOT EXISTS FeedRecords (
                            batch VARCHAR(50) NOT NULL PRIMARY KEY,
                            attributes JSON NOT NULL COMMENT '上样液属性，json格式'
                        ) COMMENT='上样液属性表';
                        """
            await conn.execute(text(create_feed_records_table))
            print("FeedRecords table created successfully.")

            # 创建实验设计，工艺优化记录表
            create_optimization_records_table = """
            CREATE TABLE IF NOT EXISTS OptimizationRecords (
                ID INT AUTO_INCREMENT PRIMARY KEY,
                optimization_introduction VARCHAR(500) NOT NULL COMMENT '工艺优化介绍，包括优化对象及使用的实验设计',
                experiment_ids JSON NOT NULL COMMENT '该实验设计涵盖的实验id，及id对应的实验设计中的实验'
            ) COMMENT='实验设计，工艺优化记录表';
            """
            await conn.execute(text(create_optimization_records_table))
            print("OptimizationRecords table created successfully.")

            # 创建实验记录表
            create_experiment_records_table = """
            CREATE TABLE IF NOT EXISTS ExperimentRecords (
                ID INT AUTO_INCREMENT PRIMARY KEY,
                start_time DATETIME COMMENT '开始时间',
                end_time DATETIME COMMENT '结束时间',
                control_command JSON NOT NULL COMMENT '柱层析控制指令',
                feed_number VARCHAR(50) NOT NULL COMMENT '上样液批次',
                phase_wash VARCHAR(50) COMMENT '洗涤溶剂',
                phase_elute VARCHAR(50) COMMENT '洗脱溶剂',
                phase_refresh VARCHAR(50) COMMENT '再生溶剂',
                phase_equilibrate VARCHAR(50) COMMENT '平衡溶剂',
                resin VARCHAR(50) COMMENT '树脂型号',
                column_height FLOAT NOT NULL COMMENT '柱高 (cm)',
                column_inner_diameter FLOAT NOT NULL COMMENT '柱内径 (cm)',
                bed_height FLOAT NOT NULL COMMENT '床层高度 (cm)',
                liquid_height FLOAT NOT NULL COMMENT '液面高度 (cm)',
                product_quality VARCHAR(50) COMMENT '产品质量（指标）',
                product_yield VARCHAR(50)  COMMENT '产品收率（%）',
                product_productivity VARCHAR(50)  COMMENT '产品产率（如g/h）'
            )COMMENT='实验记录表';
            """
            await conn.execute(text(create_experiment_records_table))
            print("ExperimentRecords table created successfully.")

            # 创建传感器表
            create_sensors_table = """
            CREATE TABLE IF NOT EXISTS Sensors (
                ID INT AUTO_INCREMENT PRIMARY KEY,
                time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '时间',
                experiment_id INT NOT NULL COMMENT '实验ID',
                data JSON COMMENT '各个传感器温度(℃)，ORP(mV)，电导率(ms/cm)，pH值，液位计mm',
                FOREIGN KEY (experiment_id) REFERENCES ExperimentRecords(ID) ON DELETE CASCADE
            ) COMMENT='传感器数据表';
            """
            await conn.execute(text(create_sensors_table))
            print("Sensors table created successfully.")

            # 创建紫外数据表
            create_uvs_table = """
            CREATE TABLE IF NOT EXISTS UVs (
                ID INT AUTO_INCREMENT PRIMARY KEY,
                time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '时间',
                experiment_id INT NOT NULL COMMENT '实验ID',
                data TEXT COMMENT '各波长nm下的紫外强度(mau)',
                FOREIGN KEY (experiment_id) REFERENCES ExperimentRecords(ID) ON DELETE CASCADE
            ) COMMENT='紫外数据表';
            """
            await conn.execute(text(create_uvs_table))
            print("UVs table created successfully.")

            # 创建近红外数据表
            create_nirs_table = """
            CREATE TABLE IF NOT EXISTS NIRs (
                ID INT AUTO_INCREMENT PRIMARY KEY,
                time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '时间',
                experiment_id INT NOT NULL COMMENT '实验ID',
                data TEXT COMMENT '各波长nm下的近红外强度(mau)',
                FOREIGN KEY (experiment_id) REFERENCES ExperimentRecords(ID) ON DELETE CASCADE
            ) COMMENT='近红外数据表';
            """
            await conn.execute(text(create_nirs_table))
            print("NIRs table created successfully.")

            # 创建日志记录表
            create_logs_table = """
            CREATE TABLE IF NOT EXISTS Logs (
                ID INT AUTO_INCREMENT PRIMARY KEY,
                time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '时间',
                experiment_id INT NOT NULL COMMENT '实验ID',
                content VARCHAR(255) NOT NULL COMMENT '内容',
                FOREIGN KEY (experiment_id) REFERENCES ExperimentRecords(ID) ON DELETE CASCADE
            ) COMMENT='日志记录表';
            """
            await conn.execute(text(create_logs_table))
            print("Logs table created successfully.")

            # --------------------------
            # 添加索引以提高查询速度
            # --------------------------

            # 传感器表：按experiment_id筛选，按time排序
            await conn.execute(text("CREATE INDEX idx_sensors_exp_time ON Sensors(experiment_id, time);"))

            # 紫外数据表：同上
            await conn.execute(text("CREATE INDEX idx_uvs_exp_time ON UVs(experiment_id, time);"))

            # 近红外数据表：同上
            await conn.execute(text("CREATE INDEX idx_nirs_exp_time ON NIRs(experiment_id, time);"))

            print("All indexes created successfully.")

        except Exception as e:
            print(f"An error occurred: {e}")


async def drop_all_tables():
    async with engine.begin() as conn:
        try:
            # 定义表删除顺序，先删除有外键引用的表，最后删除被引用的表
            table_names = ['Sensors', 'UVs', 'NIRs', 'Logs', 'OptimizationRecords', 'FeedRecords', 'ExperimentRecords']

            # 依次删除所有表
            for table_name in table_names:
                drop_table_query = f"DROP TABLE IF EXISTS {table_name};"
                await conn.execute(text(drop_table_query))
                print(f"Table {table_name} dropped successfully.")

        except Exception as e:
            print(f"An error occurred while dropping tables: {e}")


if __name__ == "__main__":
    asyncio.run(create_tables())
    # asyncio.run(drop_all_tables())
