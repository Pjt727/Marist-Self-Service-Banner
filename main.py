import os
from playwright.sync_api import sync_playwright
import csv
from playwright.sync_api import ElementHandle, TimeoutError, Error, Playwright, Page
from sanitizingClasses import Course, Section
import pandas as pd
from sanitizingClasses import Course, Section, SectionTr


def nav_to_search(page: Page) -> None:
    # selecting to go through 50 sections at a time
    page.click('button[id="search-go"]') # search with no param for the term
    page.wait_for_load_state() # for the load
    page.locator('select[class="page-size-select"]').select_option('50')
    page.wait_for_selector('select[aria-label="50 per page"]')


def select_page(page: Page, page_number: int):
    page_number_element = page.locator('input[title="Page"]')
    page_number_element.fill(str(page_number))
    page_number_element.press('Enter')



def load_data(out_path: str, start_fresh: bool) -> None:
    try:
        os.makedirs(out_path)
        course_headers_df = pd.DataFrame(columns=Course.header_row)
        section_headers_df = pd.DataFrame(columns=Section.header_row)

        course_headers_df.to_csv(f"{out_path}/courses.csv", header=True, index=False)
        section_headers_df.to_csv(f"{out_path}/sections.csv", header=True, index=False)
    except FileExistsError:
        if start_fresh:
            course_headers_df = pd.DataFrame(columns=Course.header_row)
            section_headers_df = pd.DataFrame(columns=Section.header_row)
            course_headers_df.to_csv(f"{out_path}/courses.csv", header=False, index=False)
            section_headers_df.to_csv(f"{out_path}/sections.csv", header=False, index=False)
        else:
            courses_df = pd.read_csv(f"{out_path}/courses.csv", usecols=["subject", "number", "id"])
            for _, row in courses_df.iterrows():
                Course.next_id += 1
                Course.courses[row['subject'] + row['number']] = int(row['id'])

            sections_df = pd.read_csv(f"{out_path}/sections.csv", usecols=['data_id'])
            for _, row in sections_df.iterrows():
                Section.sections.add(int(row['data_id']))


def add_trs(page: Page, out_path: str) -> int:
    courses: list[Course] = []
    sections: list[Section] = []
    bad_course_count = 0
    sections_tr = page.locator('tr[data-id]').all()
    fatal_error = False
    for tr in sections_tr:
        try:
            section_tr = SectionTr(tr.element_handle())
            if int(section_tr.tr_data_id) in Section.sections: continue
            course_id = Course.get_course(section_tr.subject, section_tr.course_number)
            if course_id is not None:
                sections.append(Section(section_tr=section_tr, course_id=course_id))
                continue
            new_course = Course(section_tr=section_tr)
            courses.append(new_course)
            new_course.add_catalog_info(tr=tr.element_handle(), page=page)
            sections.append(Section(section_tr=section_tr, course_id=new_course.id))
        except TimeoutError as exc:
            print(exc)
            print("ERROR: ", section_tr.tr_data_id)
            bad_course_count += 1
            continue
        except Exception as exc:
            print(exc)
            fatal_error = True
            break

    # writing to csv
    courses_df = pd.DataFrame(map(Course.to_csv, courses))
    sections_df = pd.DataFrame(map(Section.to_csv, sections))
    courses_df.to_csv(f"{out_path}/courses.csv", mode='a', header=False, index=False)
    sections_df.to_csv(f"{out_path}/sections.csv", mode='a', header=False, index=False)
    return -1 if fatal_error else bad_course_count 


def run(playwright: Playwright, start_fresh=False):
    term: str = "Fall 2023"
    out_path = f"./output/{term.replace(' ', '')}"
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    # load existing data
    load_data(out_path=out_path, start_fresh=start_fresh)

    # getting to the first search page
    page.goto('https://ssb1-reg.banner.marist.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search')
    page.click('div[id="s2id_txt_term"]') # term live search
    term_lookup = page.locator('input[id="s2id_autogen1_search"]') # term text input
    term_lookup.fill(term) # fill with therm
    page.click('li[role="presentation"]') # click on term
    page.click('button[id="term-go"]') # go to term search
    page.wait_for_load_state("networkidle") # wait for nav to next page
    

    nav_to_search(page)

    
    bad_course_count = 0
    current_page = 1
    last_page = int(page.wait_for_selector('span[class="paging-text total-pages"]').inner_text())
    print(last_page)
    
    # goes until it finishes all pages of the meetings
    while(True):
        print(current_page)
        bad_count = add_trs(page=page, out_path=out_path)
        if bad_count == -1: # there was a fatal error
            page.reload()
            page.wait_for_load_state('networkidle')
            nav_to_search(page)
            select_page(page, current_page)
            continue
        bad_course_count += bad_count
        current_page += 1
        if (current_page > last_page): break
        next_button = page.wait_for_selector('button[title="Next"]')
        next_button.click()
        
        
    browser.close()

    print("bad count", bad_course_count)


def scrape_degree_works():
    with sync_playwright() as playwright:
        run(playwright)


if __name__ == "__main__":
    scrape_degree_works()
