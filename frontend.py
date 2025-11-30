import streamlit as st
import requests
from datetime import datetime
import os
import google.generativeai as genai
from dotenv import load_dotenv
import time
import threading
from utils import save_chat_history, load_history, clear_history
import schedule
import re
import textwrap

load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    st.error("❌ GEMINI_API_KEY غير موجود في متغيرات البيئة")
else:
    genai.configure(api_key=API_KEY)

SYSTEM_PROMPT = """
You are a medical assistant specialized in diabetes and hypertension.
Your tasks:
1. Provide safe medical guidance.
2. Interpret symptoms.
3. Offer lifestyle & nutrition tips.
4. Remind medication schedules.
Respond in the user's language automatically.
"""

MODEL_NAME = "models/gemini-2.0-flash"


def chat_with_gemini(prompt: str, context: str | None = None, intent: str | None = None) -> str:
    """Call the model with an optional retrieval context.

    If context is provided it will be inserted into the request so the model
    can answer using the retrieved facts.
    """
    model = genai.GenerativeModel(MODEL_NAME)

    # Build message body — keep system prompt first, add small intent instructions
    # If intent=='advice' the assistant should *not* produce model predictions
    # or numeric risk outputs — only provide guidance and recommend next steps.
    intent_text = ""
    if intent == 'advice':
        intent_text = (
            "\nAssistant behavior note: The user specifically asked for advice. "
            "Do NOT run predictions, give risk scores, or output any numerical classification. "
            "Focus on safe, actionable medical guidance, lifestyle suggestions, and next steps. "
            "If a prediction is explicitly requested, ask for permission and the required inputs.\n"
        )

    ctx_text = f"\nContext (from your data):\n{context}\n" if context else ""
    response = model.generate_content(f"{SYSTEM_PROMPT}{intent_text}{ctx_text}\nUser: {prompt}")
    return response.text


def clean_html(text):
    return re.sub("<.*?>", "", text)


def detect_chat_intent(text: str) -> str | None:
    """Very small rule-based intent detector for chat actions.

    returns: 'book_appointment', 'predict_diabetes', 'predict_bp', 'predict_heart' or None
    """
    t = (text or "").lower()

    # booking intent
    if any(k in t for k in ["book", "appointment", "حجز", "موعد", "احجز"]):
        return 'book_appointment'

    # advice intent (give tips, guidance, not predictions)
    if any(k in t for k in ["advice", "advise", "نصيحة", "نصايح", "نصائح", "ماذا أفعل", "ارشاد", "ارشادات", "نصيحتي", "نرجو نصائح"]):
        return 'advice'

    # diabetes / blood sugar
    if any(k in t for k in ["diabetes", "blood sugar", "sugar", "سكر", "hba1c", "hba1c"]):
        return 'predict_diabetes'

    # blood pressure
    if any(k in t for k in ["blood pressure", "pressure", "bp", "ضغط" ]):
        return 'predict_bp'

    # heart disease
    if any(k in t for k in ["heart", "cardio", "قلب", "heart disease", "cardio"]):
        return 'predict_heart'

    return None


def detect_dir(text):
    return "rtl" if any("\u0600" <= c <= "\u06FF" for c in text) else "ltr"


def remind_medication():
    st.toast("⏰ Reminder: Time to take your medication!", icon="💊")


def start_reminders():
    schedule.every(60).minutes.do(remind_medication)
    while True:
        schedule.run_pending()
        time.sleep(5)
if 'reminder_thread_started' not in st.session_state:
    threading.Thread(target=start_reminders, daemon=True).start()
    st.session_state['reminder_thread_started'] = True

