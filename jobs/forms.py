from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, UserProfile, JobPost, JobApplication, Message, Feedback
from django.core.validators import FileExtensionValidator

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    user_type = forms.ChoiceField(choices=User.USER_TYPE_CHOICES)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'user_type']

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'address', 'education', 'skills', 'experience', 'resume', 'portfolio', 
                  'company_name', 'job_title', 'linkedin_url', 'github_url']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'education': forms.Textarea(attrs={'rows': 4}),
            'skills': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Python, Django, JavaScript, React'}),
            'experience': forms.Textarea(attrs={'rows': 4}),
        }

class JobPostForm(forms.ModelForm):
    class Meta:
        model = JobPost
        fields = ['title', 'description', 'location', 'salary_range', 'skills_required', 
                  'job_type', 'application_deadline']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6}),
            'application_deadline': forms.DateInput(attrs={'type': 'date'}),
        }

class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = ['cover_letter']
        widgets = {
            'cover_letter': forms.Textarea(attrs={'rows': 5}),
        }

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['receiver', 'subject', 'content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5}),
        }

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['feedback_type', 'subject', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),
        }

class JobSearchForm(forms.Form):
    keyword = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Job title or keyword'}))
    location = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Location'}))
    job_type = forms.ChoiceField(choices=[('', 'All')] + list(JobPost.JOB_TYPE_CHOICES), required=False)
    skill = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Skill'}))