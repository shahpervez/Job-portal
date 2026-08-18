from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    
    # Job related
    path('jobs/', views.job_list, name='job_list'),
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    path('post-job/', views.post_job, name='post_job'),
    path('my-jobs/', views.my_jobs, name='my_jobs'),
    path('job/<int:job_id>/applications/', views.manage_applications, name='manage_applications'),
    path('save-job/<int:job_id>/', views.save_job, name='save_job'),
    path('saved-jobs/', views.saved_jobs, name='saved_jobs'),
    
    # Messaging and notifications
    path('messages/', views.messages_view, name='messages'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('feedback/', views.feedback_view, name='feedback'),
    
    # Admin URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/manage-users/', views.manage_users, name='manage_users'),
    path('admin/manage-jobs/', views.manage_jobs, name='manage_jobs'),
    path('admin/report/<str:report_type>/', views.generate_report, name='generate_report'),
    path('admin/backup/', views.database_backup, name='database_backup'),
    path('admin/feedback/', views.view_feedback, name='view_feedback'),
]