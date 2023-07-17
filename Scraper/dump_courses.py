import aiohttp
import requests
import asyncio
import json
import math
import os
from playwright.async_api import async_playwright, BrowserContext 


# all of these requests do not require session cookies so can be down without playwright
async def add_more_course_info(course: dict, course_id: str, term: str, session: aiohttp.ClientSession):
    url_co_reqs = "https://ssb1-reg.banner.marist.edu/StudentRegistrationSsb/ssb/searchResults/getCorequisites"
    url_pre_reqs = "https://ssb1-reg.banner.marist.edu/StudentRegistrationSsb/ssb/searchResults/getSectionPrerequisites"
    url_course_desc = "https://ssb1-reg.banner.marist.edu/StudentRegistrationSsb/ssb/searchResults/getCourseDescription"

    payload = f"term={term}&courseReferenceNumber={course_id}"
    headers = {
        'Content-Type': "application/x-www-form-urlencoded; charset=UTF-8"
    }
    
    async with session.post(url_co_reqs, headers=headers, data=payload) as response:
        if response.status == 200:
            co_reqs_html = await response.text()
        else:
            co_reqs_html = None

    async with session.post(url_pre_reqs, headers=headers, data=payload) as response:
        if response.status == 200:
            pre_reqs_html = await response.text()
        else:
            pre_reqs_html = None

    async with session.post(url_course_desc, headers=headers, data=payload) as response:
        if response.status == 200:
            course_details_html = await response.text()
        else:
            course_details_html = None

    course['co_reqs_html'] = co_reqs_html
    course['pre_reqs_html'] = pre_reqs_html
    course['course_details_html'] = course_details_html

async def add_courses(page_offset: int, page_max_size: int, term: str, context: BrowserContext, running_data: list):
    url = f"https://ssb1-reg.banner.marist.edu/StudentRegistrationSsb/ssb/courseSearchResults/courseSearchResults?txt_term={term}&pageMaxSize={page_max_size}&pageOffset={page_offset}"

    page = await context.new_page()
    await page.goto(url)
    content = await page.content()
    content = content[content.find("{"):content.rfind("}")+1]
    try:
        content = json.loads(content)
    except json.decoder.JSONDecodeError as e:
        print(e)
        char_position = int(str(e).split("char ")[-1][:-1])
        print(content[char_position-50:char_position+50])
        return
    
    running_data = running_data.extend(content.get('data'))

    await page.close()


# Scrapes from the most recent
# Still need to get a cookie from the server
async def scrape_latest_term():
    url = "https://ssb1-reg.banner.marist.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=courseSearch"
    count_per_page = 500 
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False) 
        context = await browser.new_context()
        page = await context.new_page()

        # for some reason the term query field in the GET request is actually fake
        #   you must actually associate your cookie with the selected term
        #   I do this navigating to a term in the session then closing the page
        await page.goto(url)
        await page.click('div[id="s2id_txt_term"]') # term live search
        await page.click('li[role="presentation"]') # click on term
        await page.click('button[id="term-go"]') # go to term search
        await page.wait_for_load_state("domcontentloaded")
        await page.click('button[id="search-go"]') # search with no param for the term
        await page.wait_for_load_state("domcontentloaded")

        # first_course = await page.query_selector('.course-details-link')

        first_course = await page.wait_for_selector('.course-details-link')
        data_attributes = await first_course.get_attribute('data-attributes')
        term = data_attributes[:data_attributes.find(',')]
        total_sections_text: str = await page.locator('span[class="results-out-of"]').inner_text()
        sections_count: int = int(total_sections_text.split(" ")[0])
        await page.close()

        tasks = []
        running_data = []
        for i in range(math.ceil(sections_count / count_per_page)):
            tasks.append(add_courses(i, count_per_page, term, context, running_data))
        
        await asyncio.gather(*tasks)

    section_file_names = []
    
    for filename in os.listdir('./output'):
        if filename.startswith('sections'):
            section_file_names.append(f'./output/{filename}')
    

    if section_file_names:
        course_num_subject_to_reference = {}

        for section_file_name in section_file_names:
            with open(section_file_name) as file:
                data = json.load(file)
                for section in data:
                    refNum = section.get("courseReferenceNumber")
                    courseNum = section.get('courseNumber') 
                    subj = section.get('subject')
                    courseNum_subj = courseNum + subj
                    if not course_num_subject_to_reference.get(courseNum_subj):
                        course_num_subject_to_reference[courseNum_subj] = refNum 
        
        tasks = []
        async with aiohttp.ClientSession() as session:
            for course in running_data:
                courseNum = course.get("courseNumber")
                subj = course.get("subjectCode")
                refNum = course_num_subject_to_reference.get(courseNum + subj)
                if refNum:
                    tasks.append(add_more_course_info(course, refNum, term, session))
            
            await asyncio.gather(*tasks)

    if not os.path.exists('output'):
        os.mkdir('output')

    with open(f'output/courses{term}.json', 'w') as file:
        json.dump(running_data, file, indent=4)

if __name__ == '__main__':
    pass