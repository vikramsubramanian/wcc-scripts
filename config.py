import os

CCN = {
    'hostname': "https://ccnbikes.com",
    'credentials': {
        'username': os.environ.get('CCN_USER'),
        'password': os.environ.get('CCN_PASS'),
    },
    'url': {
        'login': "https://ccnbikes.com/rest/v2/users/login/",
        'session': "https://ccnbikes.com/rest/v2/users/session_user/",
        'reports': f"https://ccnbikes.com/rest/v2/report/report/report_dashboard_data/?access_level=view&object_id={os.environ['CCN_REPORT_ID']}&object_type=event",
    },
    'membership-report': 'Complete Registration w/ Membership Info',
    'report-timeout': 900,  # Seconds to wait for report
}
DISCOURSE = {
    'credentials': {
        'user': os.environ.get('DISCOURSE_USER'),
        'key': os.environ.get('DISCOURSE_KEY'),
    },
    'url': {
        'host': os.environ.get('DISCOURSE_HOST'),
    },
}
