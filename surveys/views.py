from django.shortcuts import render, get_object_or_404, redirect
from .models import Survey, Question, Choice, Response, Answer


def home(request):
    surveys = Survey.objects.filter(is_active=True).prefetch_related('questions').order_by('-created_at')
    return render(request, 'surveys/home.html', {'surveys': surveys})


def survey_detail(request, pk):
    survey = get_object_or_404(Survey, pk=pk, is_active=True)
    questions = survey.questions.prefetch_related('choices').all()
    return render(request, 'surveys/survey_detail.html', {'survey': survey, 'questions': questions})


def survey_submit(request, pk):
    if request.method != 'POST':
        return redirect('surveys:survey_detail', pk=pk)

    survey = get_object_or_404(Survey, pk=pk, is_active=True)
    response = Response.objects.create(survey=survey)

    for question in survey.questions.prefetch_related('choices').all():
        field_name = f'question_{question.pk}'

        if question.question_type == Question.TEXT:
            text_answer = request.POST.get(field_name, '').strip()
            Answer.objects.create(response=response, question=question, text_answer=text_answer)

        elif question.question_type == Question.MULTIPLE_CHOICE:
            choice_id = request.POST.get(field_name)
            choice = None
            if choice_id:
                try:
                    choice = question.choices.get(pk=choice_id)
                except Choice.DoesNotExist:
                    pass
            Answer.objects.create(response=response, question=question, choice=choice)

        elif question.question_type == Question.RATING:
            rating = request.POST.get(field_name, '').strip()
            Answer.objects.create(response=response, question=question, text_answer=rating)

        elif question.question_type == Question.YES_NO:
            value = request.POST.get(field_name, '').strip()
            text_answer = 'Yes' if value == 'yes' else 'No' if value == 'no' else ''
            Answer.objects.create(response=response, question=question, text_answer=text_answer)

    return redirect('surveys:thank_you', pk=pk)


def thank_you(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    return render(request, 'surveys/thank_you.html', {'survey': survey})


def services(request):
    return render(request, 'surveys/services.html', {})
