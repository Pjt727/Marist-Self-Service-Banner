# Marist-Self-Service-Banner
Web scraper for courses on Marist self-service

## Notes
- Data is admittedly over fit to my needs for another project
- Gets the following information on all courses and sections
    - Sections csv header
        - "section", "instructor", "instructor_email", "meeting_times", "taught_how", "campus", "seat_cap", "course_id"
    - Courses csv header
        - "course_title", "subject", "number", "co_requisites", "prerequisites", "college", "department", "credit_hours", "id"
- Dependencies (requirements.txt)

## How to Run
- Set up an environment
- Install the dependencies
- run the main file with arguments of the search parameter for the term you want (if it includes spaces it must be in quotes or it will be interpreted as two separate searches)
    - ex: python .\main.py "Spring 2023" "Fall 2023"
- It will will then generate csv's in the .\output\ folder