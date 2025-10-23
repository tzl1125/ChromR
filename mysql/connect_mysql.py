from sqlalchemy.engine.url import URL
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 数据库连接信息
db_config = {
    "drivername": "mysql+asyncmy",
    "username": "xxxx",
    "password": "xxxx",
    "host": "xxxx",
    "port": 3306,
    "database": "chrom",
}

DATABASE_URL = URL.create(**db_config)

# 创建异步引擎
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncDBSession = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

from sqlalchemy import text


# 异步函数获取 MySQL 版本
async def get_mysql_version():
    async with AsyncDBSession() as session:
        result = await session.execute(text("SELECT VERSION()"))
        version = result.scalar()
        return version

# 主函数
import asyncio

async def main():
    version = await get_mysql_version()
    print(f"MySQL 版本: {version}")

if __name__ == "__main__":
    asyncio.run(main())

