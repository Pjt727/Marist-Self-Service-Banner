from dataclasses import dataclass
from playwright.async_api import ElementHandle, Page

@dataclass
class SectionTr:
    tr: ElementHandle
    course_title: str
    subject: str 
    course_number: str
    section: str
    instructor: str
    campus: str
    seat_status: str
    meeting_times: list[str]
    tr_data_id: str

async def create_section_tr(tr: ElementHandle) -> SectionTr:
    tr = await tr

    course_title_selector: ElementHandle = await tr.query_selector('td[xe-field="courseTitle"]')
    course_title = await course_title_selector.inner_text()

    subject_selector: ElementHandle = await tr.query_selector('td[xe-field="subject"]')
    subject = await subject_selector.inner_text()

    course_number_selector: ElementHandle = await tr.query_selector('td[xe-field="courseNumber"]')
    course_number = await course_number_selector.inner_text()

    section_selector: ElementHandle = await tr.query_selector('td[xe-field="sequenceNumber"]')
    section = await section_selector.inner_text()

    instructor_selector: ElementHandle = await tr.query_selector('td[xe-field="instructor"] a.email')
    instructor = await instructor_selector.inner_text() if instructor_selector else None

    campus_selector: ElementHandle = await tr.query_selector('td[xe-field="campus"]')
    campus = await campus_selector.inner_text() if campus_selector else None

    seat_status_selector: ElementHandle = await tr.query_selector('td[xe-field="status"]')
    seat_status = await seat_status_selector.inner_text() if seat_status_selector else None


    meeting_time_td = await tr.query_selector('td[xe-field="meetingTime"]')
    meeting_times: list[str] = []
    if meeting_time_td:
        for meeting in await meeting_time_td.query_selector_all('div[class="meeting"]'):
            text = await meeting.inner_text()
            text = text[:text.find("\n")] + text[text.rfind("\n"):]
            meeting_times.append(text)

    tr_data_id: str = await tr.get_attribute('data-id')

    section_tr: SectionTr = SectionTr(tr, course_title=course_title, subject=subject, course_number=course_number, section=section, instructor=instructor, campus=campus, seat_status=seat_status, meeting_times=meeting_times, tr_data_id=tr_data_id)

    return section_tr


async def requisite_parser(requisite_container: ElementHandle) -> list[list[str]]:
    requisites_table = await requisite_container.query_selector('table')
    if not requisites_table:
        return None
    
    co_requisites: list[list[str]] = []
    for row in await requisites_table.query_selector_all('tr'):
        row_list: list[str] = []
        for cell in await row.query_selector_all('td,th'):
            row_list.append(await cell.inner_text())
        co_requisites.append(row_list)
    return co_requisites

async def catalog_parser(catalog_container: ElementHandle) -> tuple[str]:
    catalog_text: str = await catalog_container.inner_text()
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
        try:
            self.course_title, self.taught_how = section_tr.course_title.replace('"', "").split("\n")
        except ValueError:
            print("\n\n\n\n",section_tr.course_title,"\n\n\n\n")
            raise(ValueError(section_tr.course_title))
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
    async def add_catalog_info(self, tr: ElementHandle, page: Page) -> None:
        details_link: ElementHandle = await tr.wait_for_selector('a[class="section-details-link"]', timeout=2000)
        await details_link.click()
        details_container = await page.wait_for_selector('div[id="classDetailsContentDetailsDiv"]', timeout=2000)
        
        # Get co reqs, pre reqs and catalog info from a new course
        co_reqs_a = await page.wait_for_selector('h3[id="coReqs"]')
        await co_reqs_a.click()
        co_requisites_container = await details_container.wait_for_selector('section[aria-labelledby="coReqs"]', timeout=2000)
        self.co_requisites = await requisite_parser(co_requisites_container)

        pre_reqs_a = await page.wait_for_selector('h3[id="preReqs"]', timeout=2000)
        await pre_reqs_a.click()
        prerequisites_container = await details_container.wait_for_selector('section[aria-labelledby="preReqs"]', timeout=2000)
        self.prerequisites = await requisite_parser(prerequisites_container)
        catalog_a = await page.wait_for_selector('h3[id="catalog"]', timeout=2000)
        await catalog_a.click()
        catalog_container = await details_container.wait_for_selector('section[aria-labelledby="catalog"]', timeout=2000)
        self.college, self.department, self.credit_hours = await catalog_parser(catalog_container)

        # hit the close button
        close_button = await page.query_selector('button[class="primary-button small-button"]')
        await close_button.click()

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

    
