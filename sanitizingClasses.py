from playwright.sync_api import ElementHandle
from playwright.sync_api import Page
from typing import Union
from functools import lru_cache

class SectionTr:
    def __init__(self, tr: ElementHandle) -> None:
        self.tr = tr
        # Locate the <td> elements
        course_title_td = tr.query_selector('td[xe-field="courseTitle"]')
        subject_td = tr.query_selector('td[xe-field="subject"]')
        course_number_td = tr.query_selector('td[xe-field="courseNumber"]')
        section_td = tr.query_selector('td[xe-field="sequenceNumber"]')
        instructor_td = tr.query_selector('td[xe-field="instructor"] a.email')
        meeting_time_td = tr.query_selector('td[xe-field="meetingTime"]')
        campus = tr.query_selector('td[xe-field="campus"]')
        seat_status_td = tr.query_selector('td[xe-field="status"]')
        attribute_td = tr.query_selector('td[xe-field="attribute"]')

        # Retrieve inner text from <td> elements
        self.course_title: str = course_title_td.inner_text()
        self.subject: str = subject_td.inner_text()
        self.course_number: str = course_number_td.inner_text()
        self.section: str = section_td.inner_text() if section_td else ''
        self.instructor: str = instructor_td.inner_text() if instructor_td else ''
        self.tr_data_id: str = tr.get_attribute('data-id')
        
        # slight reformatting of meeting_time
        self.meeting_times: list[str] = []
        if meeting_time_td:
            for meeting in meeting_time_td.query_selector_all('div[class="meeting"]'):
                text = meeting.inner_text()
                text = text[:text.find("\n")] + text[text.rfind("\n"):]
                self.meeting_times.append(text)
        
        self.campus: str = campus.inner_text()
        self.seat_status: str = seat_status_td.inner_text() if seat_status_td else ''
        self.attribute: str = attribute_td.inner_text() if attribute_td else ''

    def __repr__(self) -> str:
        return f"SectionTr(course_title={self.course_title}, subject={self.subject}, course_number={self.course_number}, section={self.section}, instructor={self.instructor}, meeting_times={self.meeting_times}, seat_status={self.seat_status}, attribute={self.attribute})"



def requisite_parser(requisite_container: ElementHandle) -> list[list[str]]:
    requisites_table = requisite_container.query_selector('table')
    if not requisites_table:
        return None
    
    co_requisites: list[list[str]] = []
    for row in requisites_table.query_selector_all('tr'):
        row_list: list[str] = []
        for cell in row.query_selector_all('td,th'):
            row_list.append(cell.inner_text())
        co_requisites.append(row_list)
    return co_requisites

def catalog_parser(catalog_container: ElementHandle) -> tuple[str]:
    catalog_text = catalog_container.inner_text()
    cutoff_index = catalog_text.find("Levels: ")
    # if no cutoff was found then search the whole text
    cutoff_index = len(catalog_text) if cutoff_index == -1 else cutoff_index
    catalog_text = catalog_text[:cutoff_index]

    # this has got to be one of the most convoluted ways to do this
    heading_values: dict[str, str] = {"College:": None, "Department:": None, "Credit Hours:": None,}
    for catalog_entry in catalog_text.split("\n"):
        for heading in heading_values.keys():
            if catalog_entry[:len(heading)] == heading:
                heading_values[heading] = catalog_entry[len(heading):].strip()
        if None not in heading_values.values(): break

    # even though .values() will likely keep order bc of how dictionaries work in python
    # I have it this way just to make it more explicit 
    return heading_values["College:"], heading_values["Department:"], heading_values["Credit Hours:"]


