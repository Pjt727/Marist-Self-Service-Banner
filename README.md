# Marist-Self-Service-Banner
Web scraper for courses on Marist self-service

## Notes
- changed from scraping the HTML on the page to getting the JSON data
    - considerably faster
- Steps taken to scrape a term:
    - playwright opens an instance of chromium
    - associates the session cookie with a given term (done bc term query field does not work)
    - opens n pages at once loading the max (500) sections each to load all concurrently
    - dumps all json data to a file

## How to Run
- Set up an environment
- Install the dependencies
- To scrape sections for a given term input the search for the term
    - ex: python .\main.py sections "Spring 2023" "Fall 2023"
- To scrape courses for the latest term
    - Will take from scraped sections to get course reference number for details
    - python .\main.py courses
- It will will then generate json's in the .\output\ folder