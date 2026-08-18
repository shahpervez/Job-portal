from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from .models import *
from .forms import *
from .decorators import role_required
import csv
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import subprocess
import os

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email_verified = False
            user.save()
            # Create user profile
            UserProfile.objects.create(user=user)
            
            # Send verification email
            token = user.username + str(user.id)
            user.email_verification_token = token
            user.save()
            
            verification_link = request.build_absolute_uri(f'/verify-email/{token}/')
            send_mail(
                'Verify your email',
                f'Click the link to verify your email: {verification_link}',
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False,
            )
            messages.success(request, 'Registration successful! Please check your email for verification.')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})

def verify_email(request, token):
    try:
        user = User.objects.get(email_verification_token=token)
        user.email_verified = True
        user.email_verification_token = ''
        user.save()
        messages.success(request, 'Email verified successfully! You can now login.')
    except User.DoesNotExist:
        messages.error(request, 'Invalid verification token.')
    return redirect('login')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.email_verified:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'Please verify your email first.')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'registration/login.html')

@login_required
def user_logout(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    user = request.user
    context = {}
    
    if user.user_type == 'student' or user.user_type == 'alumni':
        applications = JobApplication.objects.filter(applicant=user).select_related('job')
        saved_jobs = SavedJob.objects.filter(user=user).select_related('job')
        recommended_jobs = []
        
        if hasattr(user, 'profile') and user.profile.skills:
            user_skills = set(user.profile.get_skills_list())
            jobs = JobPost.objects.filter(status='approved', is_active=True)
            job_scores = []
            for job in jobs:
                job_skills = set(job.get_skills_list())
                match_score = len(user_skills.intersection(job_skills))
                if match_score > 0:
                    job_scores.append((job, match_score))
            job_scores.sort(key=lambda x: x[1], reverse=True)
            recommended_jobs = [job for job, score in job_scores[:5]]
        
        context.update({
            'applications': applications[:5],
            'saved_jobs': saved_jobs[:5],
            'recommended_jobs': recommended_jobs,
        })
    
    elif user.user_type == 'employer' or user.user_type == 'alumni':
        job_posts = JobPost.objects.filter(employer=user)
        applications = JobApplication.objects.filter(job__employer=user).select_related('job', 'applicant')
        context.update({
            'job_posts': job_posts,
            'applications': applications[:10],
            'total_applications': applications.count(),
        })
    
    elif user.user_type == 'admin':
        pending_jobs = JobPost.objects.filter(status='pending').count()
        pending_users = User.objects.filter(email_verified=False).count()
        context.update({
            'pending_jobs': pending_jobs,
            'pending_users': pending_users,
            'total_users': User.objects.count(),
            'total_jobs': JobPost.objects.count(),
        })
    
    # Get unread notifications
    notifications = Notification.objects.filter(user=user, is_read=False)
    context['unread_notifications'] = notifications.count()
    
    return render(request, 'dashboard.html', context)

@login_required
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'jobs/profile.html', {'form': form, 'profile': profile})

