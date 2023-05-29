from AsyncScraper.scraper import TermScraper
import asyncio
import sys

async def main():
    try:
        terms = sys.argv[1:]
    except IndexError:
        print("Please put the term(s) you want to scrap as arguments as \"Season Year\"")

    for term in terms:
        print(f"Progress for term {term}:")
        term_scraper = TermScraper(term=term, base_out_path="./output", url='https://ssb1-reg.banner.marist.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search', is_headless=True)
        await term_scraper.run(11)

if __name__ == "__main__":
    asyncio.run(main())
