# Settings for deployment

# These settings are KIT-specific and derive some parts of the settings
# from the directory name.
#
# If you are not deploying on praktomat.cs.kit.edu you need to rewrite this file.

from os.path import join, dirname, basename
import os
from collections import OrderedDict
import logging
import time

PRAKTOMAT_PATH = dirname(dirname(dirname(__file__)))

# The name that will be displayed on top of the page and in emails.
SITE_NAME = 'Praktomat'

# Identifie this Praktomat among multiple installation on one webserver
PRAKTOMAT_ID = 'default'



# The URL where this site is reachable. 'http://localhost:8000/' in case of the
# developmentserver.
BASE_HOST = 'http://localhost:8000'
BASE_PATH = '/'
ALLOWED_HOSTS = [ '*', ]

# URL to use when referring to static files.
# STATIC_URL = BASE_PATH + 'static/'

# STATIC_ROOT = "/praktomat/static"
#STATIC_ROOT = join(dirname(PRAKTOMAT_PATH), "static")

TEST_MAXLOGSIZE=64

TEST_MAXFILESIZE=1024

TEST_TIMEOUT=25


# Absolute path to the directory that shall hold all uploaded files as well as
# files created at runtime.

# Example: "/home/media/media.lawrence.com/"
UPLOAD_ROOT = join(dirname(dirname(dirname(__file__))), 'data')

ADMINS = [
  ('Praktomat', 'praktomat@ipd.info.uni-karlsruhe.de')
]

SERVER_EMAIL = 'praktomat@i44vm3.info.uni-karlsruhe.de'

MIRROR = True
if MIRROR:
    EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
    EMAIL_FILE_PATH = join(UPLOAD_ROOT, "sent-mails")
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = "localhost"
    EMAIL_PORT = 25

DEFAULT_FROM_EMAIL = "praktomat@ipd.info.uni-karlsruhe.de"

DEBUG = False # MIRROR

DATABASES = {
    # Running the Docker image
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASS'],
        'HOST': os.environ['DB_DOCKER_SERVICE'],
        'PORT': os.environ['DB_PORT']
        }
#    'default': {
#            'ENGINE': 'django.db.backends.postgresql_psycopg2',
#            'NAME':   PRAKTOMAT_ID,
#    }
}

# Private key used to sign uploded solution files in submission confirmation email
#PRIVATE_KEY = '/srv/praktomat/mailsign/signer_key.pem'
#CERTIFICATE = '/srv/praktomat/mailsign/signer.pem'

PRIVATE_KEY = join(dirname(dirname(dirname(__file__))), 'examples', 'certificates', 'privkey.pem')
CERTIFICATE = join(dirname(dirname(dirname(__file__))), 'examples', 'certificates', 'signer.pem')
SECRET_KEY = "not-so-secret"

SYSADMIN_MOTD_URL = "https://praktomat.cs.kit.edu/sysadmin_motd.html"

# Use a dedicated user to test submissions
USEPRAKTOMATTESTER = True

# Use docker to test submission
USESAFEDOCKER = False

# Various extra files and versions
CHECKSTYLEALLJAR = '/srv/praktomat/contrib/checkstyle-5.7-all.jar'
JPLAGJAR = '/srv/praktomat/contrib/jplag.jar'


JAVA_LIBS = {
    'junit5': '/praktomat/lib/junit-platform-console-standalone-1.6.1.jar',
    'junit3': '/praktomat/extra/junit-3.8.jar', # is not included
     # map junit4 and junit 4.10 to 4.12
     'junit4': '/praktomat/lib/junit-4.12.jar:/praktomat/lib/hamcrest-core-1.3.jar',
     'junit4.10': '/praktomat/lib/junit-4.12.jar:/praktomat/lib/hamcrest-core-1.3.jar',
     'junit4.12': '/praktomat/lib/junit-4.12.jar:/praktomat/lib/hamcrest-core-1.3.jar',
     'junit4.12-gruendel': '/praktomat/lib/junit-4.12.jar:/praktomat/extra/JUnit4AddOn.jar:/praktomat/lib/hamcrest-core-1.3.jar'}



DETAILED_UNITTEST_OUTPUT = True

JUNIT4_RUN_LISTENER = 'de.ostfalia.zell.praktomat.Junit4ProFormAListener'
JUNIT4_RUN_LISTENER_LIB = '/praktomat/extra/Junit4RunListener.jar'
JUNIT5_RUN_LISTENER = 'de.ostfalia.zell.praktomat.Junit5ProFormAListener'
JUNIT5_RUN_LISTENER_LIB = '/praktomat/extra/Junit5RunListener.jar'

