from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# ---------------------- User Profile ----------------------

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('driver', 'Driver'),
        ('user', 'Passenger/User'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    contact = models.CharField(max_length=20, blank=True)

    # Driver-specific fields
    vehicle = models.CharField(max_length=50, blank=True)
    plate = models.CharField(max_length=20, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    special = models.CharField(max_length=100, blank=True)  # e.g., AC, pet-friendly

    def __str__(self):
        return f"{self.user.username} ({self.role})"

# ---------------------- Ride Model ----------------------

class Ride(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('driving', 'In Progress'),
        ('completed', 'Completed'),
    ]

    driver = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='driven_rides'
    )
    rider = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='rides'
    )  # The person posting the ride
    source = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    arrivaldate = models.DateTimeField(default=timezone.now)
    passenger = models.PositiveIntegerField(default=1)  # seats booked by creator
    sharable = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    sharers = models.ManyToManyField(
        User, through='RideShare', blank=True, related_name='shared_rides'
    )
    special = models.CharField(max_length=100, blank=True)  # optional: special requirements

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.source} → {self.destination} on {self.arrivaldate.strftime('%Y-%m-%d %H:%M')}"

    def available_seats(self):
        """Calculate available seats for sharers."""
        driver_capacity = self.driver.userprofile.capacity if self.driver and hasattr(self.driver, 'userprofile') else 0
        shared_passengers = self.rideshare_set.aggregate(total=models.Sum('passenger_count'))['total'] or 0
        seats_left = driver_capacity - self.passenger - shared_passengers
        return max(seats_left, 0)

# ---------------------- RideShare Model ----------------------

class RideShare(models.Model):
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE)
    sharer = models.ForeignKey(User, on_delete=models.CASCADE)
    passenger_count = models.PositiveIntegerField(default=1)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('ride', 'sharer')

    def __str__(self):
        return f"{self.sharer.username} shares Ride {self.ride.id} ({self.passenger_count} seats)"

# ---------------------- Optional: Ratings for Drivers ----------------------

class RideRating(models.Model):
    ride = models.OneToOneField(Ride, on_delete=models.CASCADE)
    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_given')
    ratee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_received')
    rating = models.PositiveSmallIntegerField(default=5)  # 1 to 5 stars
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rater.username} rated {self.ratee.username}: {self.rating}/5"
