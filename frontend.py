import streamlit as st
import requests
from datetime import datetime

API_URL = "http://127.0.0.1:8000/api/"
st.set_page_config(page_title="ROSHDA", page_icon="🏥", layout="wide")
# _________________CSS_________________________
# ---------- Creative Modern Sidebar (Neon + Glass) ----------
st.markdown("""
    <style>

    /* Global Background */
    .stApp {
        background: linear-gradient(135deg, #1a1c24, #11141a);
        color: #ffffff;
    }

    /* Sidebar Container */
    section[data-testid="stSidebar"] {
        background: rgba(20, 23, 32, 0.65);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255,255,255,0.08);
        padding: 30px 20px !important;
        border-radius: 0 25px 25px 0;
        box-shadow: 4px 0 25px rgba(0,0,0,0.4);
    }

    /* Sidebar Title */
   section[data-testid="stSidebar"] h1 {
    background: none !important;
    -webkit-background-clip: unset !important;
    -webkit-text-fill-color: white !important;
    color: white !important;
}


    /* Logout Button */
    .stButton>button {
        width: 100%;
        padding: 12px;
        border-radius: 12px;
        background: linear-gradient(135deg, #ff5f6d, #ff3d80);
        color: white;
        font-size: 17px;
        border: none;
        box-shadow: 0 0 8px rgba(255, 50, 100, 0.5);
        transition: 0.3s;
    }

    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 0 14px rgba(255, 50, 100, 0.8);
        background: linear-gradient(135deg, #ff3d80, #ff5f6d);
    }

    /* Radio Label (Menu Title) */
    div[data-testid="stRadio"] > label {
        color: #ffffff !important;
        font-size: 20px !important;
        font-weight: 700;
        margin-bottom: 12px;
    }

    /* Radio Items */
    div[role="radiogroup"] > label {
        background: rgba(255, 255, 255, 0.05);
        padding: 10px 15px;
        margin: 6px 0;
        border-radius: 10px;
        font-size: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
        cursor: pointer;
        transition: 0.25s;
        border: 1px solid rgba(255,255,255,0.05);
    }

    div[role="radiogroup"] > label:hover {
        background: rgba(255, 255, 255, 0.12);
        transform: translateX(4px);
    }

    /* Selected Option */
    div[role="radiogroup"] input:checked + div {
        background: linear-gradient(135deg, #ff4c6a, #ff7f50);
        border: 1px solid rgba(255,255,255,0.3);
        color: #ffffff !important;
        font-weight: 700 !important;
        box-shadow: 0 0 8px rgba(255, 99, 120, 0.7);
        transform: scale(1.02);
    }


    </style>
""", unsafe_allow_html=True)

# ________________________________________________________________
# -------- Global Brand Header --------
st.markdown("""
<div style="
    width:100%;
    padding: 18px 0;
    text-align:center;
    font-size: 32px;
    font-weight: 800;
    color: #ff4c6a;
    text-shadow: 0 0 10px rgba(255, 76, 106, 0.6);
    letter-spacing: 3px;
    margin-bottom: 25px;
    border-bottom: 1px solid rgba(255,255,255,0.15);
">
    ROSHDA
</div>
""", unsafe_allow_html=True)

# Session state
if 'token' not in st.session_state: st.session_state['token'] = None
if 'user_id' not in st.session_state: st.session_state['user_id'] = None
if 'user_name' not in st.session_state: st.session_state['user_name'] = ""
if 'role' not in st.session_state: st.session_state['role'] = None


# ---------------- API request helper ----------------
def api_request(method, endpoint, data=None, files=None):
    headers = {}
    if st.session_state['token']:
        headers['Authorization'] = f"Token {st.session_state['token']}"
    url = f"{API_URL}{endpoint}"

    try:
        if method == "POST":
            if files:
                return requests.post(url, files=files, headers=headers)
            else:
                return requests.post(url, json=data, headers=headers)

        if method == "GET":
            return requests.get(url, headers=headers)
        if method == "PUT":
            return requests.put(url, json=data, headers=headers)

    except requests.exceptions.ConnectionError:
        st.error("❌ Could not connect to backend.")
        return None