@login_required
def job_list(request):
    jobs = JobPost.objects.filter(status='approved', is_active=True)
    
    # Search functionality
    search_form = JobSearchForm(request.GET)
    if search_form.is_valid():
        keyword = search_form.cleaned_data.get('keyword')
        location = search_form.cleaned_data.get('location')
        job_type = search_form.cleaned_data.get('job_type')
        skill = search_form.cleaned_data.get('skill')
        
        if keyword:
            jobs = jobs.filter(Q(title__icontains=keyword) | Q(description__icontains=keyword))
        if location:
            jobs = jobs.filter(location__icontains=location)
        if job_type:
            jobs = jobs.filter(job_type=job_type)
        if skill:
            jobs = jobs.filter(skills_required__icontains=skill)
    
    # Pagination
    paginator = Paginator(jobs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get saved jobs for current user
    saved_job_ids = []
    if request.user.is_authenticated:
        saved_job_ids = SavedJob.objects.filter(user=request.user).values_list('job_id', flat=True)
    
    return render(request, 'jobs/job_list.html', {
        'page_obj': page_obj,
        'search_form': search_form,
        'saved_job_ids': saved_job_ids,
    })

@login_required
def job_detail(request, job_id):
    job = get_object_or_404(JobPost, id=job_id)
    has_applied = False
    is_saved = False
    
    if request.user.user_type in ['student', 'alumni']:
        has_applied = JobApplication.objects.filter(job=job, applicant=request.user).exists()
        is_saved = SavedJob.objects.filter(job=job, user=request.user).exists()
    
    # Calculate match score for job seekers
    match_score = None
    if request.user.user_type in ['student', 'alumni'] and hasattr(request.user, 'profile'):
        match_score = job.get_match_score(request.user.profile)
    
    if request.method == 'POST' and 'apply' in request.POST:
        if has_applied:
            messages.warning(request, 'You have already applied for this job.')
        else:
            form = JobApplicationForm(request.POST, request.FILES)
            if form.is_valid():
                application = form.save(commit=False)
                application.job = job
                application.applicant = request.user
                if request.user.profile.resume:
                    application.resume_used = request.user.profile.resume
                application.save()
                
                # Create notification for employer
                Notification.objects.create(
                    user=job.employer,
                    notification_type='application_update',
                    title='New Job Application',
                    message=f'{request.user.username} applied for {job.title}',
                    link=f'/job/{job.id}/applications/'
                )
                
                # Send email notification
                send_mail(
                    'New Job Application',
                    f'{request.user.username} has applied for your job posting: {job.title}',
                    settings.EMAIL_HOST_USER,
                    [job.employer.email],
                    fail_silently=True,
                )
                
                messages.success(request, 'Application submitted successfully!')
                return redirect('job_detail', job_id=job.id)
    
    return render(request, 'jobs/job_detail.html', {
        'job': job,
        'has_applied': has_applied,
        'is_saved': is_saved,
        'match_score': match_score,
    })

@login_required
def post_job(request):
    if request.user.user_type not in ['employer', 'alumni']:
        messages.error(request, 'You are not authorized to post jobs.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.employer = request.user
            job.save()
            messages.success(request, 'Job posted successfully! Waiting for admin approval.')
            return redirect('my_jobs')
    else:
        form = JobPostForm()
    
    return render(request, 'jobs/post_job.html', {'form': form})

@login_required
def my_jobs(request):
    if request.user.user_type not in ['employer', 'alumni']:
        messages.error(request, 'You are not authorized to view this page.')
        return redirect('dashboard')
    
    jobs = JobPost.objects.filter(employer=request.user)
    return render(request, 'jobs/my_jobs.html', {'jobs': jobs})

@login_required
def manage_applications(request, job_id):
    job = get_object_or_404(JobPost, id=job_id, employer=request.user)
    applications = JobApplication.objects.filter(job=job).select_related('applicant__profile')
    
    if request.method == 'POST':
        application_id = request.POST.get('application_id')
        new_status = request.POST.get('status')
        application = get_object_or_404(JobApplication, id=application_id, job=job)
        application.status = new_status
        application.save()
        
        # Notify applicant
        Notification.objects.create(
            user=application.applicant,
            notification_type='application_update',
            title='Application Status Updated',
            message=f'Your application for {job.title} has been {new_status}',
            link=f'/job/{job.id}/'
        )
        
        messages.success(request, 'Application status updated!')
        return redirect('manage_applications', job_id=job.id)
    
    return render(request, 'jobs/manage_applications.html', {
        'job': job,
        'applications': applications,
    })

@login_required
def save_job(request, job_id):
    job = get_object_or_404(JobPost, id=job_id)
    saved_job, created = SavedJob.objects.get_or_create(user=request.user, job=job)
    
    if created:
        messages.success(request, 'Job saved successfully!')
    else:
        saved_job.delete()
        messages.success(request, 'Job removed from saved list!')
    
    return redirect('job_detail', job_id=job_id)

@login_required
def saved_jobs(request):
    saved_jobs = SavedJob.objects.filter(user=request.user).select_related('job')
    return render(request, 'jobs/saved_jobs.html', {'saved_jobs': saved_jobs})

@login_required
def messages_view(request):
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.save()
            
            # Create notification for receiver
            Notification.objects.create(
                user=message.receiver,
                notification_type='message',
                title='New Message',
                message=f'You have a new message from {request.user.username}: {message.subject}',
                link=f'/messages/'
            )
            
            messages.success(request, 'Message sent successfully!')
            return redirect('messages_view')
    else:
        form = MessageForm()
    
    received_messages = Message.objects.filter(receiver=request.user).order_by('-created_at')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-created_at')
    
    # Mark messages as read
    received_messages.filter(is_read=False).update(is_read=True)
    
    return render(request, 'jobs/messages.html', {
        'form': form,
        'received_messages': received_messages,
        'sent_messages': sent_messages,
    })

@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    if request.method == 'POST':
        notification_id = request.POST.get('notification_id')
        if notification_id:
            notification = get_object_or_404(Notification, id=notification_id, user=request.user)
            notification.is_read = True
            notification.save()
        else:
            # Mark all as read
            notifications.update(is_read=True)
        
        return redirect('notifications_view')
    
    return render(request, 'jobs/notifications.html', {'notifications': notifications})

@login_required
def feedback_view(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.save()
            messages.success(request, 'Thank you for your feedback!')
            return redirect('dashboard')
    else:
        form = FeedbackForm()
    
    return render(request, 'jobs/feedback.html', {'form': form})

# Admin Views
@login_required
@role_required(['admin'])
def admin_dashboard(request):
    # Get statistics
    total_users = User.objects.count()
    total_jobs = JobPost.objects.count()
    total_applications = JobApplication.objects.count()
    
    # Monthly statistics
    from django.db.models import Count
    monthly_jobs = JobPost.objects.filter(created_at__year=timezone.now().year).annotate(
        month=models.ExtractMonth('created_at')
    ).values('month').annotate(count=Count('id')).order_by('month')
    
    monthly_applications = JobApplication.objects.filter(applied_at__year=timezone.now().year).annotate(
        month=models.ExtractMonth('applied_at')
    ).values('month').annotate(count=Count('id')).order_by('month')
    
    context = {
        'total_users': total_users,
        'total_jobs': total_jobs,
        'total_applications': total_applications,
        'monthly_jobs': list(monthly_jobs),
        'monthly_applications': list(monthly_applications),
        'pending_jobs': JobPost.objects.filter(status='pending').count(),
        'active_jobs': JobPost.objects.filter(status='approved', is_active=True).count(),
    }
    
    return render(request, 'admin_dashboard/dashboard.html', context)

@login_required
@role_required(['admin'])
def manage_users(request):
    users = User.objects.all().order_by('-date_joined')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        user = get_object_or_404(User, id=user_id)
        
        if action == 'verify':
            user.email_verified = True
            user.save()
            messages.success(request, f'User {user.username} verified successfully!')
        elif action == 'delete':
            user.delete()
            messages.success(request, f'User {user.username} deleted!')
    
    return render(request, 'admin_dashboard/manage_users.html', {'users': users})

@login_required
@role_required(['admin'])
def manage_jobs(request):
    jobs = JobPost.objects.all().order_by('-created_at')
    
    if request.method == 'POST':
        job_id = request.POST.get('job_id')
        action = request.POST.get('action')
        job = get_object_or_404(JobPost, id=job_id)
        
        if action == 'approve':
            job.status = 'approved'
            job.save()
            messages.success(request, f'Job "{job.title}" approved!')
            
            # Notify employer
            Notification.objects.create(
                user=job.employer,
                notification_type='system',
                title='Job Approved',
                message=f'Your job posting "{job.title}" has been approved and is now live.',
                link=f'/job/{job.id}/'
            )
        elif action == 'reject':
            job.status = 'rejected'
            job.save()
            messages.success(request, f'Job "{job.title}" rejected!')
    
    return render(request, 'admin_dashboard/manage_jobs.html', {'jobs': jobs})

@login_required
@role_required(['admin'])
def generate_report(request, report_type):
    if report_type == 'jobs':
        jobs = JobPost.objects.all()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="job_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Title', 'Employer', 'Location', 'Job Type', 'Status', 'Created At', 'Applications'])
        
        for job in jobs:
            writer.writerow([
                job.title,
                job.employer.username,
                job.location,
                job.get_job_type_display(),
                job.status,
                job.created_at.strftime('%Y-%m-%d'),
                job.applications.count()
            ])
        
        return response
    
    elif report_type == 'users':
        users = User.objects.all()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="user_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Username', 'Email', 'User Type', 'Email Verified', 'Date Joined'])
        
        for user in users:
            writer.writerow([
                user.username,
                user.email,
                user.user_type,
                'Yes' if user.email_verified else 'No',
                user.date_joined.strftime('%Y-%m-%d')
            ])
        
        return response
    
    elif report_type == 'applications':
        applications = JobApplication.objects.all()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="application_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Job Title', 'Applicant', 'Status', 'Applied At'])
        
        for application in applications:
            writer.writerow([
                application.job.title,
                application.applicant.username,
                application.status,
                application.applied_at.strftime('%Y-%m-%d')
            ])
        
        return response
    
    return redirect('admin_dashboard')

@login_required
@role_required(['admin'])
def database_backup(request):
    if request.method == 'POST':
        backup_file = f"backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(settings.MEDIA_ROOT, 'backups', backup_file)
        
        # Ensure backup directory exists
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        # Copy database file
        import shutil
        shutil.copy2(settings.DATABASES['default']['NAME'], backup_path)
        
        # Create backup record
        backup = DatabaseBackup.objects.create(
            backup_file=f'backups/{backup_file}',
            created_by=request.user,
            size=os.path.getsize(backup_path)
        )
        
        messages.success(request, f'Database backup created successfully!')
        return redirect('admin_dashboard')
    
    backups = DatabaseBackup.objects.all().order_by('-created_at')
    return render(request, 'admin_dashboard/backups.html', {'backups': backups})

@login_required
@role_required(['admin'])
def view_feedback(request):
    feedbacks = Feedback.objects.all().order_by('-created_at')
    
    if request.method == 'POST':
        feedback_id = request.POST.get('feedback_id')
        response_text = request.POST.get('response')
        feedback = get_object_or_404(Feedback, id=feedback_id)
        feedback.admin_response = response_text
        feedback.status = 'reviewed'
        feedback.save()
        messages.success(request, 'Feedback response saved!')
    
    return render(request, 'admin_dashboard/feedback.html', {'feedbacks': feedbacks})