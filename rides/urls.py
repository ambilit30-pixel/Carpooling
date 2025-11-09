from django.urls import path
from . import views

app_name = 'rides'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_info, name='edit_info'),
    path('profile/change-password/', views.change_password, name='change_password'),

    path('set-role/driver/', views.set_role_driver, name='set_role_driver'),
    path('set-role/passenger/', views.revert_to_passenger, name='set_role_passenger'),
    path('driver/register/', views.register_driver, name='register_driver'),

    # ride CRUD
    path('my/rides/', views.my_rides, name='my_rides'),
    path('ride/create/', views.create_ride, name='create_ride'),
    path('ride/<int:ride_id>/edit/', views.edit_ride, name='edit_ride'),
    path('ride/<int:ride_id>/delete/', views.delete_ride, name='delete_ride'),
    path('ride/<int:ride_id>/', views.ride_detail, name='ride_detail'),

    # assign / accept / reject
    path('ride/<int:ride_id>/assign/', views.assign_driver, name='assign_driver'),
    path('ride/<int:ride_id>/accept/', views.accept_assignment, name='accept_assignment'),
    path('ride/<int:ride_id>/reject/', views.reject_assignment, name='reject_assignment'),

    # start / complete
    path('ride/<int:ride_id>/start/', views.start_ride, name='start_ride'),
    path('ride/<int:ride_id>/complete/', views.complete_ride, name='complete_ride'),

    # share/search/join
    path('share/find/', views.find_rides_to_share, name='find_rides_to_share'),
    path('ride/<int:ride_id>/join/', views.join_ride, name='join_ride'),
    path('ride/<int:ride_id>/leave/', views.leave_ride, name='leave_ride'),
    path('ride/<int:ride_id>/edit-share/', views.edit_share, name='edit_share'),
]
