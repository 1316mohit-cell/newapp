"""
Multi-user Portfolio App (Streamlit + Local JSON Database)
File: streamlit_portfolio_local.py

Features:
- Signup / Login (passwords hashed with PBKDF2-HMAC-SHA256)
- Create / Edit user portfolio (name, bio, skills, projects, social links)
- Upload profile picture (stored as Base64 in local JSON)
- View other users' portfolios from a searchable dropdown
- Data stored locally (users_db.json)

Usage:
1) Install dependencies:
   pip install streamlit pillow

2) Run:
   streamlit run streamlit_portfolio_local.py
"""

import streamlit as st
import base64
import io
import os
import json
import hashlib
import hmac
from datetime import datetime
from PIL import Image

# --------------------------- Configuration ---------------------------
DB_FILE = "users_db.json"

def load_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump([], f)
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def find_user(username):
    db = load_db()
    for user in db:
        if user["username"] == username.lower():
            return user
    return None

def update_user(username, updated_fields):
    db = load_db()
    for i, user in enumerate(db):
        if user["username"] == username.lower():
            db[i].update(updated_fields)
            save_db(db)
            return
    raise ValueError("User not found")

# --------------------------- Utilities ---------------------------
SALT_SIZE = 16
ITERATIONS = 100_000

def hash_password(password: str) -> str:
    salt = os.urandom(SALT_SIZE)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return base64.b64encode(salt + key).decode("utf-8")

def verify_password(stored_b64: str, password: str) -> bool:
    data = base64.b64decode(stored_b64.encode("utf-8"))
    salt = data[:SALT_SIZE]
    key_stored = data[SALT_SIZE:]
    key_new = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return hmac.compare_digest(key_stored, key_new)

def image_bytes_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")

def base64_to_image(b64: str) -> Image.Image:
    img_bytes = base64.b64decode(b64.encode("utf-8"))
    return Image.open(io.BytesIO(img_bytes))

# --------------------------- Session helpers ---------------------------
if "user" not in st.session_state:
    st.session_state.user = None

def login_user(username: str):
    st.session_state.user = username

def logout_user():
    st.session_state.user = None

# --------------------------- UI ---------------------------
st.set_page_config(page_title="Portfolio Hub (Local)", layout="centered")

def small_header(text):
    st.markdown(f"<h2 style='margin-bottom: 6px'>{text}</h2>", unsafe_allow_html=True)

st.markdown(
    "<style>\n    .card {padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); background: #fff;}\n    .skill {display:inline-block; padding:6px 10px; margin:4px; border-radius:16px; background:#f2f4f7; font-size:14px;}\n    a {text-decoration:none; color:#0366d6}\n    </style>",
    unsafe_allow_html=True,
)

# --------------------------- Auth ---------------------------
with st.sidebar:
    st.title("Portfolio Hub (Local)")
    if st.session_state.user:
        st.write(f"Logged in as **{st.session_state.user}**")
        if st.button("Logout"):
            logout_user()
            st.experimental_rerun()
        st.markdown("---")
        st.write("Go to the main page to edit or view portfolios.")
    else:
        auth_mode = st.radio("Auth", ("Login", "Signup"))

        if auth_mode == "Signup":
            st.subheader("Create account")
            su_username = st.text_input("Choose a username", key="su_username")
            su_name = st.text_input("Full name", key="su_name")
            su_email = st.text_input("Email (optional)", key="su_email")
            su_password = st.text_input("Password", type="password", key="su_password")
            su_confirm = st.text_input("Confirm password", type="password", key="su_confirm")

            if st.button("Sign up"):
                if not su_username or not su_password:
                    st.warning("Please provide username and password.")
                elif su_password != su_confirm:
                    st.warning("Passwords don't match.")
                elif find_user(su_username):
                    st.warning("Username already exists.")
                else:
                    pw_hash = hash_password(su_password)
                    now = datetime.utcnow().isoformat()
                    doc = {
                        "username": su_username.strip().lower(),
                        "full_name": su_name.strip(),
                        "email": su_email.strip(),
                        "password_hash": pw_hash,
                        "bio": "",
                        "skills": [],
                        "projects": [],
                        "social_links": {},
                        "profile_pic": None,
                        "created_at": now,
                        "updated_at": now,
                    }
                    db = load_db()
                    db.append(doc)
                    save_db(db)
                    st.success("Account created — you can now log in.")

        else:
            st.subheader("Welcome back")
            li_username = st.text_input("Username", key="li_username")
            li_password = st.text_input("Password", type="password", key="li_password")
            if st.button("Login"):
                user = find_user(li_username)
                if not user:
                    st.error("Invalid username or password.")
                elif verify_password(user["password_hash"], li_password):
                    login_user(user["username"])
                    st.success("Logged in!")
                    st.experimental_rerun()
                else:
                    st.error("Invalid username or password.")

# --------------------------- Main App ---------------------------
st.title("Portfolio Hub — Explore creators")

col1, col2 = st.columns([2, 1])
db = load_db()

