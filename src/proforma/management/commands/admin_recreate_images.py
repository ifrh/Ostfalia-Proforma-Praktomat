from django.core.management.base import BaseCommand
from tasks.models import Task
from checker.checker import PythonUnittestChecker
import os
from django.conf import settings
import proforma


# intern call:
# python manage-docker.py admin_recreate_images
# external call:
# docker exec -u root -it praktomat3 python3 src/manage-docker.py admin_recreate_images

class Command(BaseCommand):
    help = 'Recreate sandbox images (should be executed after sandbox Dockerfile changes)'

    def handle(self, *args, **kwargs):
        proforma.sandbox.cleanup()
        proforma.sandbox.admin_delete_sandbox_images()
        proforma.sandbox.create_images()

        # get all tasks with programming language 'python'
        tasks = Task.objects.filter(prog_lang='python')
        if len(tasks) == 0:
            print('no python tasks available => fínished')
            return

        checkers = PythonUnittestChecker.PythonUnittestChecker.objects.all()
        for checker in checkers:
            requirements_txt = checker.files.filter(filename='requirements.txt', path='')
            if len(requirements_txt) != 0:
                print(checker.id)
                print('requirements.txt gefunden for task ' + str(checker.task.id))
                requirements_txt = requirements_txt.first()

                requirements_path = os.path.join(settings.UPLOAD_ROOT,
                                                 proforma.task.get_storage_path(requirements_txt, requirements_txt.filename))

                image = proforma.sandbox.PythonImage(checker, requirements_path)
                print('data: create sandbox image for python unit test')

                a = image.create_image_yield()
                # 'consume' a, needed because create_image_yield is a generator which returns an iterator
                # This is required, otherwise the function is not completely executed
                b = list(a)

