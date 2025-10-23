from arxiv import Client, Search
import pandas as pd
from fastapi import APIRouter, Form
import json

router = APIRouter(
    prefix="/arxiv",
    tags=["arxiv"],
    responses={404: {"description": "Not found"}},
)


@router.post("/")
async def arxiv_search(query: str = Form(description='arxiv 检索式')):
    print(f'arxiv search query: {query}')
    # 使用线程池执行同步函数
    loop = asyncio.get_event_loop()
    result_df = await loop.run_in_executor(None, get_arxiv_data, query)

    if result_df.empty:
        result = "没有查找到文献"
    else:
        parsed = json.loads(result_df.to_json(orient='records'))
        result = json.dumps(parsed, indent=4, ensure_ascii=False)

    return {"result": result}


def get_arxiv_data(query):
    """获取 arxiv 检索结果"""
    client = Client()
    search = Search(
        query=query,
        max_results=100,
    )

    data = []
    for result in client.results(search):
        data.append({
            'url': result.entry_id,
            'published': result.published,
            'title': result.title,
            'authors': [author.name for author in result.authors],
            'summary': result.summary
        })
    print(f"arxiv共检索到 {len(data)} 篇文献")

    return pd.DataFrame(data)


if __name__ == "__main__":
    import asyncio


    async def main():
        await arxiv_search(
            'ti:\"large language model*\" AND cat:q-bio.GN AND submittedDate:[202301010000 TO 202506302359]')


    asyncio.run(main())
