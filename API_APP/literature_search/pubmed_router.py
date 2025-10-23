import pandas as pd
from fastapi import APIRouter, Form
import json
from Bio import Entrez, Medline

router = APIRouter(
    prefix="/pubmed",
    tags=["pubmed"],
    responses={404: {"description": "Not found"}},
)


@router.post("/")
async def pubmed_search(query: str = Form(description='pubmed 检索式')):
    print(f'pubmed search query: {query}')
    # 使用线程池执行同步函数
    loop = asyncio.get_event_loop()
    result_df = await loop.run_in_executor(None, search_pubmed, query)

    if result_df.empty:
        result = "没有查找到文献"
    else:
        parsed = json.loads(result_df.to_json(orient='records'))
        result = json.dumps(parsed, indent=4, ensure_ascii=False)

    return {"result": result}


def search_pubmed(query):
    Entrez.email = 'xxxx'
    Entrez.api_key = "xxxx"

    handle = Entrez.esearch(db='pubmed', retmax=100, term=query)
    record = Entrez.read(handle)
    id_list = record['IdList']

    df = pd.DataFrame(
        columns=['Title', 'Abstract', 'Authors', 'Journal', 'Keywords', 'DOI', 'URL', 'PublicationDate'])

    print(f"pubmed成功检索{len(id_list)}条记录")
    for pmid in id_list:
        handle = Entrez.efetch(db='pubmed', id=pmid, rettype='medline', retmode='text')
        records = Medline.parse(handle)
        record = next(records)

        title = record.get('TI', '')
        abstract = record.get('AB', '')
        authors = ', '.join(record.get('AU', []))
        journal = record.get('JT', '')
        keywords = ', '.join(record.get('MH', []))
        lid_value = record.get('LID', '')
        doi = ''
        if lid_value:
            parts = lid_value.split()
            if parts:
                doi = parts[0].replace('[doi]', '')
        url = f"https://www.ncbi.nlm.nih.gov/pubmed/{pmid}"

        pub_date = record.get('EDAT', '')
        if not pub_date:
            pub_date = record.get('DP', '')

        new_row = pd.DataFrame({
            'Title': [title],
            'Abstract': [abstract],
            'Authors': [authors],
            'Journal': [journal],
            'Keywords': [keywords],
            'DOI': [doi],
            'URL': [url],
            'PublicationDate': [pub_date]
        })
        df = pd.concat([df, new_row], ignore_index=True)

    return df


if __name__ == "__main__":
    import asyncio


    async def main():
        await pubmed_search("\"type 2 diabetes\" AND (drug therapy OR pharmacotherapy)"
                            " AND \"clinical trial\"[pt] AND \"JAMA\"[ta] AND 2018:2023[dp]")


    asyncio.run(main())
