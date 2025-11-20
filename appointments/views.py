from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import JSONParser
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token

from .models import Doctor, PatientProfile, Appointment
from .serializers import DoctorSerializer, PatientProfileSerializer, AppointmentSerializer


# ---------------- Helpers ----------------
def get_user_role(user):
    if hasattr(user, "doctor_profile"):
        return "doctor"
    if hasattr(user, "patient_profile"):
        return "patient"
    return "patient"   # default fallback


# ---------------- Signup ----------------

class SignupPatient(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        name = request.data.get('name')
        age = request.data.get('age')

        if not all([username, password, name]):
            return Response({"error": "All fields are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists."},
                            status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, password=password,
                                        first_name=name)
        PatientProfile.objects.create(user=user, age=age)

        token, _ = Token.objects.get_or_create(user=user)

        return Response({"message": "Patient registered",
                         "token": token.key},
                        status=status.HTTP_201_CREATED)


class SignupDoctor(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        name = request.data.get('name')
        specialization = request.data.get('specialization')

        if not all([username, password, name, specialization]):
            return Response({"error": "All fields are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists."},
                            status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, password=password,
                                        first_name=name)
        doctor = Doctor.objects.create(user=user, name=name, specialization=specialization)

        token, _ = Token.objects.get_or_create(user=user)

        return Response({"message": "Doctor registered",
                         "doctor": DoctorSerializer(doctor).data,
                         "token": token.key},
                        status=status.HTTP_201_CREATED)


# ---------------- Login ----------------

class Login(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"error": "Invalid credentials"},
                            status=status.HTTP_400_BAD_REQUEST)

        token, _ = Token.objects.get_or_create(user=user)
        role = get_user_role(user)

        return Response({"token": token.key, "role": role},
                        status=status.HTTP_200_OK)


# ---------------- Profile ----------------

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        user = request.user
        data = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "email": user.email,
        }

        if hasattr(user, "patient_profile"):
            profile = user.patient_profile
            data["age"] = profile.age
            data["medical_history"] = profile.medical_history

        return Response(data, status=status.HTTP_200_OK)

    def put(self, request):
        user = request.user

        user.first_name = request.data.get("first_name", user.first_name)
        user.email = request.data.get("email", user.email)
        user.save()

        if hasattr(user, "patient_profile"):
            profile = user.patient_profile
            profile.age = request.data.get("age", profile.age)
            profile.medical_history = request.data.get("medical_history", profile.medical_history)
            profile.save()

        return Response({"message": "Profile updated"},
                        status=status.HTTP_200_OK)


# ---------------- Doctors List ----------------

class DoctorList(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        doctors = Doctor.objects.filter(available=True)
        return Response(DoctorSerializer(doctors, many=True).data,
                        status=status.HTTP_200_OK)


# ---------------- Appointments ----------------

class CreateAppointment(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        doctor_id = request.data.get('doctor_id')
        date = request.data.get('date')
        time = request.data.get('time')
        reason = request.data.get('reason', "")

        if not doctor_id:
            return Response({"error": "doctor_id is required"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            doctor = Doctor.objects.get(id=doctor_id)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor not found"},
                            status=status.HTTP_404_NOT_FOUND)

        if not doctor.available:
            return Response({"error": "Doctor is not available"},
                            status=status.HTTP_400_BAD_REQUEST)

        appointment = Appointment.objects.create(
            doctor=doctor,
            patient=request.user,
            date=date,
            time=time,
            reason=reason
        )

        return Response(AppointmentSerializer(appointment).data,
                        status=status.HTTP_201_CREATED)


class MyAppointments(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        appointments = Appointment.objects.filter(patient=request.user)
        return Response(AppointmentSerializer(appointments, many=True).data,
                        status=status.HTTP_200_OK)
