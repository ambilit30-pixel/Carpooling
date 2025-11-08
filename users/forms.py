from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import UserProfile, Ride, RideShare

# ---------------------- User Authentication ----------------------

class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("Username already exists")
        return username

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 != p2:
            raise ValidationError("Passwords do not match")
        cleaned_data['password2'] = p2
        return cleaned_data

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

# ---------------------- User Profile ----------------------

class EditInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput)
    new_password1 = forms.CharField(widget=forms.PasswordInput)
    new_password2 = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password1')
        p2 = cleaned_data.get('new_password2')
        if p1 != p2:
            raise ValidationError("New passwords do not match")
        return cleaned_data

class DriverForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['contact', 'vehicle', 'plate', 'capacity', 'special']

# ---------------------- Ride Management ----------------------

class RideForm(forms.ModelForm):
    arrivaldate = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    
    class Meta:
        model = Ride
        fields = ['source', 'destination', 'arrivaldate', 'passenger', 'sharable']

class RideEditForm(forms.ModelForm):
    arrivaldate = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    
    class Meta:
        model = Ride
        fields = ['source', 'destination', 'arrivaldate', 'passenger', 'sharable']

# ---------------------- Ride Sharing ----------------------

class ShareForm(forms.Form):
    destination = forms.CharField(max_length=100)
    earlyarrival = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    latearrival = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    passenger = forms.IntegerField(min_value=1)

    def clean(self):
        cleaned_data = super().clean()
        early = cleaned_data.get('earlyarrival')
        late = cleaned_data.get('latearrival')
        if early and late and early > late:
            raise ValidationError("Early arrival cannot be after late arrival")
        return cleaned_data

class ShareEditForm(forms.ModelForm):
    class Meta:
        model = RideShare
        fields = ['passenger_count']
