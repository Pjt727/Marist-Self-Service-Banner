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
    instructor_email: str
    campus: str
    seat_status: str
    meeting_times: list[str]

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
    instructor_email = await instructor_selector.get_attribute("href") if instructor_selector else None

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


    section_tr: SectionTr = SectionTr(tr, course_title=course_title, subject=subject, course_number=course_number, section=section, instructor=instructor, instructor_email=instructor_email, campus=campus, seat_status=seat_status, meeting_times=meeting_times)

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
    header_row: list[str] = ["course_title", "subject", "number", "co_requisites", "prerequisites", "college", "department", "credit_hours", "id"]
    def __init__(self, course_title: str, subject: str, number: str, co_requisites: str, prerequisites: str, college: str, department: str, credit_hours: str) -> None:
        try:
            self.course_title = course_title.replace('"', "").split("\n")[0]
        except ValueError:
            self.course_title = course_title
        self.subject = subject
        self.number = number
        self.co_requisites = co_requisites
        self.prerequisites = prerequisites
        self.college = college
        self.department = department
        self.credit_hours = credit_hours
        
        self.id = Course.next_id
        Course.courses[self.subject + self.number] = self.id
        Course.next_id += 1

        
    def get_course(subject: str, number: str) -> int:
        return Course.courses.get(subject+number,None)

    def to_csv(self) -> list[str]:
        return [getattr(self, attr) for attr in Course.header_row]


async def create_course(section_tr: SectionTr, page: Page, courses: list[Course]) -> int:
    tr = section_tr.tr
    details_link: ElementHandle = await tr.wait_for_selector('a[class="section-details-link"]', timeout=2000)
    await details_link.click()
    details_container = await page.wait_for_selector('div[id="classDetailsContentDetailsDiv"]', timeout=2000)
    
    # Get co reqs, pre reqs and catalog info from a new course
    co_reqs_a = await page.wait_for_selector('h3[id="coReqs"]')
    await co_reqs_a.click()
    co_requisites_container = await details_container.wait_for_selector('section[aria-labelledby="coReqs"]', timeout=2000)
    co_requisites = await requisite_parser(co_requisites_container)

    pre_reqs_a = await page.wait_for_selector('h3[id="preReqs"]', timeout=2000)
    await pre_reqs_a.click()
    prerequisites_container = await details_container.wait_for_selector('section[aria-labelledby="preReqs"]', timeout=2000)
    prerequisites = await requisite_parser(prerequisites_container)
    catalog_a = await page.wait_for_selector('h3[id="catalog"]', timeout=2000)
    await catalog_a.click()
    catalog_container = await details_container.wait_for_selector('section[aria-labelledby="catalog"]', timeout=2000)
    college, department, credit_hours = await catalog_parser(catalog_container)

    # hit the close button
    close_button = await page.query_selector('button[class="primary-button small-button"]')
    await close_button.click()

    # in case a different async task finished it while it was working
    existing_course_id = Course.get_course(section_tr.subject, section_tr.course_number)
    if existing_course_id: return existing_course_id

    c = Course(course_title=section_tr.course_title, 
               subject=section_tr.subject, 
               number=section_tr.course_number, 
               co_requisites=co_requisites, 
               prerequisites=prerequisites, 
               college=college, 
               department=department, 
               credit_hours=credit_hours
               )
    courses.append(c)
    return c.id




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
    header_row = ["section", "instructor", "instructor_email", "meeting_times", "taught_how", "campus", "seat_cap", "course_id"]
    def __init__(self, section_tr: SectionTr, course_id: int) -> None:
        self.section: str = section_tr.section
        self.instructor: str = section_tr.instructor
        try:
            self.taught_how = section_tr.course_title.replace('"', "").split("\n", 1)[1]
        except IndexError:
            self.taught_how = None

        try:
            self.meeting_times: list[str] = meeting_times_parser(section_tr.meeting_times)
        except ValueError:
            self.meeting_times = None

        if section_tr.instructor_email:
            try:
                self.instructor_email = section_tr.instructor_email[section_tr.instructor_email.find(":") + 1:]
            except IndexError:
                self.instructor_email = None
        else:
            self.instructor_email = None
        
        self.campus: str = section_tr.campus
        self.seat_cap: int = seat_cap_parser(section_tr.seat_status)

        self.course_id: int = course_id


    def to_csv(self) -> list[str]:
        return [getattr(self, attr) for attr in Section.header_row]
