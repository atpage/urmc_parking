#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
import datetime as dt
import time

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, DateTime, Integer

#################################### Setup: ####################################

url = 'https://www.rochester.edu/parking/mobile/lots.php'
payload = {'campus': 'URMC'}

db_file = 'parking.db'

delay = 60*5  # seconds to wait between requests
timeout = 30  # how long to wait for page to load

################################## Database: ###################################

Base = declarative_base()

class OpenSpaces(Base):
    __tablename__ = 'open_spaces'
    id            = Column(Integer, primary_key=True)
    checked_gmt   = Column(DateTime, index=True)
    lot           = Column(String, index=True)
    spaces        = Column(Integer)
    # TODO?: different index setup

def get_engine():
    engine = create_engine('sqlite:///%s' % db_file)
    return engine

def get_session(engine=None):
    if not engine:
        engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    return session

################################## Functions: ##################################

def get_page():
    r = requests.get(url, params=payload, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError("failed to get %s" % url)
    return r.text

def parse_spaces(spaces):
    """convert a string like 'Open Spaces  315' into an integer like 315"""
    if 'Open Spaces' not in spaces:
        return 0
    # if 'full' in spaces.lower() or ' to ' in spaces:
    #     return 0
    nspaces = re.search(r'[\d]+', spaces)
    if nspaces is None:
        return 0
    return int(nspaces.group(0))

def get_current_status():
    lot_status = {}
    page_text = get_page()
    soup = BeautifulSoup(page_text, 'html.parser')
    parking_list_html = soup.find(id="parking-list")
    for lot in parking_list_html.find_all("tr"):
        columns = lot.find_all("td")
        if len(columns) != 2:
            raise RuntimeError("page not formatted as expected")
        lot, spaces = [c.get_text().strip() for c in columns]
        spaces = parse_spaces(spaces)
        lot_status[lot] = spaces
    return lot_status

#################################### main: #####################################

def main_loop(session):
    while True:
        time.sleep(delay)
        try:
            status = get_current_status()
        except:
            print("failed to get lot status at %s" % dt.datetime.now())
            continue
        checked_time = dt.datetime.utcnow()  # TODO?: look at response header for time too/instead
        for lot in status:
            row = OpenSpaces(
                checked_gmt = checked_time,
                lot         = lot,
                spaces      = status[lot],
            )
            session.add(row)
        session.commit()

if __name__ == '__main__':
    # set up connection:
    engine = get_engine()
    session = get_session(engine)
    # create tables:
    Base.metadata.create_all(engine)
    # watch the feed:
    main_loop(session)

################################################################################
