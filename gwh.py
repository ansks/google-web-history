'''Google Web History
export google web search history to CSV

Usage:
    python gwh.py outfile email passwd [code]

    where `code` is used for second factor authentication.
'''

import datetime
import re
import sys

import mechanize
from bs4 import BeautifulSoup


def select_form(browser, form_id):
    '''With a mechanize browser, selects a form based on id'''
    for form in browser.forms():
        if form.attrs.get('id') == form_id:
            browser.form = form
            break

def descend(node, path):
    '''Traverse a beautifulsoup node downwards according to
    a specific path.
    descend(node, [0, 1]) => node.contents[0].contents[1]
    '''
    for i in path:
        if len(node.contents) <= i:
            return None
        node = node.contents[i]
    return node

def authenticate(browser, email, passwd, code=None):
    '''Authenticate a google user based on the supplied credentials'''
    attempt_first_factor(browser, email, passwd)
    if failed_first_factor(browser):
        sys.exit("Incorrect email and password combination")
    if requires_second_factor(browser):
        attempt_second_factor(browser, code)
        if failed_second_factor(browser):
            sys.exit("Second factor failed")
    return True

def attempt_first_factor(browser, email, passwd):
    '''Attempt a email/password challange'''
    response = browser.open('https://history.google.com')
    select_form(browser, 'gaia_loginform')
    browser['Email'] = email
    browser['Passwd'] = passwd
    return browser.submit()

def attempt_second_factor(browser, code):
    '''Attempt to second factor authentication code challenge'''
    select_form(browser, 'gaia_secondfactorform')
    browser['smsUserPin'] = code
    return browser.submit()

def requires_second_factor(browser):
    '''Check to see if second factor authentication'''
    return 'SecondFactor' in browser.response().geturl()

def failed_first_factor(browser):
    '''Check to see if first factor authentication was unsuccessful'''
    return 'ServiceLoginAuth' in browser.response().geturl()

def failed_second_factor(browser):
    '''Check to see if second factor authentication was unsuccessful'''
    return 'SecondFactor' in browser.response().geturl()

def parse_time(time):
    '''Convert a time from "3:36pm" to "15:36"'''
    pm = time[-2:] == 'pm'
    time = time[:-2].split(':')
    hours = int(time[0])
    mins = int(time[1])
    if pm:
        hours += 12
    return '{:02d}:{:02d}'.format(hours, mins)

def parse_date(date):
    '''Convert a date from "14 Jan" or "14 Jan, 2013" to :2013-01-14"'''
    if date == 'Today':
        return datetime.date.today().isoformat()
    elif date == 'Yesterday':
        yesterday = datetime.date.today() - datetime.timedelta(1)
        return yesterday.isoformat()
    else:
        date = date.replace(' ', '')
        date = date.split(',')
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month = months.index(date[0][:3]) + 1
        day = int(date[0][3:])
        year = datetime.date.today().year
        if len(date) == 2:
            year = int(date[1])
        return datetime.date(day=day, month=month, year=year).isoformat()

def get_page(browser, url, history):
    '''Get all searches from a page and return the URL to the next page.'''
    response = browser.open(url)
    soup = BeautifulSoup(response.read())
    search_date = parse_date('Today')
    for search in soup.find_all('br')[2].children:
        if search.name != 'div':
            # Contains nothing useful
            continue
        if len(search.contents) > 0 and search.contents[0].name == 'h1':
            # This div contains the date
            search_date = parse_date(search.contents[0].text)
        elif search.attrs.get('id', '').startswith('div'):
            # This div contains search term and search time
            search_term_node = descend(search, [0,0,0,0,1,1,0])
            search_time_node = descend(search, [0,0,0,0,1,4])
            if search_term_node is None or search_time_node is None:
                continue
            search_term = search_term_node.text
            search_time = parse_time(search_time_node.text)
            history.append([search_date, search_time, search_term])

    # Determine the URL for the next page, if there is a next page
    buttons = soup.find_all('a', attrs={'class': 'kd-button'})
    for button in buttons:
        if button.text == 'Older':
            return button.attrs.get('href')

def get_history(email, passwd, code=None):
    '''Get the google search history for a user.'''
    browser = mechanize.Browser()
    browser.set_handle_robots(False)
    if authenticate(browser, email, passwd, code):
        history = []
        next_url = 'https://history.google.com?num=1000'
        while next_url is not None:
            next_url = get_page(browser, next_url, history)
        return history


if __name__ == '__main__':
    argc = len(sys.argv)
    if argc < 4 or argc > 5:
        sys.exit('Usage: python gwh.py outfile email passwd [code]')

    outfile = sys.argv[1]
    email = sys.argv[2]
    passwd = sys.argv[3]
    code = None
    if argc == 5:
        code = sys.argv[4]

    history = get_history(email, passwd, code)
    with open(outfile, 'w') as f:
        for search in history:
            line = u','.join(search).encode('ascii', 'ignore')
            f.write('{}\n'.format(line))
    print('{} records written to {}'.format(len(history), outfile))

