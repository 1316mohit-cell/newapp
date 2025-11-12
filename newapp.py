"""
Multi-user Portfolio App (Streamlit + MongoDB Atlas)
File: streamlit_portfolio_app.py

Features:
- Signup / Login (passwords hashed with PBKDF2-HMAC-SHA256)
- Create / Edit user portfolio (name, bio, skills, projects, social links)
- Upload profile picture (stored as Base64 in MongoDB)
- View other users' portfolios from a searchable dropdown
- Data stored in MongoDB Atlas (use st.secrets or env var for MONGO_URI)

Usage:
1) Create a Streamlit secrets entry (recommended) or set env var MONGO_URI.
   In Streamlit Cloud, go to Settings → Secrets and add:
   {
     "MONGO_URI": "your-mongodb-connection-string"
   }

2) Install dependencies:
   pip install streamlit pymongo pillow

3) Run locally:
   streamlit run streamlit_portfolio_app.py

Notes:
- This implementation stores images as Base64 inside the user document in MongoDB.
- The app uses minimal design (clean layout) and keeps everything in a single file.
"""
import streamlit as st
from pymongo import MongoClient

# Access the secret key
mongo_uri = st.secrets["MONGO_URI"]

# Connect to MongoDB
client = MongoClient(mongo_uri)
db = client["your_database_name"]

import streamlit as st
from pymongo import MongoClient, ASCENDING
import base64
import io
from datetime import datetime
import hashlib
import os
import hmac
import json
from PIL import Image

# --------------------------- Configuration ---------------------------
# Get MongoDB URI from Streamlit secrets or environment variable
MONGO_URI = None
if st.secrets and "MONGO_URI" in st.secrets:
    MONGO_URI = st.secrets["MONGO_URI"]
else:
    MONGO_URI = os.environ.get("MONGO_URI")

if not MONGO_URI:
    st.error("MongoDB connection string not found. Set MONGO_URI in Streamlit secrets or environment variables.")
    st.stop()

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.get_database()  # default database from URI
users_col = db.get_collection("users")
# Ensure username is unique
users_col.create_index([("username", ASCENDING)], unique=True)

# --------------------------- Utilities ---------------------------
SALT_SIZE = 16
ITERATIONS = 100_000

def hash_password(password: str) -> str:
    """Return base64-encoded salt+hash"""
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
    st.session_state.user = None  # will store username

def login_user(username: str):
    st.session_state.user = username

def logout_user():
    st.session_state.user = None

# --------------------------- UI helpers ---------------------------
st.set_page_config(page_title="Portfolio Hub", layout="centered")

def small_header(text):
    st.markdown(f"<h2 style='margin-bottom: 6px'>{text}</h2>", unsafe_allow_html=True)

# Minimal CSS
st.markdown(
    "<style>\n    .card {padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); background: #fff;}\n    .skill {display:inline-block; padding:6px 10px; margin:4px; border-radius:16px; background:#f2f4f7; font-size:14px;}\n    a {text-decoration:none; color:#0366d6}\n    </style>",
    unsafe_allow_html=True,
)

# --------------------------- Auth: Signup / Login ---------------------------
with st.sidebar:
    st.title("Portfolio Hub")
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
                else:
                    try:
                        pw_hash = hash_password(su_password)
                        now = datetime.utcnow()
                        doc = {
                            "username": su_username.strip().lower(),
                            "full_name": su_name.strip(),
                            "email": su_email.strip(),
                            "password_hash": pw_hash,
                            "bio": "",
                            "skills": [],
                            "projects": [],
                            "social_links": {},
                            "profile_pic": None,  # base64
                            "created_at": now,
                            "updated_at": now,
                        }
                        users_col.insert_one(doc)
                        st.success("Account created — you can now log in.")
                    except Exception as e:
                        st.error(f"Could not create account: {e}")

        else:  # Login
            st.subheader("Welcome back")
            li_username = st.text_input("Username", key="li_username")
            li_password = st.text_input("Password", type="password", key="li_password")
            if st.button("Login"):
                if not li_username or not li_password:
                    st.warning("Enter username and password.")
                else:
                    user = users_col.find_one({"username": li_username.strip().lower()})
                    if not user:
                        st.error("Invalid username or password.")
                    else:
                        if verify_password(user["password_hash"], li_password):
                            login_user(user["username"])
                            st.success("Logged in!")
                            st.experimental_rerun()
                        else:
                            st.error("Invalid username or password.")

# --------------------------- Main App ---------------------------
st.title("Portfolio Hub — Explore creators")

col1, col2 = st.columns([2, 1])

