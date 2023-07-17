from Scraper.dump_sections import scrape_term
from Scraper.dump_courses import scrape_latest_term
import asyncio
import sys

async def main():
    instructions = "To scrape sections: 'python .\main.py sections \"Season Year\"\n\
        To scrape courses: 'python .\main.py courses'"
    try:
        args = sys.argv[1:]
    except IndexError:
        print("Invalid input")
        print(instructions)

    main_arg: str = args[0]

    if main_arg.lower() == 'sections':
        try:
            terms = args[1:]
        except IndexError:
            print("Invalid input")
            print(instructions)

        tasks = []
        for term in terms:
            tasks.append(scrape_term(term))
        
        await asyncio.gather(*tasks)
    elif main_arg.lower() == 'courses':
        await scrape_latest_term()
    else:
        print("Invalid input")
        print(instructions)


if __name__ == "__main__":
    asyncio.run(main())
