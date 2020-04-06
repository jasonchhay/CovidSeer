"""
WSGI config for coronaseer project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os

#Adam addition
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
#End Adam addition


from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'covidseer.settings.production')

application = get_wsgi_application()

#Adam addition test
#sys.path.append('/data/websites/covidseer/covidseer')
#sys.path.append('/data/websites/covidseer')
