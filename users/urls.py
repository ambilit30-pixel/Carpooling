from django.urls import path
from . import views

app_name = 'rides'

urlpatterns = [
    # auth
    path('register/', views.register, name='register'),
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # add this to the urlpatterns list
    path('profile/revert-to-passenger/', views.revert_to_passenger, name='revert_to_passenger'),


    # dashboard & profile
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_info, name='edit_info'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/register-driver/', views.register_driver, name='register_driver'),

    # ride CRUD
    path('rides/create/', views.create_ride, name='create_ride'),
    path('rides/<int:ride_id>/edit/', views.edit_ride, name='edit_ride'),
    path('rides/<int:ride_id>/delete/', views.delete_ride, name='delete_ride'),

    # assign/start/complete
    path('rides/<int:ride_id>/assign-driver/', views.assign_driver, name='assign_driver'),
    path('rides/<int:ride_id>/start/', views.start_ride, name='start_ride'),
    path('rides/<int:ride_id>/complete/', views.complete_ride, name='complete_ride'),

    # sharing
    path('share/find/', views.find_rides_to_share, name='find_rides_to_share'),
    path('share/<int:ride_id>/join/', views.join_ride, name='join_ride'),
    path('share/<int:ride_id>/leave/', views.leave_ride, name='leave_ride'),
    path('share/<int:ride_id>/edit/', views.edit_share, name='edit_share'),
]
