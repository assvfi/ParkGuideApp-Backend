from django.db import models

class Course(models.Model):
    title = models.JSONField()

    def __str__(self):
        return self.title.get('en', 'Untitled Course')

class Module(models.Model):
    course = models.ForeignKey(Course, related_name='modules', on_delete=models.CASCADE)
    title = models.JSONField()
    content = models.JSONField(blank=True, null=True)
    quiz = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.title.get('en', 'Untitled Module')