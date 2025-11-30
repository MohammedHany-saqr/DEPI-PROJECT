from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import JSONParser
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import joblib
import numpy as np
import os # <--- ADD THIS LINE
import joblib
import traceback # <--- ADD THIS LINE HERE
import numpy as np
import pandas as pd
from PIL import Image
import random # For chat/tumor placeholders
from scipy.stats import boxcox
from .models import Doctor, PatientProfile, Appointment
from .serializers import DoctorSerializer, PatientProfileSerializer, AppointmentSerializer
import ocr_processor
import tempfile
from django.core.files.storage import default_storage


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


# ---------------- OCR / ID extraction ----------------
class ExtractID(APIView):
    """Accept an uploaded ID image and run the OCR pipeline (uses ocr_processor.py).

    Endpoint: POST /api/ocr/extract-id/
    Expects form-data file field named 'file' (or 'image'). Returns JSON with name, age, gender, address, national_id
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            # prefer 'file' field but allow 'image' fallback
            upload = request.FILES.get('file') or request.FILES.get('image')
            if not upload:
                return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

            # save to a temporary file and pass path to OCR processor
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(upload.name)[1])
            tmp.write(upload.read())
            tmp.flush()
            tmp_path = tmp.name
            tmp.close()

            result = ocr_processor.run_ocr_on_file(tmp_path)

            # cleanup file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            # include error information to help debugging
            return Response({"error": f"OCR failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# appointments/views.py (REPLACE your existing PredictHeartDisease class with this)
class PredictHeartDisease(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        try:
            APP_DIR = os.path.dirname(os.path.abspath(__file__))
            MODEL_PATH = os.path.join(APP_DIR, "..", "models") 

            # 2. Load saved model and preprocessing objects using the calculated path
            model = joblib.load(os.path.join(MODEL_PATH, "heart.pkl"))
            scaler = joblib.load(os.path.join(MODEL_PATH, "scaler.pkl"))
            opt_lambda = joblib.load(os.path.join(MODEL_PATH, "opt_lambda.pkl"))
            # 2. Extract Raw Features with SAFE FALLBACKS
            data = request.data
            
            # Use .get(key, default) to prevent NoneType errors on conversion
            age_years = data.get("age", 40)
            height_cm = data.get("height", 170.0)
            weight = data.get("weight", 70.0)
            ap_hi = data.get("ap_hi", 120.0)
            ap_lo = data.get("ap_lo", 80.0)
            cholesterol = data.get("cholesterol", 1) # Default to 1 (Normal)
            gluc = data.get("gluc", 1)             # Default to 1 (Normal)
            smoke = data.get("smoke", 0)
            alco = data.get("alco", 0)

            # --- Preprocessing Pipeline ---
            
            # a. Feature Engineering (Pulse Pressure, MAP, BMI)
            height_m = float(height_cm) / 100 
            pulse_pressure = float(ap_hi) - float(ap_lo) 
            map_val = float(ap_lo) + (pulse_pressure) / 3 
            bmi = float(weight) / (height_m ** 2) 

            # b. Age Transformation (Box-Cox) 
            # Use .item() to safely extract the single transformed scalar value
            age_box = boxcox(np.array([age_years]), lmbda=opt_lambda)[0].item()
            
            # c. Create DataFrame for Numerical Features
            data_to_scale = pd.DataFrame({
                'age_box': [age_box],
                'weight': [float(weight)],
                'smoke': [int(smoke)],
                'alco': [int(alco)],
                'pulse_pressure': [pulse_pressure],
                'map': [map_val],
                'bmi': [bmi]
            })

            # d. Scaling 
            scaled_features = scaler.transform(data_to_scale)
            scaled_df = pd.DataFrame(scaled_features, columns=data_to_scale.columns)

            # e. One-Hot Encoding 
            chol_above = 1 if cholesterol == 2 else 0
            chol_normal = 1 if cholesterol == 1 else 0
            chol_well_above = 1 if cholesterol == 3 else 0
            
            gluc_above = 1 if gluc == 2 else 0
            gluc_normal = 1 if gluc == 1 else 0
            gluc_well_above = 1 if gluc == 3 else 0
            
            ohe_features = pd.DataFrame({
                'cholesterol_above_normal': [chol_above],
                'cholesterol_normal': [chol_normal],
                'cholesterol_well_above_normal': [chol_well_above],
                'gluc_above_normal': [gluc_above],
                'gluc_normal': [gluc_normal],
                'gluc_well_above_normal': [gluc_well_above]
            })

            # f. Combine and Prepare Final Input Array
            final_features_df = pd.concat([scaled_df, ohe_features], axis=1)
            features_array = final_features_df.to_numpy().reshape(1, -1)

            # 3. Predict
            prediction = int(model.predict(features_array)[0])

            return Response({"prediction": prediction}, status=status.HTTP_200_OK)

        except FileNotFoundError:
            # Print the traceback for FileNotFoundError to the console
            traceback.print_exc()
            return Response({"error": "Model or preprocessing files not found. Check paths: ../models/heart.pkl, ../models/scaler.pkl, ../models/opt_lambda.pkl"}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            # Print the full error for general exceptions to the console
            traceback.print_exc() 
            return Response({"error": f"Prediction failed due to data processing error: {str(e)}"}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
# ---------------- Diabetes Prediction ----------------
# appointments/views.py (Final corrected PredictDiabetes class)
# appointments/views.py (Final corrected PredictDiabetes class)
# appointments/views.py (Final corrected PredictDiabetes class)

class PredictDiabetes(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        try:
            # 1. Setup path and load model components
            APP_DIR = os.path.dirname(os.path.abspath(__file__))
            MODEL_PATH = os.path.join(APP_DIR, "..", "models")
            
            model = joblib.load(os.path.join(MODEL_PATH, "diabetes.pkl"))
            scaler = joblib.load(os.path.join(MODEL_PATH, "scaler_diabetes.pkl"))
            
            # 2. Extract Raw Features with SAFE FALLBACKS
            data = request.data
            
            # Numerical features (to be scaled)
            age = float(data.get("age", 40))
            bmi = float(data.get("bmi", 25.0))
            hba1c_level = float(data.get("hba1c_level", 5.5))
            blood_glucose_level = float(data.get("blood_glucose_level", 100.0))

            # Binary/Categorical features
            hypertension = int(data.get("hypertension", 0))
            heart_disease = int(data.get("heart_disease", 0))
            gender = data.get("gender", "Female")
            race = data.get("race", "Other")
            smoking_history = data.get("smoking_history", "Never")
            
            # --- Preprocessing Pipeline ---

            # a. Numerical Scaling: Create DataFrame 
            
            # CRITICAL FIX: Confirmed Order from diabetes.ipynb notebook is used here:
            NUMERICAL_COLS_TRAINING_ORDER = [
                'bmi', 
                'hbA1c_level', 
                'blood_glucose_level',
                'age'
            ]

            numerical_features_df = pd.DataFrame({
                'age': [age],
                'bmi': [bmi],
                'hbA1c_level': [hba1c_level], 
                'blood_glucose_level': [blood_glucose_level]
            })
            
            # Enforce the explicit column order before transformation
            numerical_features_df = numerical_features_df[NUMERICAL_COLS_TRAINING_ORDER]
            
            # Scale the numerical data using the loaded scaler
            scaled_numerical_array = scaler.transform(numerical_features_df)
            scaled_df = pd.DataFrame(scaled_numerical_array, columns=NUMERICAL_COLS_TRAINING_ORDER)

            # b. Categorical Encoding (Manual One-Hot Encoding)
            
            OHE_DATA = {
                # Binary features
                'hypertension': [hypertension],
                'heart_disease': [heart_disease],
                
                # Gender OHE 
                'gender_Female': [1 if gender == "Female" else 0],
                'gender_Male': [1 if gender == "Male" else 0],
                
                # Smoking History OHE
                'smoking_history_Current': [1 if smoking_history == "Current" else 0],
                'smoking_history_Former': [1 if smoking_history == "Former" else 0],
                'smoking_history_Never': [1 if smoking_history == "Never" else 0],
                
                # Race OHE 
                'race_African': [1 if race == "African" else 0],
                'race_American': [1 if race == "American" else 0],
                'race_Asian': [1 if race == "Asian" else 0],
                'race_Caucasian': [1 if race == "Caucasian" else 0],
                'race_Hispanic': [1 if race == "Hispanic" else 0],
                'race_Other': [1 if race == "Other" else 0],
            }
            ohe_df = pd.DataFrame(OHE_DATA)
            
            # c. Combine features 
            FINAL_FEATURE_ORDER = list(scaled_df.columns) + list(ohe_df.columns)
            
            combined_df = pd.concat([scaled_df, ohe_df], axis=1)
            
            # Prepare the final array, ensuring columns are strictly ordered
            features_array = combined_df[FINAL_FEATURE_ORDER].to_numpy().reshape(1, -1)
            
            # 3. Predict
            prediction = int(model.predict(features_array)[0])

            return Response({"prediction": prediction}, status=status.HTTP_200_OK)

        except FileNotFoundError:
            traceback.print_exc()
            return Response({"error": "Diabetes Model or scaler files not found. Ensure all files are in the ../models/ folder."}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            traceback.print_exc()
            return Response({"error": f"Diabetes Prediction failed due to data processing error: {str(e)}"}, 
                            status=status.HTTP_400_BAD_REQUEST)
