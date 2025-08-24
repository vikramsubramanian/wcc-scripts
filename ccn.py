from dotenv import load_dotenv
load_dotenv()
from time import sleep
import csv
import os
import logging
import requests
from config import CCN as config

logger = logging.getLogger(__name__)
cookies = None

def login():
    """ Log in to CCN's REST API and retrieves a session cookie """
    global cookies

    url = config['url']['login']
    data = {
        "username": config['credentials']['username'],
        "password": config['credentials']['password']
    }

    r = requests.post(url, data=data)

    if r.status_code != 200:
        msg = f"Could not establish CCN session. Returned status: {r.status_code}"
        logger.error(msg)
        raise Exception(msg)

    cookies = r.cookies


def check_report():
    """
    Download the reports status JSON object from CCN
    Returns a dict with values from the membership report type
    """
    global cookies

    # Get report types and links
    url = config['url']['reports']
    res = requests.get(url, cookies=cookies)

    # make sure we get a response
    if res.status_code != 200:
        msg = f"Error updating report. {res.status_code}: {res.text}"
        logger.error(msg)
        raise Exception(msg)

    # parse the json response
    data = res.json()

    # Iterate through the report types and isolate the membership report we're looking for
    report_types = [x['report_types'] for x in data['report_type_groups'] if x['name'] == 'Registration Reports'][0]
    membership_report = [x for x in report_types if x['name'] == config['membership-report']][0]

    return membership_report


def download_report():
    """
    Downloads the CSV report from CCN
    """
    global cookies

    # initial status check on report generation
    report = check_report()

    # check the report status and update if needed
    if report['last_report']['is_beeing_generated'] == False:
        url = config['hostname'] + report['update_link']
        res = requests.get(url, cookies=cookies)
        logger.info(f"Updating Report: {config['membership-report']}")
        print('\rWaiting [{0}]'.format('#'), end="")
        sleep(5)

    report = check_report()
    count = 5
    # keep checking every 5 seconds
    while report['last_report']['is_beeing_generated'] == True:
        if count >= config['report-timeout']:
            logger.error(f"Script timed out waiting for report to generate. ({count} seconds)")
            exit(1)

        count += 5
        print('\rWaiting [{0}]'.format('#' * int(count/5)), end="")
        sleep(5)
        report = check_report()

    # find the report download URL
    report_url = report['last_report']['report_files'][1]['url']
    logger.info("Report Updated.")
    logger.info("Downloading CSV.")
    logger.info(report_url)

    # download the CSV report
    res = requests.get(report_url)
    with open('members_temp.csv', 'wb') as file:
        file.write(res.content)

    logger.info("Download complete.")


def process_file(src, dest, delete=False):
    members = []
    # open members file
    with open(src, newline='') as src_file:
        reader = csv.reader(src_file)
        members.extend(reader)

    # Gather all email addresses
    emails = [x[8].lower() for idx, x in enumerate(members) if len(x) > 2 and idx > 0 and x[8]]

    # Reformat and trim records
    records = []
    for index, row in enumerate(members):
        # Skip headers and extra footer data
        if index == 0 or len(row) < 2:
            continue

        email = row[8].lower()
        dubs = False
        # check for dupe emails
        if emails.count(email) > 1:
            dubs = True

        # Pull out our desired fields
        records.append({
            'first': row[6],
            'last': row[7],
            'email': row[8].lower(),
            'sex': row[9],
            'dubs': dubs,
        })

    logging.info("Creating trimmed membership.")

    # Write records to file
    with open(dest, 'w') as dest_file:
        # create the csv writer
        writer = csv.writer(dest_file)
        # Write field headers in CSV file
        writer.writerow([
            'first',
            'last',
            'email',
            'sex',
            'dubs'
        ])
        # write remaining records
        for index, row in enumerate(records):
            writer.writerow(row.values())

    # Delete source file if delete is true
    if delete:
        logging.info("Deleting original membership file.")
        os.remove(src)


def main():
    """ Running the module directly just downloads the report """
    logging.basicConfig(filename='ccn.log', filemode='a', format='%(asctime)s %(name)s - %(levelname)s - %(message)s')
    logging.getLogger().addHandler(logging.StreamHandler())
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    login()
    download_report()
    process_file('members_temp.csv', 'members.csv', delete=True)