# ---------------- Login / Logout ----------------
def handle_login(username, password):
    res = api_request("POST", "login/", {"username": username, "password": password})
    if res and res.status_code == 200:
        data = res.json()
        st.session_state['token'] = data['token']
        st.session_state['role'] = data['role']
        profile_res = api_request("GET", "profile/")
        if profile_res and profile_res.status_code == 200:
            profile_data = profile_res.json()
            st.session_state['user_id'] = profile_data.get('id', profile_data.get('username'))
            st.session_state['user_name'] = (
                    profile_data.get('name')
                    or profile_data.get('full_name')
                    or profile_data.get('first_name')
                    or profile_data.get('username')
                    or profile_data.get('user')
                    or username
            )

            st.success("Login Successful!")
            st.rerun()
    else:
        st.error("Invalid Username or Password")


def handle_logout():
    st.session_state['token'] = None
    st.session_state['user_id'] = None
    st.session_state['user_name'] = ""
    st.session_state['role'] = None
    st.rerun()


# ---------------- Login / Signup Screen ----------------
if not st.session_state['token']:
    st.title("🏥 AI Hospital Portal")
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"): handle_login(username, password)

    with tab2:
        st.subheader("Create New Account")

        # ----------- Upload ID for Auto Fill -----------
        uploaded_id = st.file_uploader("Upload National ID Card", type=["jpg", "jpeg", "png"])

        auto_name = ""
        auto_age = None
        auto_gender = ""
        auto_address = ""

        if uploaded_id is not None:
            st.image(uploaded_id, use_column_width=True)
            if st.button("Extract from ID"):
                files = {"file": uploaded_id.getvalue()}
                res = api_request("POST", "ocr/extract-id/", files=files)

                if res and res.status_code == 200:
                    data = res.json()
                    st.success("ID Extracted Successfully!")

                    # Auto-filled values returned from backend OCR
                    auto_name = data.get("name", "")
                    auto_gender = data.get("gender", "")
                    auto_address = data.get("address", "")
                    auto_age = data.get("age", None)
                else:
                    st.error("Failed to extract info — check backend.")
        # -------------------------------------------------

        with st.form("signup_form"):
            new_user = st.text_input("Choose a Username")
            new_pass = st.text_input("Choose a Password", type="password")
            full_name = st.text_input("Full Name", value=auto_name)

            role_select = st.selectbox("I am a...", ["patient", "doctor"])

            if role_select == "patient":
                gender = st.text_input("Gender", value=auto_gender)
                age = st.number_input("Age", min_value=0, max_value=120, value=auto_age if auto_age else 0)
                address = st.text_area("Address", value=auto_address)
            else:
                spec = st.text_input("Specialization")

            if st.form_submit_button("Register"):
                if role_select == "patient":
                    payload = {
                        "username": new_user,
                        "password": new_pass,
                        "name": full_name,
                        "age": age,
                        "gender": gender,
                        "address": address
                    }
                    endpoint = "signup/patient/"

                else:
                    payload = {
                        "username": new_user,
                        "password": new_pass,
                        "name": full_name,
                        "specialization": spec
                    }
                    endpoint = "signup/doctor/"

                res = api_request("POST", endpoint, payload)

                if res and res.status_code == 201:
                    st.success("✅ Account created! Login now.")
                else:
                    st.error(f"Registration failed: {res.text if res else 'Server error'}")