class Course:
    next_id = 1
    courses: dict[str, int] = {} # subject + course number, id
    header_row: list[str] = ["course_title", "taught_how", "subject", "number", "co_requisites", "prerequisites", "college", "department", "credit_hours", "id"]
    def __init__(self, section_tr: SectionTr) -> None:
        self.course_title, self.taught_how = section_tr.course_title.replace('"', "").split("\n")
        self.subject = section_tr.subject
        self.number = section_tr.course_number
        self.co_requisites = None
        self.prerequisites = None
        self.college = None
        self.department = None
        self.credit_hours = None
        self.id = Course.next_id

        Course.next_id += 1

        Course.courses[self.subject+self.number] = self.id
    
    def get_course(subject: str, number: str) -> int:
        return Course.courses.get(subject+number,None)
    
    # navigate to the catalog and get info
    def add_catalog_info(self, tr: ElementHandle, page: Page) -> None:
        details_link = tr.wait_for_selector('a[class="section-details-link"]')
        details_link.click()
        details_container = page.wait_for_selector('div[id="classDetailsContentDetailsDiv"]')
        
        # Get co reqs, pre reqs and catalog info from a new course
        page.wait_for_selector('h3[id="coReqs"]').click()
        co_requisites_container = details_container.wait_for_selector('section[aria-labelledby="coReqs"]')
        self.co_requisites = requisite_parser(co_requisites_container)

        page.wait_for_selector('h3[id="preReqs"]').click()
        prerequisites_container = details_container.wait_for_selector('section[aria-labelledby="preReqs"]')
        self.prerequisites = requisite_parser(prerequisites_container)
        page.wait_for_selector('h3[id="catalog"]').click()
        catalog_container = details_container.wait_for_selector('section[aria-labelledby="catalog"]')
        self.college, self.department, self.credit_hours = catalog_parser(catalog_container)

        # hit the close button
        page.wait_for_selector('button[class="primary-button small-button"]').click()

    def to_csv(self) -> list[str]:
        return [getattr(self, attr) for attr in Course.header_row]


def meeting_times_parser(meeting_times: list[str]) -> list[tuple[str]]:
    meeting_times_sanitized: list[tuple[str]] = []
    meeting_times_sanitized.append(("days", "start_time", "end_time", "meeting_type", "building", "room", "start_date", "end_date",))
    for meeting_time in meeting_times:
        try:
            days, left_over = meeting_time.split('\n', 1)
        except ValueError:
            days, left_over = meeting_time.split('SMTWTFS', 1)
        time_range, left_over = left_over.split('Type:', 1)
        start_time, end_time = map(str.strip, time_range.split(' - ', 1))
        meeting_type, left_over = left_over.split('Building:', 1)
        meeting_type = meeting_type.replace('\xa0', '').strip()
        building, left_over = left_over.split('Room:')
        building = building.strip()
        room, left_over = left_over.split('Start Date:')
        room = room.strip()
        start_date, left_over = left_over.split('End Date:')
        start_date = start_date.strip()
        end_date = left_over.strip()
        meeting_times_sanitized.append((days, start_time, end_time, meeting_type, building, room, start_date, end_date,))
        

    return meeting_times_sanitized


def seat_cap_parser(seat_status: str) -> int:
    seps = seat_status.split(" ")
    nums = []
    for sep in seps:
        try:
            nums.append(int(sep))
        except ValueError:
            pass
    return max(nums)


class Section:
    sections: set[str] = set()
    header_row = ["section", "instructor", "meeting_times", "campus", "seat_cap", "data_id", "course_id"]
    def __init__(self, section_tr: SectionTr, course_id: int) -> None:
        self.section: str = section_tr.section
        self.instructor: str = section_tr.instructor
        try:
            self.meeting_times: list[str] = meeting_times_parser(section_tr.meeting_times)
        except ValueError:
            self.meeting_times = None

        
        self.campus: str = section_tr.campus
        self.seat_cap: int = seat_cap_parser(section_tr.seat_status)

        self.course_id: int = course_id
        self.data_id: int = int(section_tr.tr_data_id)
        Section.sections.add(self.data_id)


    def to_csv(self) -> list[str]:
        return [getattr(self, attr) for attr in Section.header_row]

    
