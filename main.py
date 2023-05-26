from AsyncScraper.scraper import TermScraper
import asyncio

async def main():
    term_scraper = TermScraper(term="Spring 2021", base_out_path="./output", is_headless=True)
    await term_scraper.run(10)

if __name__ == "__main__":
    asyncio.run(main())