# ---------------- Dashboard ----------------
else:
    # Sidebar
    display_name = st.session_state.get("user_name", "").strip()

    if not display_name:
        display_name = "User"

    if st.session_state['role'] == "doctor":
        display_name = "Dr. " + display_name

    st.sidebar.markdown(f"""
        <h1 style='font-size:26px; font-weight:800; color:white;'>
            👋 Welcome, {display_name}
        </h1>
    """, unsafe_allow_html=True)
    if st.sidebar.button("Logout"):
        handle_logout()

    # Main menu
    menu_options = ["My Appointments"]
    if st.session_state['role'] == "patient":
        menu_options.insert(0, "Book Appointment")
        menu_options.append("My Medical Profile")
        menu_options.append("Chat")
        menu_options.append("Blood Sugar Check")
        menu_options.append("Blood Pressure Check")
        menu_options.append("Heart Disease Check")
        menu_options.append("Brain Tumor Scan")

    # Radio menu for main options
    menu = st.sidebar.radio("Menu", menu_options)

    if menu == "Book Appointment":
        st.header("📅 Book a Doctor")
        res = api_request("GET", "doctors/")
        if res and res.status_code == 200:
            doctors = res.json()
            doc_options = {f"Dr. {d['name']} ({d['specialization']})": d['id'] for d in doctors}
            with st.form("booking_form"):
                selected_doc = st.selectbox("Select Doctor", list(doc_options.keys()))
                appt_date = st.date_input("Date")
                appt_time = st.time_input("Time")
                reason = st.text_area("Reason")
                if st.form_submit_button("Confirm Appointment"):
                    payload = {"doctor_id": doc_options[selected_doc], "date": appt_date.strftime("%Y-%m-%d"),
                               "time": appt_time.strftime("%H:%M:%S"), "reason": reason}
                    post_res = api_request("POST", "appointment/create/", payload)
                    if post_res and post_res.status_code == 201:
                        st.success("Appointment Booked!")
                    else:
                        st.error(f"Failed: {post_res.text if post_res else 'Server error'}")
        else:
            st.warning("No doctors found.")

    elif menu == "My Appointments":
        st.header("🗓️ My Appointments")
        res = api_request("GET", "appointments/mine/")
        if res and res.status_code == 200:
            appts = res.json()
            if appts:
                for a in appts:
                    st.write(f"**Date:** {a['date']} {a['time']}")
                    st.caption(f"Doctor: Dr. {a['doctor']['name']} ({a['doctor']['specialization']})")
                    st.caption(f"Reason: {a['reason']}")
            else:
                st.info("No appointments found.")

    elif menu == "My Medical Profile":
        st.header("📂 My Profile")
        res = api_request("GET", "profile/")
        if res and res.status_code == 200:
            data = res.json()
            with st.form("profile_update"):
                name = st.text_input("Full Name", value=data.get('first_name', ''))
                email = st.text_input("Email", value=data.get('email', ''))
                age = st.number_input("Age", value=data.get('age', 0))
                history = st.text_area("Medical History", value=data.get('medical_history', ''))
                if st.form_submit_button("Update Profile"):
                    payload = {"first_name": name, "email": email, "age": age, "medical_history": history}
                    put_res = api_request("PUT", "profile/", payload)
                    if put_res and put_res.status_code in [200, 201]:
                        st.success("Profile Updated!")
                    else:
                        st.error("Failed to update profile.")
    elif menu == "Chat":
        st.header("💬 Chat with Doctor / Support (AI Powered)")

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state["messages"] = []

        # Text input
        user_input = st.text_input("Type your message:")

        # Send button
        if st.button("Send") and user_input:

            # Add user message
            st.session_state["messages"].append({
                "role": "user",
                "text": user_input
            })

            # ----------------- Call Backend API -----------------
            try:
                response = api_request(
                    "POST",
                    "chat/ai/",
                    {"message": user_input}
                )

                if response and response.status_code == 200:
                    bot_reply = response.json().get("reply", "⚠️ No response from AI.")
                else:
                    bot_reply = "⚠️ Error connecting to AI model."

            except Exception as e:
                bot_reply = f"⚠️ Exception: {e}"

            # Add bot message
            st.session_state["messages"].append({
                "role": "bot",
                "text": bot_reply
            })

        # ----------------- Display Chat -----------------
        for msg in st.session_state["messages"]:
            if msg["role"] == "user":
                st.markdown(f"🧑‍💻 **You:** {msg['text']}")
            else:
                st.markdown(f"🤖 **AI:** {msg['text']}")

    elif menu == "Blood Sugar Check":

        st.header("🩺 Blood Sugar Check")

        with st.form("blood_sugar_form"):

            year = st.number_input("Year of Birth", min_value=1900, max_value=2025, value=2000)

            gender = st.selectbox("Gender", ["Male", "Female"])
            gender_val = 1 if gender == "Male" else 0

            age = st.number_input("Age", min_value=0, max_value=120, value=30)

            race = st.selectbox("Race", ["African", "American", "Asian", "Caucasian", "Hispanic", "Other"])

            hypertension = st.selectbox("Hypertension", ["Yes", "No"])

            heart_disease = st.selectbox("Heart Disease", ["Yes", "No"])

            smoking_history = st.selectbox("Smoking History", ["Never", "Former", "Current"])

            bmi = st.number_input("BMI", min_value=0.0, max_value=100.0, value=25.0)

            hba1c_level = st.number_input("HbA1c Level (%)", min_value=0.0, max_value=20.0, value=5.5)

            blood_glucose_level = st.number_input("Blood Glucose Level (mg/dL)", min_value=0.0, max_value=500.0,
                                                  value=100.0)

            submitted = st.form_submit_button("Check Blood Sugar Risk")

        if submitted:

            # -------------------- PAYLOAD FOR MODEL --------------------

            payload = {

                "year": year,
                "gender": gender_val, 
                "age": age,
                "race": race,
                "hypertension": 1 if hypertension == "Yes" else 0,
                "heart_disease": 1 if heart_disease == "Yes" else 0,
                "smoking_history": smoking_history,
                "bmi": bmi,
                "hba1c_level": hba1c_level,
                "blood_glucose_level": blood_glucose_level

            }

            # -------------------- API CALL --------------------

            res = api_request("POST", "predict/diabetes/", payload)

            if res and res.status_code == 200:

                prediction = res.json()["prediction"]  # expected 0 = no diabetes, 1 = diabetes

                if prediction == 1:

                    risk = "High Diabetes Risk"

                    color = "#b30000"

                else:

                    risk = "Low Diabetes Risk"
                    color = "#009933"

            else:

                st.error("Prediction failed — check backend")
                st.stop()

            # -----------------------------------------------------

            st.subheader("Model Prediction:")

            st.markdown(f"""

                <div style='padding:20px; border-radius:10px; 

                background-color:{color}; color:white; 

                font-size:22px; text-align:center; margin-top:10px;'>

                <b>{risk}</b>

                </div>

            """, unsafe_allow_html=True)


    elif menu == "Blood Pressure Check":

        st.header("💓 Blood Pressure Check")

        with st.form("bp_form"):

            # ---- NEW INPUTS ----

            age = st.number_input("Age", min_value=1, max_value=120, value=30)
            gender = st.selectbox("Gender", ["Male", "Female"])
            gender_val = 1 if gender == "Male" else 0  
            height = st.number_input("Height (cm)", min_value=50, max_value=250, value=170)

            weight = st.number_input("Weight (kg)", min_value=10, max_value=300, value=70)

            ap_hi = st.number_input("Systolic BP (ap_hi)", min_value=50, max_value=250, value=120)

            ap_lo = st.number_input("Diastolic BP (ap_lo)", min_value=30, max_value=150, value=80)

            cholesterol = st.selectbox("Cholesterol Level", [1, 2, 3])

            gluc = st.selectbox("Glucose Level", [1, 2, 3])

            smoke = st.selectbox("Smokes?", [0, 1])

            alco = st.selectbox("Alcohol Intake?", [0, 1])

            heart_disease = st.selectbox("Heart Disease?", [0, 1])

            submitted = st.form_submit_button("Check Blood Pressure")

        if submitted:

            payload = {
                "age": age,
                "gender": gender_val, 
                "height": height,
                "weight": weight,
                "ap_hi": ap_hi,
                "ap_lo": ap_lo,
                "cholesterol": cholesterol,
                "gluc": gluc,
                "smoke": smoke,
                "alco": alco,
                "heart_disease": heart_disease

            }
            res = api_request("POST", "predict/heart/", payload)

            if res and res.status_code == 200:
                prediction = res.json()["prediction"]  # 0=Low Risk, 1=High Risk of Heart Disease


                if ap_hi >= 140 or ap_lo >= 90:
                    bp_level = "High Blood Pressure (Hypertension)"
                    bp_color = "#b30000"
                elif ap_hi < 90 or ap_lo < 60:
                    bp_level = "Low Blood Pressure"
                    bp_color = "#0066cc"
                else:
                    bp_level = "Normal Blood Pressure"
                    bp_color = "#009933"

                heart_risk_msg = "High Risk of Heart Disease" if prediction == 1 else "Low Risk of Heart Disease"
                heart_risk_color = "#b30000" if prediction == 1 else "#009933"

                st.subheader("Results:")

                st.markdown(f"""
                    <div style='padding:15px; border-radius:10px; 
                    background-color:{bp_color}; color:white; font-size:18px; text-align:center;'>
                    <b>Your Blood Pressure Level:</b><br>{bp_level}
                    </div>

                    <div style='padding:15px; border-radius:10px; 
                    background-color:{heart_risk_color}; color:white; font-size:18px; text-align:center; margin-top:10px;'>
                    <b>AI Model Heart Disease Prediction:</b><br>{heart_risk_msg}
                    </div>

                """, unsafe_allow_html=True)

            else:
                st.error("Prediction failed — check backend")

    elif menu == "Heart Disease Check":
        st.header("❤️ Heart Disease Prediction")

        with st.form("heart_form"):

            age = st.number_input("Age", min_value=1, max_value=120, value=40)
            gender = st.selectbox("Gender", ["Male", "Female"])
            gender_val = 1 if gender == "Male" else 0

            height = st.number_input("Height (cm)", min_value=50, max_value=250, value=170)
            weight = st.number_input("Weight (kg)", min_value=10, max_value=300, value=70)

            ap_hi = st.number_input("Systolic BP (ap_hi)", min_value=50, max_value=250, value=120)
            ap_lo = st.number_input("Diastolic BP (ap_lo)", min_value=30, max_value=150, value=80)

            cholesterol = st.selectbox("Cholesterol Level", [1, 2, 3])
            gluc = st.selectbox("Glucose Level", [1, 2, 3])

            smoke = st.selectbox("Smokes?", [0, 1])
            alco = st.selectbox("Alcohol Intake?", [0, 1])
            active = st.selectbox("Physical Activity?", [0, 1])

            submitted = st.form_submit_button("Check Heart Disease Risk")

        if submitted:

            # -------------------- PAYLOAD FOR MODEL --------------------
            payload = {
                "age": age,
                "gender": gender_val,  
                "height": height,
                "weight": weight,
                "ap_hi": ap_hi,
                "ap_lo": ap_lo,
                "cholesterol": cholesterol,
                "gluc": gluc,
                "smoke": smoke,
                "alco": alco,
                "active": active
            }

            # -------------------- API CALL --------------------
            res = api_request("POST", "predict/heart/", payload)

            if res and res.status_code == 200:
                prediction = res.json()["prediction"]  # expected 0=No disease, 1=Disease

                if prediction == 1:
                    risk = "High Risk of Heart Disease"
                    color = "#b30000"  # Red
                else:
                    risk = "Low Risk of Heart Disease"
                    color = "#009933"  # Green
            else:
                st.error("Prediction failed — check backend")
                st.stop()

            # -------------------- RESULT CARD --------------------
            st.subheader("Model Prediction:")

            st.markdown(f"""
                <div style='padding:20px; border-radius:10px; 
                background-color:{color}; color:white; 
                font-size:22px; text-align:center; margin-top:10px;'>
                <b>{risk}</b>
                </div>
            """, unsafe_allow_html=True)

    elif menu == "Brain Tumor Scan":
        st.header("🧠 Brain Tumor Detection (AI Model)")
        st.write("Upload an MRI/CT image and the AI model will detect if a tumor exists.")

        uploaded_image = st.file_uploader("Upload Brain MRI", type=["jpg", "jpeg", "png"])

        if uploaded_image:
            st.image(uploaded_image, caption="Uploaded MRI", use_column_width=True)

            if st.button("Analyze Image"):
                with st.spinner("Running AI Model..."):

                    # Prepare image file for API
                    files = {"image": uploaded_image.getvalue()}
                    res = api_request("POST", "tumor/detect/", files=files)

                if res and res.status_code == 200:
                    data = res.json()
                    prediction = data["prediction"]
                    confidence = data["confidence"]

                    if prediction == "tumor":
                        st.error(f"⚠️ Tumor Detected — Confidence: {confidence:.2f}")
                    else:
                        st.success(f"✅ No Tumor Detected — Confidence: {confidence:.2f}")

                else:
                    st.error("❌ Failed to connect to the detection model")
