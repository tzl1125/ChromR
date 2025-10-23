import asyncio
import json

import pandas as pd
import pybliometrics
from fastapi import APIRouter, Form
from pybliometrics.scopus import ScopusSearch

router = APIRouter(
    prefix="/scopus",
    tags=["scopus"],
    responses={404: {"description": "Not found"}},
)


@router.post("/")
async def scopus_search(query: str = Form(description='scopus 检索式')):
    print(f'scopus search query: {query}')
    loop = asyncio.get_event_loop()

    try:
        # 设置3分钟超时限制
        result_df = await asyncio.wait_for(
            loop.run_in_executor(None, main, query),
            timeout=180.0  # 180秒 = 3分钟
        )
    except asyncio.TimeoutError:
        print("Scopus检索超时，已取消任务")
        return {"result": "检索超时，请简化检索式后重试"}
    except Exception as e:
        print(f"检索过程中发生错误: {str(e)}")
        return {"result": f"检索错误: {str(e)}"}

    if result_df.empty:
        result = "没有查找到文献"
    else:
        parsed = json.loads(result_df.to_json(orient='records'))
        result = json.dumps(parsed, indent=4, ensure_ascii=False)

    return {"result": result}


def get_scopus_data(query):
    """获取 Scopus 检索结果并处理可能的 API 限制"""
    search = ScopusSearch(query, verbose=True)
    df = pd.DataFrame(search.results)
    record_count = len(df)

    if record_count > 100:
        df = df.head(100)
        print(f"scopus检索结果超过100条，已截取前100条记录")

    print(f"scopus成功获取 {len(df)} 条记录")
    return df


def main(query):
    pybliometrics.scopus.init()
    df = get_scopus_data(query)
    if df.empty:
        return df
    processed_df = df[['title', 'author_names', 'description', 'publicationName', 'doi', 'coverDate']].copy()
    processed_df.columns = ['标题', '作者', '摘要', '期刊', 'DOI', '发布时间']
    return processed_df


if __name__ == "__main__":
    async def search():
        await scopus_search('TITLE-ABS-KEY ( optimization AND of AND chromatography )  AND PUBYEAR > 2025')


    asyncio.run(search())
