from django.test import TestCase, Client
from django.urls import reverse
from .models import Survey, Question, Choice, Response, Answer


class SurveyModelTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(title='Test Survey', description='A test survey')
        self.text_q = Question.objects.create(
            survey=self.survey, text='What is your name?', question_type=Question.TEXT, order=1
        )
        self.mc_q = Question.objects.create(
            survey=self.survey, text='Pick one', question_type=Question.MULTIPLE_CHOICE, order=2
        )
        self.choice_a = Choice.objects.create(question=self.mc_q, text='Option A')
        self.choice_b = Choice.objects.create(question=self.mc_q, text='Option B')
        self.rating_q = Question.objects.create(
            survey=self.survey, text='Rate this', question_type=Question.RATING, order=3
        )
        self.yesno_q = Question.objects.create(
            survey=self.survey, text='Do you agree?', question_type=Question.YES_NO, order=4
        )

    def test_survey_str(self):
        self.assertEqual(str(self.survey), 'Test Survey')

    def test_question_str(self):
        self.assertIn('Test Survey', str(self.text_q))

    def test_choice_str(self):
        self.assertEqual(str(self.choice_a), 'Option A')

    def test_question_ordering(self):
        questions = list(self.survey.questions.all())
        self.assertEqual(questions[0], self.text_q)
        self.assertEqual(questions[1], self.mc_q)


class HomeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.active_survey = Survey.objects.create(title='Active', is_active=True)
        self.inactive_survey = Survey.objects.create(title='Inactive', is_active=False)

    def test_home_lists_active_surveys(self):
        response = self.client.get(reverse('surveys:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Active')
        self.assertNotContains(response, 'Inactive')

    def test_home_template(self):
        response = self.client.get(reverse('surveys:home'))
        self.assertTemplateUsed(response, 'surveys/home.html')
        self.assertTemplateUsed(response, 'surveys/base.html')


class SurveyDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.survey = Survey.objects.create(title='Detail Survey', is_active=True)
        self.q = Question.objects.create(
            survey=self.survey, text='Your thoughts?', question_type=Question.TEXT
        )

    def test_detail_returns_200(self):
        response = self.client.get(reverse('surveys:survey_detail', args=[self.survey.pk]))
        self.assertEqual(response.status_code, 200)

    def test_detail_404_for_inactive(self):
        inactive = Survey.objects.create(title='Inactive', is_active=False)
        response = self.client.get(reverse('surveys:survey_detail', args=[inactive.pk]))
        self.assertEqual(response.status_code, 404)

    def test_detail_shows_question(self):
        response = self.client.get(reverse('surveys:survey_detail', args=[self.survey.pk]))
        self.assertContains(response, 'Your thoughts?')

    def test_detail_template(self):
        response = self.client.get(reverse('surveys:survey_detail', args=[self.survey.pk]))
        self.assertTemplateUsed(response, 'surveys/survey_detail.html')


class SurveySubmitViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.survey = Survey.objects.create(title='Submit Survey', is_active=True)
        self.text_q = Question.objects.create(
            survey=self.survey, text='Name?', question_type=Question.TEXT, order=1
        )
        self.mc_q = Question.objects.create(
            survey=self.survey, text='Choice?', question_type=Question.MULTIPLE_CHOICE, order=2
        )
        self.choice = Choice.objects.create(question=self.mc_q, text='Yes')
        self.rating_q = Question.objects.create(
            survey=self.survey, text='Rate?', question_type=Question.RATING, order=3
        )
        self.yesno_q = Question.objects.create(
            survey=self.survey, text='Agree?', question_type=Question.YES_NO, order=4
        )

    def test_get_redirects_to_detail(self):
        response = self.client.get(reverse('surveys:survey_submit', args=[self.survey.pk]))
        self.assertRedirects(response, reverse('surveys:survey_detail', args=[self.survey.pk]))

    def test_post_creates_response_and_answers(self):
        data = {
            f'question_{self.text_q.pk}': 'Alice',
            f'question_{self.mc_q.pk}': str(self.choice.pk),
            f'question_{self.rating_q.pk}': '4',
            f'question_{self.yesno_q.pk}': 'yes',
        }
        response = self.client.post(reverse('surveys:survey_submit', args=[self.survey.pk]), data)
        self.assertRedirects(response, reverse('surveys:thank_you', args=[self.survey.pk]))

        self.assertEqual(Response.objects.count(), 1)
        self.assertEqual(Answer.objects.count(), 4)

        text_answer = Answer.objects.get(question=self.text_q)
        self.assertEqual(text_answer.text_answer, 'Alice')

        mc_answer = Answer.objects.get(question=self.mc_q)
        self.assertEqual(mc_answer.choice, self.choice)

        rating_answer = Answer.objects.get(question=self.rating_q)
        self.assertEqual(rating_answer.text_answer, '4')

        yesno_answer = Answer.objects.get(question=self.yesno_q)
        self.assertEqual(yesno_answer.text_answer, 'Yes')

    def test_post_inactive_survey_returns_404(self):
        inactive = Survey.objects.create(title='Inactive', is_active=False)
        response = self.client.post(reverse('surveys:survey_submit', args=[inactive.pk]), {})
        self.assertEqual(response.status_code, 404)


class ThankYouViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.survey = Survey.objects.create(title='Thank You Survey')

    def test_thank_you_returns_200(self):
        response = self.client.get(reverse('surveys:thank_you', args=[self.survey.pk]))
        self.assertEqual(response.status_code, 200)

    def test_thank_you_template(self):
        response = self.client.get(reverse('surveys:thank_you', args=[self.survey.pk]))
        self.assertTemplateUsed(response, 'surveys/thank_you.html')

    def test_thank_you_shows_survey_title(self):
        response = self.client.get(reverse('surveys:thank_you', args=[self.survey.pk]))
        self.assertContains(response, 'Thank You Survey')
