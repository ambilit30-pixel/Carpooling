from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [

    # ---------------------- Authentication ----------------------
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ---------------------- Dashboard ----------------------
    path('dashboard/', views.dashboard, name='dashboard'),

    # ---------------------- Profile ----------------------
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.editinfo, name='editinfo'),
    path('profile/changepassword/', views.changepassword, name='changepassword'),
    path('profile/regisdriver/', views.regisdriver, name='regisdriver'),

    # ---------------------- Ride Management ----------------------
    path('ride/create/', views.create_ride, name='create_ride'),
    path('ride/edit/<int:ride_id>/', views.edit_ride, name='edit_ride'),
    path('ride/delete/<int:ride_id>/', views.delete_ride, name='delete_ride'),
    path('ride/assign_driver/<int:ride_id>/', views.assign_driver, name='assign_driver'),
    path('ride/start/<int:ride_id>/', views.start_ride, name='start_ride'),
    path('ride/complete/<int:ride_id>/', views.complete_ride, name='complete_ride'),

    # ---------------------- Ride Sharing ----------------------
    path('rideshare/find/', views.find_rides_to_share, name='find_rides_to_share'),
    path('rideshare/join/<int:ride_id>/', views.join_ride, name='join_ride'),
    path('rideshare/leave/<int:ride_id>/', views.leave_ride, name='leave_ride'),
    path('rideshare/edit/<int:ride_id>/', views.edit_share, name='edit_share'),

    # ---------------------- Current Ride / Driver Actions ----------------------
    path('ride/current/<int:ride_id>/', views.curtride, name='curtride'),
    path('ride/find_driver/<int:ride_id>/', views.find_ridedriver, name='find_ridedriver'),
    path('ride/handle_drive/<int:ride_id>/', views.handle_drive, name='handle_drive'),
]
