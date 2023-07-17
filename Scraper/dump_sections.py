import json
import asyncio
import os
import math
from playwright.async_api import async_playwright, BrowserContext 


async def add_sections(page_offset: int, page_max_size: int, context: BrowserContext, running_data: list):
    url = f"https://ssb1-reg.banner.marist.edu/StudentRegistrationSsb/ssb/searchResults/searchResults?startDatepicker=&endDatepicker=&pageOffset={page_offset}&pageMaxSize={page_max_size}"
    page = await context.new_page()
    await page.goto(url)
    content = await page.content()
    content = content[content.find("{"):content.rfind("}") + 1]
    try:
        content = json.loads(content)
    except json.decoder.JSONDecodeError as e:
        print(e)
        char_position = int(str(e).split("char ")[-1][:-1])
        print(content[char_position-50:char_position+50])
        return
    
    running_data = running_data.extend(content.get('data'))

    await page.close()


async def scrape_term(term):
    url = "https://ssb1-reg.banner.marist.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search"
    count_per_page = 500 
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True) 
        context = await browser.new_context()
        page = await context.new_page()

        # for some reason the term query field in the GET request is actually fake
        #   you must actually associate your cookie with the selected term
        #   I do this navigating to a term in the session then closing the page
        await page.goto(url)
        await page.click('div[id="s2id_txt_term"]') # term live search
        await page.locator('input[id="s2id_autogen1_search"]').fill(term) # term text input
        await page.wait_for_load_state("domcontentloaded")
        await page.click('li[role="presentation"]') # click on term
        await page.click('button[id="term-go"]') # go to term search
        await page.click('button[id="search-go"]') # search with no param for the term
        total_sections_text: str = await page.locator('span[class="results-out-of"]').inner_text()
        sections_count: int = int(total_sections_text.split(" ")[0])
        await page.close()

        tasks = []
        running_data = []
        for i in range(math.ceil(sections_count / count_per_page)):
            tasks.append(add_sections(i, count_per_page, context, running_data))
        
        await asyncio.gather(*tasks)

        if not os.path.exists('output'):
            os.mkdir('output')

        with open(f'output/sections{term.replace(" ", "")}.json', 'w') as file:
            json.dump(running_data, file, indent=4)


if __name__ == "__main__":
    asyncio.run(scrape_term('2023'))