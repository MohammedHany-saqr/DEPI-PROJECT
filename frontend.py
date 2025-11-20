import streamlit as st
import requests
from datetime import datetime

API_URL = "http://127.0.0.1:8000/api/"
st.set_page_config(page_title="AI Health Portal", page_icon="🏥", layout="wide")

# ---------------- Session Init ----------------
defaults = {
    "token": None,
    "user_id": None,
    "user_name": "",
    "role": None,
    "logged_in": False,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------- API Request Helper ----------------
def api_request(method, endpoint, data=None):
    headers = {}
    if st.session_state["token"]:
        headers["Authorization"] = f"Token {st.session_state['token']}"

    url = f"{API_URL}{endpoint}"

    try:
        if method == "GET":
            return requests.get(url, headers=headers)
        if method == "POST":
            return requests.post(url, json=data, headers=headers)
        if method == "PUT":
            return requests.put(url, json=data, headers=headers)
    except requests.exceptions.ConnectionError:
        st.error("❌ Could not connect to backend.")
        return None


# ---------------- Login / Logout ----------------
def handle_login(username, password):
    res = api_request("POST", "login/", {"username": username, "password": password})

    if not res or res.status_code != 200:
        st.error("Invalid Username or Password")
        return

    data = res.json()
    st.session_state["token"] = data["token"]
    st.session_state["role"] = data["role"]

    # Fetch profile AFTER token is stored
    profile_res = api_request("GET", "profile/")
    if profile_res and profile_res.status_code == 200:
        prof = profile_res.json()
        st.session_state["user_id"] = prof.get("id", None)
        st.session_state["user_name"] = prof.get("first_name", username)

        st.session_state["logged_in"] = True
        st.success("Login Successful!")
        st.stop()  # stop execution → UI reloads cleanly


def handle_logout():
    for key in ["token", "user_id", "user_name", "role", "logged_in"]:
        st.session_state[key] = defaults[key]
    st.success("Logged out successfully!")
    st.rerun()


# ---------------- Login / Signup Screen ----------------
if not st.session_state["logged_in"]:
    st.title("🏥 AI Hospital Portal")
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])

    # -------- Login Tab --------
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                handle_login(username, password)

    # -------- Signup Tab --------
    with tab2:
        with st.form("signup_form"):
            st.subheader("Create New Account")

            new_user = st.text_input("Choose a Username")
            new_pass = st.text_input("Choose a Password", type="password")
            full_name = st.text_input("Full Name")

            role_select = st.selectbox("I am a...", ["patient", "doctor"])

            if role_select == "patient":
                age = st.number_input("Age", 0, 120, 25)
            else:
                spec = st.text_input("Specialization")

            if st.form_submit_button("Register"):
                if role_select == "patient":
                    payload = {
                        "username": new_user,
                        "password": new_pass,
                        "name": full_name,
                        "age": age,
                    }
                    endpoint = "signup/patient/"
                else:
                    payload = {
                        "username": new_user,
                        "password": new_pass,
                        "name": full_name,
                        "specialization": spec,
                    }
                    endpoint = "signup/doctor/"

                res = api_request("POST", endpoint, payload)
                if res and res.status_code == 201:
                    st.success("✅ Account created! You may now login.")
                else:
                    st.error(f"Registration failed: {res.text if res else 'Server error'}")

    st.stop()


# ---------------- Dashboard ----------------
st.sidebar.title(f"Welcome, {st.session_state['user_name']}")
if st.sidebar.button("Logout"):
    handle_logout()

menu_options = ["Book Appointment", "My Appointments"]
if st.session_state["role"] == "patient":
    menu_options.append("My Medical Profile")

menu = st.sidebar.radio("Menu", menu_options)


# -------- Book Appointment --------
if menu == "Book Appointment":
    st.header("📅 Book a Doctor")

    res = api_request("GET", "doctors/")
    if res and res.status_code == 200:
        doctors = res.json()

        if not doctors:
            st.warning("No available doctors.")
        else:
            doctor_map = {f"Dr. {d['name']} ({d['specialization']})": d["id"] for d in doctors}

            with st.form("booking_form"):
                selected = st.selectbox("Select Doctor", list(doctor_map.keys()))
                appt_date = st.date_input("Date")
                appt_time = st.time_input("Time")
                reason = st.text_area("Reason")

                if st.form_submit_button("Confirm Appointment"):
                    payload = {
                        "doctor_id": doctor_map[selected],
                        "date": appt_date.strftime("%Y-%m-%d"),
                        "time": appt_time.strftime("%H:%M:%S"),
                        "reason": reason,
                    }

                    ans = api_request("POST", "appointment/create/", payload)
                    if ans and ans.status_code == 201:
                        st.success("Appointment Booked!")
                    else:
                        st.error(f"Failed: {ans.text if ans else 'Server error'}")
    else:
        st.error("Failed to load doctors.")


# -------- My Appointments --------
elif menu == "My Appointments":
    st.header("🗓️ My Appointments")
    res = api_request("GET", "appointments/mine/")

    if res and res.status_code == 200:
        appts = res.json()
        if not appts:
            st.info("No appointments found.")
        else:
            for a in appts:
                st.subheader(f"{a['date']} at {a['time']}")
                st.caption(f"Doctor: Dr. {a['doctor']['name']} ({a['doctor']['specialization']})")
                st.write(f"Reason: {a['reason']}")
                st.write("---")


# -------- Patient Profile --------
elif menu == "My Medical Profile":
    st.header("📂 My Profile")
    res = api_request("GET", "profile/")

    if res and res.status_code == 200:
        data = res.json()
        with st.form("profile_update"):
            name = st.text_input("Full Name", value=data.get("first_name", ""))
            email = st.text_input("Email", value=data.get("email", ""))
            age = st.number_input("Age", 0, 120, value=data.get("age", 0))
            history = st.text_area("Medical History", value=data.get("medical_history", ""))

            if st.form_submit_button("Update Profile"):
                payload = {
                    "first_name": name,
                    "email": email,
                    "age": age,
                    "medical_history": history,
                }
                r = api_request("PUT", "profile/", payload)
                if r and r.status_code in [200, 201]:
                    st.success("Profile Updated!")
                else:
                    st.error("Failed to update profile.")