# The checkstyle versions must be sorted in order to find the latest version =>
# therefore an OrderedDict must be used because in Python 3.5 the order is not defined!
# We currently use Python 3.5.
# list(settings.CHECKSTYLE_VER.keys())[-1] must return the last value!
CHECKSTYLE_VER = OrderedDict()
CHECKSTYLE_VER['check-6.2']  = '/praktomat/lib/checkstyle-8.23-all.jar'
CHECKSTYLE_VER['check-7.6']  = '/praktomat/lib/checkstyle-8.23-all.jar'
CHECKSTYLE_VER['check-8.23'] = '/praktomat/lib/checkstyle-8.23-all.jar'
CHECKSTYLE_VER['check-8.29'] = '/praktomat/lib/checkstyle-8.29-all.jar'
CHECKSTYLE_VER['check-10.1'] = '/praktomat/lib/checkstyle-10.1-all.jar'


# GIT_LOG_FORMAT = "--oneline" # short hash message
GIT_LOG_FORMAT = "--pretty=format:%H" # only full hash

JCFDUMP = 'jcf-dump'
SETLXJAR = '/praktomat/extra/setlX-2.7.jar'

#JAVA_BINARY = 'javac-sun-1.7'
#JVM = 'java-sun-1.7'




# Our VM has 4 cores, so lets try to use them
NUMBER_OF_TASKS_TO_BE_CHECKED_IN_PARALLEL = 6
# But not with Isabelle, which is memory bound

# Finally load defaults for missing settings.
from . import defaults
defaults.load_defaults(globals())

# add unknown mimetype for setlx because otherwise Kit praktomat
# does not know it and will try and store NULL into database
# which results in an exception
defaults.MIMETYPE_ADDITIONAL_EXTENSIONS.append(('text/x-stlx', '.stlx'))
defaults.MIMETYPE_ADDITIONAL_EXTENSIONS.append(('text/plain', '.csv'))



# logging formatter for profiling function runtime
class DurationFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = time.time()
    def formatTime(self, record, datefmt=None):
        now = record.created
        duration = now - self.start_time
        self.start_time = time.time()
        return format(duration * 1000, '.1f')

def formatterfactory(format):
    return DurationFormatter(format)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            # relative time for performance measuring for profiling
            # comment the following line out in order to have normal log output!!
            # '()': 'settings.docker.formatterfactory',
            # absolute timestamp
            'format': '%(asctime)6s %(relativeCreated)d [%(process)d] [%(levelname)s] %(module)s %(message)s',
}
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
#        'file': {
#            'level': 'INFO',
#            'class': 'logging.FileHandler',
#            'filename': os.path.join(PRAKTOMAT_PATH, 'debug.log'),
#            'formatter': 'verbose'
#        },
#        'error-file': {
#            'level': 'ERROR',
#            'class': 'logging.FileHandler',
#            'filename': os.path.join(PRAKTOMAT_PATH, 'error.log'),
#            'formatter': 'verbose'
#        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
    },
    'loggers': {
        'proforma': {
            'handlers': ['console'],
#            'level': 'INFO',  # change debug level as appropiate
            'level': 'DEBUG',  # change debug level as appropiate
            #'propagate': False,
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,  # keep 10 historical versions
        },
        'checker': {
            'handlers': ['console'],
#            'level': 'INFO',  # change debug level as appropiate
            'level': 'DEBUG',  # change debug level as appropiate
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,  # keep 10 historical versions
        },
        'tasks': {
            'handlers': ['console'],
#            'level': 'INFO',  # change debug level as appropiate
            'level': 'DEBUG',  # change debug level as appropiate
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,  # keep 10 historical versions
        },
        'utilities': {
            'handlers': ['console'],
#            'level': 'INFO',  # change debug level as appropiate
            'level': 'DEBUG',  # change debug level as appropiate
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,  # keep 10 historical versions
        },
        ## SQL:
#        'django': {
#            'handlers': ['console', 'error-file', 'file'],
#            'level': 'DEBUG',  # change debug level as appropiate
#            'maxBytes': 1024*1024*4,  # 15MB
#            'backupCount': 10,  # keep 10 historical versions
#        },
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',  # change debug level as appropiate
            'propagate': False,
            'maxBytes': 1024*1024*4,  # 15MB
            'backupCount': 10,  # keep 10 historical versions
        }
    }
}

