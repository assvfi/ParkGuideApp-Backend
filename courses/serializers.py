# courses/serializers.py
from rest_framework import serializers
from .models import Course, Module

class ModuleSerializer(serializers.ModelSerializer):
    # Virtual fields for frontend
    contentTitle = serializers.SerializerMethodField()
    videoLabel = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'title', 'contentTitle', 'content', 'videoLabel', 'quiz']

    def get_contentTitle(self, obj):
        return getattr(obj, 'contentTitle', 'Module Content')

    def get_videoLabel(self, obj):
        return getattr(obj, 'videoLabel', 'Watch Video')


class CourseSerializer(serializers.ModelSerializer):
    modules = ModuleSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'title', 'modules']