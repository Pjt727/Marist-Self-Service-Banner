# Marist-Self-Service-Banner
Web scraper for courses on Marist self-service

## Notes
- Data is admittedly over fit to my needs for another project
    - if more data is needed or specific data should be 
- Gets information on all courses and sections for a given term
    - Sections
        - section,instructor,meeting_times,campus,seat_cap,data_id, course_id
    - Courses
        - course_title,taught_how,subject,number,co_requisites,prerequisites,college,department,credit_hours,id
- For some reason there is occasionally some sections that do not get input (can rerun the program to minimize this)
- Dependencies (requirements.txt):
    - pandas
    - playwright