with col1:
    st.header("Explore portfolios")
    search_term = st.text_input("Search by username or skill, or leave blank to list all")

    users = db
    if search_term:
        term = search_term.strip().lower()
        users = [
            u for u in db
            if term in u["username"].lower()
            or term in u.get("full_name", "").lower()
            or any(term in s.lower() for s in u.get("skills", []))
        ]

    usernames = [u["username"] for u in users]
    selected_username = None
    if usernames:
        selected_username = st.selectbox("Select a user to view", ["-- choose --"] + usernames)
    else:
        st.info("No users found.")

    if selected_username and selected_username != "-- choose --":
        user_doc = find_user(selected_username)
        if user_doc:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            left, right = st.columns([1, 3])
            with left:
                if user_doc.get("profile_pic"):
                    try:
                        img = base64.b64decode(user_doc["profile_pic"].encode("utf-8"))
                        st.image(img, use_column_width=True, output_format='PNG')
                    except Exception:
                        st.write("[Image cannot be displayed]")
                else:
                    st.write("No profile image")

            with right:
                st.markdown(f"### {user_doc.get('full_name') or user_doc.get('username')}")
                if user_doc.get("bio"):
                    st.write(user_doc.get("bio"))
                if user_doc.get("skills"):
                    st.markdown("**Skills**")
                    for s in user_doc.get("skills", []):
                        st.markdown(f"<span class='skill'>{s}</span>", unsafe_allow_html=True)
                if user_doc.get("projects"):
                    st.markdown("**Projects**")
                    for p in user_doc.get("projects", []):
                        st.markdown(f"**{p.get('title')}**")
                        if p.get("description"):
                            st.write(p.get("description"))
                        if p.get("link"):
                            st.markdown(f"[Project Link]({p.get('link')})")
                        st.write("---")
                if user_doc.get("social_links"):
                    st.markdown("**Social**")
                    for k, v in user_doc.get("social_links", {}).items():
                        if v:
                            st.markdown(f"- [{k}]({v})")
            st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.header("Your account")
    if st.session_state.user:
        username = st.session_state.user
        user_doc = find_user(username)
        st.markdown(f"**{user_doc.get('full_name') or username}**")
        if st.button("Edit my portfolio"):
            st.experimental_set_query_params(edit=username)
            st.experimental_rerun()
        if st.button("Create sample portfolio (demo)"):
            sample = {
                "full_name": "Demo User",
                "bio": "This is a sample portfolio created for demo.",
                "skills": ["Python", "Streamlit", "LocalDB"],
                "projects": [
                    {"title": "Demo Project", "description": "A demo project.", "link": "https://example.com"}
                ],
                "social_links": {"GitHub": "https://github.com/", "LinkedIn": ""},
                "updated_at": datetime.utcnow().isoformat(),
            }
            update_user(username, sample)
            st.success("Sample portfolio created.")
            st.experimental_rerun()
    else:
        st.info("Login or Signup from the left sidebar to create your portfolio.")

# --------------------------- Edit Portfolio ---------------------------
params = st.experimental_get_query_params()
if "edit" in params and params.get("edit"):
    edit_username = params.get("edit")[0]
    if not st.session_state.user or st.session_state.user != edit_username:
        st.warning("You must be logged in as this user to edit their portfolio.")
    else:
        user_doc = find_user(edit_username)
        st.header("Edit your portfolio")

        with st.form("portfolio_form"):
            full_name = st.text_input("Full name", value=user_doc.get("full_name", ""))
            bio = st.text_area("Bio / About", value=user_doc.get("bio", ""))
            skills_raw = st.text_input("Skills (comma separated)", value=",".join(user_doc.get("skills", [])))

            st.markdown("**Add a project**")
            p_title = st.text_input("Project title")
            p_desc = st.text_area("Project description")
            p_link = st.text_input("Project link (optional)")
            if "projects_temp" not in st.session_state:
                st.session_state.projects_temp = user_doc.get("projects", [])

            if st.form_submit_button("Add project"):
                if p_title:
                    st.session_state.projects_temp.append({
                        "title": p_title,
                        "description": p_desc,
                        "link": p_link,
                    })
                    st.success("Project added (temporarily). Save to persist.")
                    st.experimental_rerun()

        if "projects_temp" in st.session_state and st.session_state.projects_temp:
            st.markdown("**Your projects**")
            for i, p in enumerate(st.session_state.projects_temp):
                colA, colB = st.columns([8, 1])
                with colA:
                    st.markdown(f"**{p.get('title')}** — {p.get('description')}")
                with colB:
                    if st.button(f"Remove##{i}"):
                        st.session_state.projects_temp.pop(i)
                        st.experimental_rerun()

        st.markdown("---")
        st.markdown("**Profile picture**")
        img_file = st.file_uploader("Upload profile picture", type=["png","jpg","jpeg"]) 
        if img_file:
            img_bytes = img_file.read()
            st.image(img_bytes, use_column_width=False, width=150)

        github = st.text_input("GitHub URL", value=user_doc.get("social_links", {}).get("GitHub", ""))
        linkedin = st.text_input("LinkedIn URL", value=user_doc.get("social_links", {}).get("LinkedIn", ""))
        website = st.text_input("Website URL", value=user_doc.get("social_links", {}).get("Website", ""))

        if st.button("Save portfolio"):
            updated = {
                "full_name": full_name.strip(),
                "bio": bio.strip(),
                "skills": [s.strip() for s in skills_raw.split(",") if s.strip()],
                "projects": st.session_state.get("projects_temp", user_doc.get("projects", [])),
                "social_links": {"GitHub": github.strip(), "LinkedIn": linkedin.strip(), "Website": website.strip()},
                "updated_at": datetime.utcnow().isoformat(),
            }
            if img_file:
                updated["profile_pic"] = image_bytes_to_base64(img_bytes)
            else:
                updated["profile_pic"] = user_doc.get("profile_pic")

            update_user(edit_username, updated)
            st.success("Portfolio saved.")
            if "projects_temp" in st.session_state:
                del st.session_state.projects_temp
            st.experimental_set_query_params()
            st.experimental_rerun()

st.markdown("---")
st.caption("Built with Streamlit • Local Storage Version • Minimal & Clean")
