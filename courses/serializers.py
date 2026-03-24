# courses/serializers.py
from rest_framework import serializers
from .models import Course, Module, ModuleProgress, CourseProgress

class ModuleSerializer(serializers.ModelSerializer):
    # Virtual fields for frontend
    contentTitle = serializers.SerializerMethodField()
    videoLabel = serializers.SerializerMethodField()
    quizzes = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'title', 'contentTitle', 'content', 'videoLabel', 'quiz', 'quizzes']

    @staticmethod
    def _normalize_correct_answers(quiz_item):
        if not isinstance(quiz_item, dict):
            raise serializers.ValidationError('Each quiz entry must be an object.')

        has_single = 'correctIndex' in quiz_item and quiz_item.get('correctIndex') is not None
        has_multi = 'correctIndexes' in quiz_item and quiz_item.get('correctIndexes') is not None

        if not has_single and not has_multi:
            raise serializers.ValidationError('Each quiz entry must include correctIndex or correctIndexes.')

        if has_multi:
            correct_indexes = quiz_item.get('correctIndexes')
            if not isinstance(correct_indexes, list) or not correct_indexes:
                raise serializers.ValidationError('correctIndexes must be a non-empty list of integers.')
            if len(correct_indexes) > 3:
                raise serializers.ValidationError('A question can have at most 3 correct answers.')
            if not all(isinstance(index, int) and index >= 0 for index in correct_indexes):
                raise serializers.ValidationError('correctIndexes must contain non-negative integers only.')
        else:
            single_index = quiz_item.get('correctIndex')
            if not isinstance(single_index, int) or single_index < 0:
                raise serializers.ValidationError('correctIndex must be a non-negative integer.')
            correct_indexes = [single_index]

        unique_indexes = sorted(set(correct_indexes))
        if len(unique_indexes) != len(correct_indexes):
            raise serializers.ValidationError('correctIndexes cannot contain duplicate values.')

        if len(unique_indexes) == 1:
            quiz_item['correctIndex'] = unique_indexes[0]
        else:
            quiz_item.pop('correctIndex', None)
        quiz_item['correctIndexes'] = unique_indexes
        return quiz_item

    @classmethod
    def _normalize_quiz_payload(cls, value):
        if value in (None, ''):
            return []
        if isinstance(value, dict):
            return [cls._normalize_correct_answers(value)]
        if isinstance(value, list):
            normalized = []
            for quiz_item in value:
                normalized.append(cls._normalize_correct_answers(quiz_item))
            return normalized
        raise serializers.ValidationError('Quiz data must be an object or a list of objects.')

    def to_internal_value(self, data):
        mutable_data = data.copy()

        if 'quizzes' in mutable_data:
            mutable_data['quiz'] = mutable_data.get('quizzes')

        return super().to_internal_value(mutable_data)

    def validate_quiz(self, value):
        return self._normalize_quiz_payload(value)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        normalized_quizzes = self._normalize_quiz_payload(instance.quiz)
        representation['quizzes'] = normalized_quizzes
        representation['quiz'] = normalized_quizzes[0] if normalized_quizzes else None
        return representation

    def get_contentTitle(self, obj):
        return getattr(obj, 'contentTitle', 'Module Content')

    def get_videoLabel(self, obj):
        return getattr(obj, 'videoLabel', 'Watch Video')

    def get_quizzes(self, obj):
        return self._normalize_quiz_payload(obj.quiz)


class CourseSerializer(serializers.ModelSerializer):
    modules = ModuleSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'title', 'modules']

class ModuleProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleProgress
        fields = ['id', 'user', 'module', 'completed', 'completed_at']
        read_only_fields = ['id', 'user', 'completed_at']


class CourseProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseProgress
        fields = ['id', 'user', 'course', 'completed_modules', 'total_modules', 'progress', 'completed', 'updated_at']
        read_only_fields = ['id', 'user', 'updated_at']