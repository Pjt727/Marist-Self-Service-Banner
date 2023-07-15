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
- run the main file with arguments of the search parameter for the term you want (if it includes spaces it must be in quotes or it will be interpreted as two separate searches)
    - ex: python .\main.py "Spring 2023" "Fall 2023"
- It will will then generate csv's in the .\output\ folder