from JsonParser.json_dumper import scrape_term
import asyncio
import sys

async def main():
    try:
        terms = sys.argv[1:]
    except IndexError:
        print("Please put the term(s) you want to scrap as arguments as \"Season Year\"")

    tasks = []

    for term in terms:
        tasks.append(scrape_term(term))
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