# ---------------------------------------------------


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
        padding: 16px 26px;
        border-radius: 28px;
        background: linear-gradient(135deg, #ff7a8a, #ff3d80);
        color: white;
        font-size: 18px;
        font-weight: 600;
        border: none;
        box-shadow: 0 8px 18px rgba(255, 60, 110, 0.28);
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        margin-bottom: 12px;
    }

    .stButton>button:hover {
        transform: translateX(4px);
        box-shadow: 0 14px 28px rgba(255, 50, 120, 0.45);
        background: linear-gradient(135deg, #ff4c6a, #ff7f7f);
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
if 'messages' not in st.session_state: st.session_state['messages'] = []


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


def fetch_db_context(user_question: str) -> dict:
    """Gather a compact context from backend endpoints relevant to the current user.

    The function calls `profile/` and `appointments/mine/` and returns a short
    plain-text summary that will be injected into the model prompt.
    """
    if not st.session_state.get('token'):
        return ""  # no auth -> no personal context

    parts = []
    sources = []

    # 1) Profile
    profile = api_request("GET", "profile/")
    if profile and profile.status_code == 200:
        p = profile.json()
        sources.append('profile')
        parts.append(f"Name: {p.get('first_name', '')}")
        if 'age' in p:
            parts.append(f"Age: {p.get('age')}")
        if 'medical_history' in p and p.get('medical_history'):
            parts.append(f"Medical history: {p.get('medical_history')}")

    # 2) Appointments (recent)
    appts = api_request("GET", "appointments/mine/")
    if appts and appts.status_code == 200:
        a = appts.json()
        sources.append('appointments')
        if a:
            # include next/upcoming 3 appointments
            entries = []
            for item in a[:3]:
                doc = item.get('doctor', {})
                entries.append(f"{item.get('date')} {item.get('time')} with Dr. {doc.get('name', '')} ({doc.get('specialization','')}) - {item.get('reason','')}")
            if entries:
                parts.append("Upcoming appointments:\n" + "\n".join(entries))

    # 3) Doctors list (only fetch if user asked about doctors/availability)
    question = (user_question or "").lower()
    want_doctors = any(k in question for k in ["doctor", "doctors", "دكتور", "دكات", "available", "متاح", "specialization", "تخصص"])
    if want_doctors:
        docs_res = api_request("GET", "doctors/")
        if docs_res and docs_res.status_code == 200:
            docs = docs_res.json()
            # format available doctors
            if docs:
                sources.append('doctors')
                entries = []
                for d in docs[:10]:
                    # assume serializer returns name & specialization & available flag
                    name = d.get('name', '')
                    spec = d.get('specialization', '')
                    avail = d.get('available', True)
                    status = 'available' if avail else 'unavailable'
                    entries.append(f"Dr. {name} — {spec} ({status})")
                parts.append("Doctors:\n" + "\n".join(entries))

    # Fallback if nothing found
    if not parts:
        return {"text": "", "sources": []}

    # Short-circuit: include question to bias retrieval to relevant fields (optional)
    summary = "\n".join(parts)
    # When injecting into model, keep it concise
    return {"text": summary, "sources": sources}


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

        # restore any previously extracted values so they persist across reruns
        auto_name = st.session_state.get('auto_name', "")
        auto_age = st.session_state.get('auto_age', None)
        auto_gender = st.session_state.get('auto_gender', "")
        auto_address = st.session_state.get('auto_address', "")

        if uploaded_id is not None:
            # use_container_width replaces the deprecated use_column_width parameter
            st.image(uploaded_id, use_container_width=True)
            if st.button("Extract from ID"):
                # prepare a proper file tuple (filename, bytes, content_type) for requests
                filename = getattr(uploaded_id, 'name', 'id.jpg')
                content_type = getattr(uploaded_id, 'type', None)
                file_bytes = uploaded_id.getvalue()

                if content_type:
                    files = {"file": (filename, file_bytes, content_type)}
                else:
                    files = {"file": (filename, file_bytes)}

                res = api_request("POST", "ocr/extract-id/", files=files)

                # api_request returns None when it can't connect — provide clearer feedback
                if res is None:
                    st.error("Failed to extract info — no response from backend. Is the API running at http://127.0.0.1:8000/api/ ?")
                elif res.status_code == 200:
                    data = res.json()
                    st.success("ID Extracted Successfully!")

                    # persist extracted fields into session_state so the signup form can use them
                    st.session_state['auto_name'] = data.get("name", "")
                    st.session_state['auto_gender'] = data.get("gender", "")
                    st.session_state['auto_address'] = data.get("address", "")
                    st.session_state['auto_age'] = data.get("age", None)

                    # rerun to show the pre-filled fields in the signup form
                    st.experimental_rerun()
                else:
                    # show status and any returned message to help debugging
                    status = getattr(res, 'status_code', 'no response') if res else 'no response'
                    details = ''
                    try:
                        details = res.text if res is not None else ''
                    except Exception:
                        details = ''
                    st.error(f"Failed to extract info — status: {status}{' - ' + details if details else ''}")
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
    # Replace default sidebar radio menu with the new stacked pink 'Main Menu' buttons
    # Keep Logout working and map each button to an internal `selected_menu` state
    if st.sidebar.button("Logout"):
        handle_logout()

    # ensure we can persist selection across reruns
    if 'selected_menu' not in st.session_state:
        # default to profile or role-specific landing
        st.session_state['selected_menu'] = 'My Medical Profile' if st.session_state['role'] else 'My Medical Profile'

    # Visual 'Main Menu' heading
    st.sidebar.markdown("""
        <div style='color: white; font-weight:700; font-size:18px; margin-top:8px; margin-bottom:8px;'>
            Main Menu
        </div>
    """, unsafe_allow_html=True)

    # Create big buttons for the main actions (stacked as in the provided design)
    if st.sidebar.button("My Medical Profile"):
        st.session_state['selected_menu'] = 'My Medical Profile'
        st.rerun()

    if st.sidebar.button("Chat"):
        st.session_state['selected_menu'] = 'Chat'
        st.rerun()

    if st.sidebar.button("Prediction"):
        st.session_state['selected_menu'] = 'Prediction'
        st.rerun()

    if st.sidebar.button("Appointments"):
        st.session_state['selected_menu'] = 'Appointments'
        st.rerun()

    # Use selected_menu to decide what to render on the main area
    menu = st.session_state.get('selected_menu', 'My Medical Profile')

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
                        st.header("💬 AI Medical Assistant ")

                        if 'reminder_thread_started' not in st.session_state:
                            threading.Thread(target=start_reminders, daemon=True).start()
                            st.session_state['reminder_thread_started'] = True


                        chat_container = st.container(height=400, border=True)

                        for msg in st.session_state["messages"]:
                            if msg["role"] == "user":
                                # sanitize user text to avoid accidental HTML being rendered
                                safe_text = clean_html(msg['text'])
                                chat_container.markdown(f"""
                                        <div style="text-align:right; margin-bottom: 10px; padding: 10px; background-color: #2e8b57; border-radius: 10px; color: white;">
                                            <b>👤 You:</b> {safe_text}
                                        </div>
                                        """, unsafe_allow_html=True)
                            else:
                                # sanitize assistant messages to remove any stray HTML tags (eg. stray </div>)
                                safe_text = clean_html(msg['text'])
                                chat_container.markdown(f"""
                                        <div style="text-align:left; margin-bottom: 10px; padding: 10px; background-color: #1e1e2d; border-radius: 10px; color: #dddddd;">
                                            <b>🤖 Assistant:</b> {safe_text}
                                        </div>
                                        """, unsafe_allow_html=True)


                        # RAG is automatic: the app will fetch your profile/appointments and doctors
                        # when appropriate and inject that context into the LLM prompt.

                        user_msg = st.text_input("Type your message:",
                                                 placeholder="Symptoms, medication, diet...",
                                                 key="user_input")

                        send_button = st.empty()

                        if send_button.button("Send", use_container_width=True) and user_msg:
                            # store message immediately
                            st.session_state["messages"].append({"role": "user", "text": user_msg})

                            # detect intent — if booking/prediction intent, open inline form instead of calling LLM directly
                            intent = detect_chat_intent(user_msg)

                            # Only some detected intents require an interactive form
                            actionable_intents = {'book_appointment', 'predict_diabetes', 'predict_bp', 'predict_heart'}
                            if intent in actionable_intents:
                                # set pending intent and keep original message for context
                                st.session_state['pending_intent'] = intent
                                st.session_state['pending_user_msg'] = user_msg
                                # rerun so the UI shows the inline form
                                st.rerun()

                            # otherwise it's a normal chat message -> fetch context and ask LLM
                            with st.spinner("Thinking..."):
                                try:
                                    retrieval_result = fetch_db_context(user_msg)
                                    ctx_text = retrieval_result.get('text') if retrieval_result else None
                                    # pass detected intent to the LLM so it can adapt its response style
                                    reply = chat_with_gemini(user_msg, context=ctx_text, intent=intent)

                                    # If retrieval returned context, show a small badge listing sources
                                    if retrieval_result and retrieval_result.get('sources'):
                                        used = ", ".join(retrieval_result['sources'])
                                        st.info(f"🔎 Retrieved data included from: {used} — used to answer your question.")

                                    # Save a note that retrieval was used (tag in saved history)
                                    if retrieval_result and retrieval_result.get('text'):
                                        save_chat_history(clean_html(user_msg), clean_html(reply) + "\n\n[retrieved_context_used: " + ",".join(retrieval_result.get('sources', [])) + "]")
                                    else:
                                        save_chat_history(clean_html(user_msg), clean_html(reply))

                                except Exception as e:
                                    reply = f"⚠️ Error connecting to model: {e}"

                            st.session_state["messages"].append({"role": "bot", "text": reply})
                            st.rerun()


                        # If an intent was detected earlier and is pending, show the inline intent form
                        pending = st.session_state.get('pending_intent')
                        if pending:
                            st.markdown("---")
                            st.subheader("Action Required — follow-up info")

                            # Booking form
                            if pending == 'book_appointment':
                                if not st.session_state.get('token'):
                                    st.warning("Please login to book an appointment.")
                                    # clear pending
                                    st.session_state.pop('pending_intent', None)
                                    st.session_state.pop('pending_user_msg', None)
                                else:
                                    st.markdown("**I can book an appointment for you. Provide a few details below:**")
                                    # fetch doctors list
                                    docs_res = api_request('GET', 'doctors/')
                                    doctors = []
                                    if docs_res and docs_res.status_code == 200:
                                        doctors = docs_res.json()

                                    doc_map = {f"Dr. {d.get('name','')} ({d.get('specialization','')})": d.get('id') for d in doctors}

                                    with st.form('chat_booking_form'):
                                        selected = st.selectbox('Select Doctor', list(doc_map.keys()) if doc_map else ['No doctors available'])
                                        appt_date = st.date_input('Date')
                                        appt_time = st.time_input('Time')
                                        reason = st.text_area('Reason', value=st.session_state.get('pending_user_msg',''))
                                        if st.form_submit_button('Confirm Booking'):
                                            if not doc_map:
                                                st.error('No doctors available to book.')
                                            else:
                                                payload = { 'doctor_id': doc_map[selected], 'date': appt_date.strftime('%Y-%m-%d'), 'time': appt_time.strftime('%H:%M:%S'), 'reason': reason }
                                                res = api_request('POST','appointment/create/', payload)
                                                if res and res.status_code == 201:
                                                    st.success('✅ Appointment Booked!')
                                                    # append assistant reply
                                                    st.session_state['messages'].append({'role':'bot', 'text': f"Appointment booked with {selected} on {appt_date} at {appt_time}."})
                                                    save_chat_history(clean_html(st.session_state.get('pending_user_msg','')), f"Booked appointment: {selected} {appt_date} {appt_time}")
                                                    # clear pending
                                                    st.session_state.pop('pending_intent', None)
                                                    st.session_state.pop('pending_user_msg', None)
                                                    st.rerun()
                                                else:
                                                    st.error(f'Failed to book appointment: {res.text if res else "server error"}')

                            # Diabetes prediction
                            elif pending == 'predict_diabetes':
                                st.markdown('**Blood Sugar (Diabetes) prediction — fill required fields:**')
                                with st.form('chat_diabetes_form'):
                                    year = st.number_input('Year of Birth', min_value=1900, max_value=2025, value=2000)
                                    gender = st.selectbox('Gender', ['Male','Female'])
                                    gender_val = 1 if gender == 'Male' else 0
                                    age = st.number_input('Age', min_value=0, max_value=120, value=30)
                                    race = st.selectbox('Race', ['African', 'American', 'Asian', 'Caucasian', 'Hispanic', 'Other'])
                                    hypertension = st.selectbox('Hypertension', ['Yes','No'])
                                    heart_disease = st.selectbox('Heart Disease', ['Yes','No'])
                                    smoking_history = st.selectbox('Smoking History', ['Never','Former','Current'])
                                    bmi = st.number_input('BMI', min_value=0.0, max_value=100.0, value=25.0)
                                    hba1c_level = st.number_input('HbA1c Level (%)', min_value=0.0, max_value=20.0, value=5.5)
                                    blood_glucose_level = st.number_input('Blood Glucose Level (mg/dL)', min_value=0.0, max_value=500.0, value=100.0)
                                    if st.form_submit_button('Run Diabetes Prediction'):
                                        payload = { 'year': year, 'gender': gender_val, 'age': age, 'race': race, 'hypertension': 1 if hypertension=='Yes' else 0, 'heart_disease': 1 if heart_disease=='Yes' else 0, 'smoking_history': smoking_history, 'bmi': bmi, 'hba1c_level': hba1c_level, 'blood_glucose_level': blood_glucose_level }
                                        res = api_request('POST','predict/diabetes/', payload)
                                        if res and res.status_code==200:
                                            data = res.json(); pred = data.get('prediction',0)
                                            out = 'High Diabetes Risk' if pred==1 else 'Low Diabetes Risk'
                                            st.success(f'Prediction: {out}')
                                            st.session_state['messages'].append({'role':'bot','text': f'Diabetes prediction: {out}'})
                                            # clear pending
                                            st.session_state.pop('pending_intent', None)
                                            st.session_state.pop('pending_user_msg', None)
                                            st.rerun()
                                        else:
                                            st.error('Prediction failed — check backend')

                            # Blood pressure prediction
                            elif pending == 'predict_bp':
                                st.markdown('**Blood Pressure prediction — provide the measurements:**')
                                with st.form('chat_bp_form'):
                                    age = st.number_input('Age', min_value=1, max_value=120, value=30)
                                    gender = st.selectbox('Gender', ['Male','Female'])
                                    gender_val = 1 if gender=='Male' else 0
                                    height = st.number_input('Height (cm)', min_value=50, max_value=250, value=170)
                                    weight = st.number_input('Weight (kg)', min_value=10, max_value=300, value=70)
                                    ap_hi = st.number_input('Systolic BP (ap_hi)', min_value=50, max_value=250, value=120)
                                    ap_lo = st.number_input('Diastolic BP (ap_lo)', min_value=30, max_value=150, value=80)
                                    cholesterol = st.selectbox('Cholesterol Level', [1,2,3])
                                    gluc = st.selectbox('Glucose Level', [1,2,3])
                                    smoke = st.selectbox('Smokes?', [0,1])
                                    alco = st.selectbox('Alcohol Intake?', [0,1])
                                    heart_disease = st.selectbox('Heart Disease?', [0,1])
                                    if st.form_submit_button('Run BP Prediction'):
                                        payload = { 'age': age, 'gender': gender_val, 'height': height, 'weight': weight, 'ap_hi': ap_hi, 'ap_lo': ap_lo, 'cholesterol': cholesterol, 'gluc': gluc, 'smoke': smoke, 'alco': alco, 'heart_disease': heart_disease }
                                        res = api_request('POST','predict/heart/', payload)
                                        if res and res.status_code==200:
                                            prediction = res.json().get('prediction',0)
                                            # Determine BP level here too
                                            if ap_hi >= 140 or ap_lo >= 90:
                                                bp_level = 'High Blood Pressure (Hypertension)'
                                            elif ap_hi < 90 or ap_lo < 60:
                                                bp_level = 'Low Blood Pressure'
                                            else:
                                                bp_level = 'Normal Blood Pressure'
                                            heart_risk_msg = 'High Risk of Heart Disease' if prediction==1 else 'Low Risk of Heart Disease'
                                            st.success(f'Results: {bp_level} — {heart_risk_msg}')
                                            st.session_state['messages'].append({'role':'bot','text': f'BP results: {bp_level}; Heart risk: {heart_risk_msg}'})
                                            st.session_state.pop('pending_intent', None)
                                            st.session_state.pop('pending_user_msg', None)
                                            st.rerun()
                                        else:
                                            st.error('Prediction failed — check backend')

                            # Heart disease prediction
                            elif pending == 'predict_heart':
                                st.markdown('**Heart disease prediction — provide required fields:**')
                                with st.form('chat_heart_form'):
                                    age = st.number_input('Age', min_value=1, max_value=120, value=40)
                                    gender = st.selectbox('Gender', ['Male','Female'])
                                    gender_val = 1 if gender=='Male' else 0
                                    height = st.number_input('Height (cm)', min_value=50, max_value=250, value=170)
                                    weight = st.number_input('Weight (kg)', min_value=10, max_value=300, value=70)
                                    ap_hi = st.number_input('Systolic BP (ap_hi)', min_value=50, max_value=250, value=120)
                                    ap_lo = st.number_input('Diastolic BP (ap_lo)', min_value=30, max_value=150, value=80)
                                    cholesterol = st.selectbox('Cholesterol Level', [1,2,3])
                                    gluc = st.selectbox('Glucose Level', [1,2,3])
                                    smoke = st.selectbox('Smokes?', [0,1])
                                    alco = st.selectbox('Alcohol Intake?', [0,1])
                                    active = st.selectbox('Physical Activity?', [0,1])
                                    if st.form_submit_button('Run Heart Prediction'):
                                        payload = { 'age': age, 'gender': gender_val, 'height': height, 'weight': weight, 'ap_hi': ap_hi, 'ap_lo': ap_lo, 'cholesterol': cholesterol, 'gluc': gluc, 'smoke': smoke, 'alco': alco, 'active': active }
                                        res = api_request('POST','predict/heart/', payload)
                                        if res and res.status_code==200:
                                            prediction = res.json().get('prediction',0)
                                            out = 'High Risk of Heart Disease' if prediction==1 else 'Low Risk of Heart Disease'
                                            st.success(f'Prediction: {out}')
                                            st.session_state['messages'].append({'role':'bot','text': f'Heart disease prediction: {out}'})
                                            st.session_state.pop('pending_intent', None)
                                            st.session_state.pop('pending_user_msg', None)
                                            st.rerun()
                                        else:
                                            st.error('Prediction failed — check backend')

                        st.divider()
                        st.subheader("💾 Saved History (File)")

                        if st.button("🗑️ Clear All Saved History"):
                            clear_history()
                            st.success("History cleared successfully!")
                            time.sleep(1)
                            st.rerun()

                        history = load_history()

                        if history:
                            for h in reversed(history[-5:]):
                                st.markdown(f"**{h['user']}**", help=f"AI: {h['bot']}")
                        else:
                            st.caption("No saved conversations in file.")
    elif menu == "Prediction":

        st.header("🔮 Prediction Center")
        st.write("Choose a prediction tool below:")

        if st.button("🩺 Blood Sugar Check"):
            st.session_state['selected_menu'] = 'Blood Sugar Check'
            st.rerun()

        if st.button("💓 Blood Pressure Check"):
            st.session_state['selected_menu'] = 'Blood Pressure Check'
            st.rerun()

        if st.button("❤️ Heart Disease Check"):
            st.session_state['selected_menu'] = 'Heart Disease Check'
            st.rerun()

        if st.button("🧠 Brain Tumor Scan"):
            st.session_state['selected_menu'] = 'Brain Tumor Scan'
            st.rerun()

    elif menu == "Appointments":

        st.header("📅 Appointments")
        # For patients offer both booking and viewing their appointments
        if st.session_state.get('role') == 'patient':
            if st.button("Book Appointment"):
                st.session_state['selected_menu'] = 'Book Appointment'
                st.rerun()

            if st.button("My Appointments"):
                st.session_state['selected_menu'] = 'My Appointments'
                st.rerun()
        else:
            # For doctors we go directly to their appointments list
            st.session_state['selected_menu'] = 'My Appointments'
            st.rerun()

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
                data = res.json()
                prediction = data.get("prediction", 0)  # Default 0 if missing

                if prediction == 1:
                    risk = "High Diabetes Risk"
                    color = "#b30000"
                else:
                    risk = "Low Diabetes Risk"
                    color = "#009933"
            else:
                st.error("Prediction failed — check backend")
                st.stop()

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
            st.image(uploaded_image, caption="Uploaded MRI", use_container_width=True)

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