with col1:
    st.header("Explore portfolios")
    search_term = st.text_input("Search by username or skill, or leave blank to list all")

    # Query users
    query = {}
    if search_term:
        term = search_term.strip().lower()
        query = {
            "$or": [
                {"username": {"$regex": term, "$options": "i"}},
                {"full_name": {"$regex": term, "$options": "i"}},
                {"skills": {"$elemMatch": {"$regex": term, "$options": "i"}}},
            ]
        }

    users = list(users_col.find(query, {"password_hash": 0}).sort("updated_at", -1))

    usernames = [u["username"] for u in users]
    selected_username = None
    if usernames:
        selected_username = st.selectbox("Select a user to view", ["-- choose --"] + usernames)
    else:
        st.info("No users found. Ask someone to sign up!")

    if selected_username and selected_username != "-- choose --":
        user_doc = users_col.find_one({"username": selected_username}, {"password_hash": 0})

        if user_doc:
            # Display clean portfolio
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
                st.write("\n")
                if user_doc.get("skills"):
                    st.markdown("**Skills**")
                    for s in user_doc.get("skills", []):
                        st.markdown(f"<span class='skill'>{s}</span>", unsafe_allow_html=True)
                st.write("\n")
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
        user_doc = users_col.find_one({"username": username}, {"password_hash": 0})
        st.markdown(f"**{user_doc.get('full_name') or username}**")
        if st.button("Edit my portfolio"):
            st.experimental_set_query_params(edit=username)
            st.experimental_rerun()

        st.markdown("---")
        st.write("Quick actions:")
        if st.button("Create sample portfolio (demo)"):
            # helpful for testing
            sample = {
                "full_name": "Demo User",
                "bio": "This is a sample portfolio created for demo.",
                "skills": ["Python", "Streamlit", "MongoDB"],
                "projects": [
                    {"title": "Demo Project", "description": "A demo project.", "link": "https://example.com"}
                ],
                "social_links": {"GitHub": "https://github.com/", "LinkedIn": ""},
                "updated_at": datetime.utcnow(),
            }
            users_col.update_one({"username": username}, {"$set": sample})
            st.success("Sample portfolio created.")
            st.experimental_rerun()

    else:
        st.info("Login or Signup from the left sidebar to create your portfolio.")

# --------------------------- Edit / Create Portfolio Page ---------------------------
params = st.experimental_get_query_params()
if "edit" in params and params.get("edit"):
    edit_username = params.get("edit")[0]
    if not st.session_state.user or st.session_state.user != edit_username:
        st.warning("You must be logged in as this user to edit their portfolio.")
    else:
        user_doc = users_col.find_one({"username": edit_username})
        st.header("Edit your portfolio")
        with st.form("portfolio_form"):
            full_name = st.text_input("Full name", value=user_doc.get("full_name", ""))
            bio = st.text_area("Bio / About", value=user_doc.get("bio", ""))
            skills_raw = st.text_input("Skills (comma separated)", value=",".join(user_doc.get("skills", [])))

            # Projects - simple add interface
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
                    st.success("Project added (saved temporarily). Scroll down and Save portfolio to persist.")
                    st.experimental_rerun()
                else:
                    st.warning("Project title required to add.")

        # show temp projects and allow removal
        if "projects_temp" in st.session_state and st.session_state.projects_temp:
            st.markdown("**Your projects (temporary list)**")
            for i, p in enumerate(st.session_state.projects_temp):
                colA, colB = st.columns([8,1])
                with colA:
                    st.markdown(f"**{p.get('title')}** — {p.get('description')}")
                with colB:
                    if st.button(f"Remove##{i}"):
                        st.session_state.projects_temp.pop(i)
                        st.experimental_rerun()

        # Profile image uploader
        st.markdown("---")
        st.markdown("**Profile picture**")
        img_file = st.file_uploader("Upload profile picture", type=["png","jpg","jpeg"]) 
        if img_file:
            img_bytes = img_file.read()
            st.image(img_bytes, use_column_width=False, width=150)

        # Social links
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
                "updated_at": datetime.utcnow(),
            }
            if img_file:
                # store base64
                updated["profile_pic"] = image_bytes_to_base64(img_bytes)
            else:
                # keep existing picture if present
                updated["profile_pic"] = user_doc.get("profile_pic")

            users_col.update_one({"username": edit_username}, {"$set": updated})
            st.success("Portfolio saved.")
            # clear temp
            if "projects_temp" in st.session_state:
                del st.session_state.projects_temp
            st.experimental_set_query_params()
            st.experimental_rerun()

# --------------------------- Footer ---------------------------
st.markdown("---")
st.caption("Built with Streamlit • Minimal & Clean • Data stored in MongoDB")

