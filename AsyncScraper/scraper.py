import os
import asyncio
from playwright.async_api import async_playwright, expect
from playwright.async_api import ElementHandle, TimeoutError, Error, Playwright, Page, Locator, LocatorAssertions
import pandas as pd
from tqdm import tqdm
from .sanitizingClasses import SectionTr, Course, Section, create_section_tr

class TermScraper:
    def __init__(self, term: str, base_out_path: str, is_headless: bool = False, url: str = 'https://ssb1-reg.banner.marist.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search', MAX_PAGE_RETRY=5, MAX_TR_RETRY=3, TO_CSV_BUFFER: int=5_000) -> None:
        self.term: str = term
        self.out_path: str = f"{base_out_path}/{term.replace(' ', '')}"
        self.headless: bool = is_headless
        self.url: str = url
        self.MAX_PAGE_RETRY: int = MAX_PAGE_RETRY
        self.MAX_TR_RETRY: int = MAX_TR_RETRY
        self.TO_CSV_BUFFER: int = TO_CSV_BUFFER

        self.prep_csv()

    
    def prep_csv(self) -> None:
        if not os.path.exists(self.out_path): # No previous data
            os.makedirs(self.out_path)
            course_headers_df = pd.DataFrame(columns=Course.header_row)
            section_headers_df = pd.DataFrame(columns=Section.header_row)
            course_headers_df.to_csv(f"{self.out_path}/courses.csv", header=True, index=False)
            section_headers_df.to_csv(f"{self.out_path}/sections.csv", header=True, index=False)
            return
        # There is previous data
        courses_df = pd.read_csv(f"{self.out_path}/courses.csv", usecols=["subject", "number", "id"])
        for _, row in courses_df.iterrows():
            Course.next_id += 1
            Course.courses[row['subject'] + row['number']] = int(row['id'])

        sections_df = pd.read_csv(f"{self.out_path}/sections.csv", usecols=['data_id'])
        for _, row in sections_df.iterrows():
            Section.sections.add(int(row['data_id']))

    async def run(self, num_of_tabs: int = 8) -> None:
        async with async_playwright() as playwright:
            self.bad_pages: list[int] = []
            

            # getting info to configure tasks
            self.playwright = playwright
            self.browser = await playwright.chromium.launch(headless=self.headless)
            page = await self.browser.new_page()
            await self.nav_to_search(page)
            self.last_page =  int(await page.locator('span[class="paging-text total-pages"]').inner_text())
            total_sections_text: str = await page.locator('span[class="results-out-of"]').inner_text()
            self.sections_count: int = int(total_sections_text.split(" ")[0])
            pages_each: int = (self.last_page // num_of_tabs)
            pages_left_over: int = self.last_page % num_of_tabs
            if num_of_tabs > self.last_page:
                pages_each = 1
                pages_left_over = 0
            await page.close()

            tasks = []

            # subdividing the pages and creating tasks
            running_start_page = 1
            for i in range(min(num_of_tabs, self.last_page)):
                num_of_pages = pages_each + 1 if i < pages_left_over else pages_each
                tasks.append(self.scrape_pages(running_start_page, running_start_page + num_of_pages-1))
                running_start_page += num_of_pages
            self.pages_current_running = num_of_tabs

            # csv handling
            self.courses: list[Course] = []
            self.sections: list[Section] = []
            tasks.append(self.add_to_csv())

            self.progress_bar = tqdm(total=self.sections_count)

            await asyncio.gather(*tasks)
            self.progress_bar.close()

            await self.browser.close()

            self.add_to_csv_sync() # ensure everything was submitted
            print(f"Pages with mistakes: {self.bad_pages}")
    

    async def nav_to_search(self, page: Page):
        await page.goto(self.url)
        await page.click('div[id="s2id_txt_term"]') # term live search
        await page.locator('input[id="s2id_autogen1_search"]').fill(self.term) # term text input
        await page.wait_for_load_state("domcontentloaded")
        await page.click('li[role="presentation"]') # click on term
        await page.click('button[id="term-go"]') # go to term search
        await page.click('button[id="search-go"]') # search with no param for the term
        await page.locator('select[class="page-size-select"]').select_option('50')
        await page.wait_for_selector('select[aria-label="50 per page"]', timeout=10000)

    

    async def scrape_pages(self, start_page, end_page) -> None:
        # implement scraping from start_page to end_page
        page = await self.browser.new_page()
        await self.nav_to_search(page)

        for page_number in range(start_page, end_page + 1):
            try:
                await self.scrape_page(page=page, page_number=page_number)
            except Error:
                self.bad_pages.append(page_number)
        await page.close()
        self.pages_current_running -= 1


    async def scrape_page(self, page: Page, page_number: int, retry_depth: int = 1) -> None:
        try:
            await self.select_page(page=page, page_number=page_number)
            tr_count = self.sections_count % 50 if page_number == self.last_page else 50
            await page.wait_for_selector('tr[data-id]', timeout=3000)
            locator_trs: Locator = page.locator('tr[data-id]')
            await expect(locator_trs).to_have_count(tr_count) # ensure that there is the correct amount trs
            for locator_tr in await locator_trs.all():
                await self.scrape_tr(page=page, locator_tr=locator_tr)
        except Error:
            if retry_depth >= self.MAX_PAGE_RETRY: raise Error("Max retry limit reached")

            await self.nav_to_search(page=page)
            await self.scrape_page(page, page_number, retry_depth=retry_depth + 1)
    

    async def scrape_tr(self, page: Page, locator_tr: Locator, retry_depth: int = 1):
        try:
            section_tr: SectionTr = await create_section_tr(locator_tr.element_handle(timeout=5000))
            if int(section_tr.tr_data_id) in Section.sections: return
            course_id = Course.get_course(section_tr.subject, section_tr.course_number)
            if course_id is not None:
                self.sections.append(Section(section_tr=section_tr, course_id=course_id))
                self.progress_bar.update(1)
                return
            new_course = Course(section_tr=section_tr)
            self.sections.append(Section(section_tr=section_tr, course_id=new_course.id))
            await new_course.add_catalog_info(tr=section_tr.tr, page=page)
            self.courses.append(new_course)
            self.progress_bar.update(1)
        except Error:
            if retry_depth >= self.MAX_TR_RETRY: raise Error("Max tr retry limit reached")
            possible_button_to_close: ElementHandle = await page.query_selector('button["primary-button small-button"]')
            if possible_button_to_close: await possible_button_to_close.click()
            await self.scrape_tr(page=page, locator_tr=locator_tr, retry_depth=retry_depth + 1)
        

    async def select_page(self, page: Page, page_number: int) -> None:
        await page.wait_for_selector('input[title="Page"]', timeout=3000)
        page_number_element: Locator = page.locator('input[title="Page"]')
        await page_number_element.fill(str(page_number))
        await page_number_element.press('Enter')
    

    async def add_to_csv(self) -> None:
        await asyncio.sleep(self.TO_CSV_BUFFER/ 1000)
        courses_df = pd.DataFrame(map(Course.to_csv, self.courses))
        sections_df = pd.DataFrame(map(Section.to_csv, self.sections))
        courses_df.to_csv(f"{self.out_path}/courses.csv", mode='a', header=False, index=False)
        sections_df.to_csv(f"{self.out_path}/sections.csv", mode='a', header=False, index=False)
        self.courses = []
        self.sections = []

        if self.pages_current_running > 0:
            await self.add_to_csv()
    
    def add_to_csv_sync(self) -> None:
        courses_df = pd.DataFrame(map(Course.to_csv, self.courses))
        sections_df = pd.DataFrame(map(Section.to_csv, self.sections))
        courses_df.to_csv(f"{self.out_path}/courses.csv", mode='a', header=False, index=False)
        sections_df.to_csv(f"{self.out_path}/sections.csv", mode='a', header=False, index=False)