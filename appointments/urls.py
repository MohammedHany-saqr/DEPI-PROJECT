from django.urls import path
from .views import SignupPatient, SignupDoctor, Login, ProfileView, DoctorList, CreateAppointment, MyAppointments

urlpatterns = [
    path("signup/patient/", SignupPatient.as_view()),
    path("signup/doctor/", SignupDoctor.as_view()),
    path("login/", Login.as_view()),
    path("profile/", ProfileView.as_view()),
    path("doctors/", DoctorList.as_view()),
    path("appointment/create/", CreateAppointment.as_view()),
    path("appointments/mine/", MyAppointments.as_view()),
]
