# Settings for deployment

# These settings are KIT-specific and derive some parts of the settings
# from the directory name.
#
# If you are not deploying on praktomat.cs.kit.edu you need to rewrite this file.

from os.path import join, dirname, basename
import os

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
STATIC_URL = BASE_PATH + 'static/'

STATIC_ROOT = join(dirname(PRAKTOMAT_PATH), "static")

TEST_MAXLOGSIZE=512

TEST_MAXFILESIZE=512

TEST_TIMEOUT=180


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

DEBUG = MIRROR

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

# Enable Shibboleth:
SHIB_ENABLED = True
REGISTRATION_POSSIBLE = False

SYSADMIN_MOTD_URL = "https://praktomat.cs.kit.edu/sysadmin_motd.html"

# Use a dedicated user to test submissions
USEPRAKTOMATTESTER = False

# Use docker to test submission
USESAFEDOCKER = True

# Various extra files and versions
CHECKSTYLEALLJAR = '/srv/praktomat/contrib/checkstyle-5.7-all.jar'
JPLAGJAR = '/srv/praktomat/contrib/jplag.jar'
#JAVA_BINARY = 'javac-sun-1.7'
#JVM = 'java-sun-1.7'

# Our VM has 4 cores, so lets try to use them
NUMBER_OF_TASKS_TO_BE_CHECKED_IN_PARALLEL = 6
# But not with Isabelle, which is memory bound

# Finally load defaults for missing settings.
from . import defaults
defaults.load_defaults(globals())
