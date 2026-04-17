# =============================================================================
# SAMPLE ORDER SYNC | Introduction
# =============================================================================
#   Welcome to Sample Order Sync (SOS), an app developed for BFH-HAFL and it's soil lab. It aims to ease the process of ordering soil sample analyses for both customers and lab personnel.
#   Main features of the app: Role based user management - Dashboard with statistical metrices to faster assess lab work load - Guided wizard with both Excel and/or manual sample input -
#   Database managed processing of orders, samples, analysis methods and reporting - Catalog of provided methods - Lab information - Simple and easy transfer of data with audit trail.
#
#   Main developer: Simon Heiniger, BFH-HAFL (hgs5@bfh.ch)
#   Alpha tester: Daniel Wächter, ZHAW; Franziska Büeler BFH-HAFL
#   Beta tester: tbd

# =============================================================================
# app.py
# =============================================================================
#
#   Main Application Entry Point: app.py
#   ------------------------------------
#   This module serves as the primary orchestrator for the Sample Order Sync application.
#   It manages the high-level application lifecycle and integrates the following core components:
#
#   1. AUTHENTICATION & RBAC: Implements the login/registration gatekeeper and handles
#       Role-Based Access Control (RBAC) to distinguish between Lab Admins and Customers.
#
#   2. STATE PERSISTENCE: Manages the 'st.session_state' to ensure data continuity
#       across the multi-step ordering wizard and administrative dashboards.
#
#   3. ROUTING & NAVIGATION: Controls the conditional rendering of the UI based on
#       the user's navigation choice (Dashboard, Wizard, Catalog, Admin Tools).
#
#   4. UI/UX FRAMEWORK: Defines the global layout, including the sidebar, header
#       logic, language localization (i18n), and error handling wrappers.
#
#   5. BUSINESS LOGIC INTEGRATION: Acts as the bridge between the frontend (Streamlit),
#       the backend processing (logic.py), and the database layer (database.py).
#

# =============================================================================
# Library import
# =============================================================================

import streamlit as st
import pandas as pd
import time
import re
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from xhtml2pdf import pisa
import io

# =============================================================================
# Module import
# =============================================================================

from database import SessionLocal, init_db, User, Order, Sample
from translation import t
from logic import ORDER_STATUSES, STATUS_COLORS, notify_user_status_change
from ui_assets import inject_custom_css, get_logo_html, get_footer_html
from ui_wizard import render_wizard_page, method_catalog_view
from ui.ui_dashboard import render_dashboard_fragment
from ui.ui_management import admin_reporting_view, admin_user_view

# =============================================================================
# Version log
# =============================================================================

APP_VERSION = "0.4.0 - beta"
RELEASE_DATE = "16.04.2026"
CONTACT_INFO = "hgs5@bfh.ch"

# =============================================================================
# Development mode
# =============================================================================
#   Skips loginpage at rerun during development stages.
#   !!! Change DEPLOY_STATE = "deployed" before release

# * (python -m) streamlit run app.py

DEPLOY_STATE = "deployed"  # !!!

# =============================================================================
# Initialisign database (Further information -> database.py)
# =============================================================================
init_db()


# =============================================================================
# Seeding of Sysadmin
# =============================================================================
# ! Potential risk of SECURITY LEAKS, make sure to change PW after start-up and roll-out
def seed_initial_admin():
    session = SessionLocal()
    try:
        if session.query(User).count() == 0:
            admin_user = User(
                email="admin@bfh.ch",
                first_name="System",
                last_name="Admin",
                password=generate_password_hash("admin"),
                role="superadmin",
                department="LIMS IT",
                is_active=True,
            )
            session.add(admin_user)
            session.commit()
    finally:
        session.close()


seed_initial_admin()

# =============================================================================
# Browser Icon
# =============================================================================
# ! No st.xxxxx code above this block !
st.set_page_config(
    page_title="SAMPLE ORDER SYNC",
    page_icon="assets/sample_order_sync_tab_icon.png",
    layout="wide",
)


# =============================================================================
# Alphanumerical Natural Sorting
# =============================================================================
# Helper function for UI lists to appear in natural order rather than lexicographical
def natural_sort_key(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", str(text))]


# =============================================================================
# Session State & Appliation Memory Initialization
# =============================================================================
#   Central memory registration for user session_states. Prevents memory loss and
#   acts as source of truth for the code.
def ensure_session_state():
    defaults = {
        "page": "login",
        "auth_mode": "login",
        "language": "de",
        "role": "user",
        "username": "",
        "user_id": None,
        "user_email": "",
        "wizard_step": 1,
        "samples": [],
        "selected_preparation": [],
        "selected_analyses": [],
        "analysis_packages": [],
        "validation_errors": [],
        "pending_df": None,
        "uploaded_file_name": None,
        "customer_note": "",
    }

    #   Fast-Pass for developers, if environment is set to "dev", bypasses the login and initiates a session
    #   as default Sysadmin
    if DEPLOY_STATE == "dev" and "user_id" not in st.session_state:
        session = SessionLocal()
        try:
            admin = session.query(User).filter_by(role="superadmin").first()
            if admin:
                defaults.update(
                    {
                        "role": admin.role,
                        "user_email": admin.email,
                        "username": f"{admin.first_name} {admin.last_name}",
                        "user_id": admin.id,
                        "page": "dashboard",
                    }
                )
        finally:
            session.close()
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


ensure_session_state()


# =============================================================================
# Persistent Language Selector
# =============================================================================
#   Manages multilingual app framework with seamless transition between languages. Languages is written
#   into database so language settings is persistent for users.


def render_language_selector():
    lang_map = {"de": "Deutsch", "fr": "Français"}
    inv_lang_map = {v: k for k, v in lang_map.items()}

    if "language" not in st.session_state or st.session_state.language not in lang_map:
        if st.session_state.get("language") == "Deutsch":
            st.session_state.language = "de"
        else:
            st.session_state.language = "de"

    current_key = st.session_state.language
    current_label = lang_map[current_key]

    langs_labels = list(lang_map.values())
    curr_idx = langs_labels.index(current_label)

    sel_label = st.sidebar.selectbox(
        t("lang_label"), langs_labels, index=curr_idx, key="widget_lang_selector"
    )

    new_key = inv_lang_map[sel_label]

    if new_key != st.session_state.language:
        st.session_state.language = new_key

        if st.session_state.get("user_id"):
            try:
                session = SessionLocal()
                user = session.query(User).get(st.session_state.user_id)
                if user:
                    user.language_set = new_key
                    session.commit()
                session.close()

            except Exception as e:
                print(f"{t('error_lang_save')}: {e}")

        st.rerun()


# =============================================================================
# Caching for perfomance optimisation & role bases access
# =============================================================================
#   Fetching of user related/relevant data in a single trip, easing strain on database.
#   Managing access to order data, where superadmin/admin see all orders regular users only
#   see theirs. enforcing security at data layer basis.
@st.cache_data(ttl=300)
def get_orders_data_cached(user_id, role):
    session = SessionLocal()

    try:
        query = (
            session.query(Order)
            .options(joinedload(Order.user), joinedload(Order.samples))
            .order_by(Order.created_at.desc())
        )
        if role not in ["admin", "superadmin"]:
            query = query.filter_by(user_id=user_id)
        orders = query.all()
        result = []

        for o in orders:
            result.append(
                {
                    "id": o.id,
                    "order_number": o.order_number if o.order_number else f"#{o.id}",
                    "project_name": o.project_name,
                    "psp_element": o.psp_element,
                    "status": o.status,
                    "created_at": o.created_at,
                    "completed_at": o.completed_at,
                    "sample_count": len(o.samples),
                    "user_fullname": (
                        f"{o.user.first_name} {o.user.last_name}"
                        if o.user
                        else "Unbekannt"
                    ),
                    "user_email": o.user.email if o.user else "",
                    "user_dept": o.user.department if o.user else "",
                    "has_report": o.result_file_blob is not None,
                    "file_name": o.result_file_name,
                    "customer_note": o.customer_note,
                    "lab_note": o.lab_note,
                    "samples": [
                        {
                            "preparation": s.cat_preparation,
                            "methods": s.cat_analyses,
                            "name": s.customer_sample_name,
                            "material": s.material_type,
                            "external_id": s.external_id,
                        }
                        for s in o.samples
                    ],
                }
            )
        return result

    finally:
        session.close()


# =============================================================================
# Login, Registration & Recovery
# =============================================================================
def login_page():
    render_language_selector()
    _, center, _ = st.columns([1, 2, 1])

    with center:
        st.title(f"{t('portal_title')}")

        if st.session_state.auth_mode == "login":
            st.markdown(f"### {t('auth_login_header')}")
            with st.form("login_form"):
                email = st.text_input(t("email")).strip()
                password = st.text_input(t("password"), type="password")
                if st.form_submit_button(
                    t("login_btn"), type="primary", width="stretch"
                ):
                    session = SessionLocal()
                    user = session.query(User).filter_by(email=email).first()

                    if user and check_password_hash(user.password, password):
                        if user.is_active:
                            st.session_state.update(
                                {
                                    "user_id": user.id,
                                    "user_email": user.email,
                                    "username": f"{user.first_name} {user.last_name}",
                                    "role": user.role,
                                    "page": "dashboard",
                                    "language": (
                                        user.language_set
                                        if user.language_set
                                        else "Deutsch"
                                    ),
                                }
                            )
                            st.rerun()

                        else:
                            st.warning(t("user_pending"))

                    else:
                        st.error(t("err_login_failed"))
                    session.close()
            col_l, col_r = st.columns(2)

            if col_l.button(t("no_account"), width="stretch"):
                st.session_state.auth_mode = "register"
                st.rerun()

            if col_r.button(t("forgot_pw"), width="stretch"):
                st.session_state.auth_mode = "forgot_password"
                st.rerun()

        elif st.session_state.auth_mode == "forgot_password":
            st.markdown(f"### {t('forgot_pw')}")
            st.write(t("forgot_pw_instruction"))
            with st.form("forgot_pw_form"):
                email = st.text_input(t("email")).strip()
                if st.form_submit_button(
                    "Reset anfordern", type="primary", width="stretch"
                ):
                    session = SessionLocal()
                    user = session.query(User).filter_by(email=email).first()
                    if user:
                        user.password_reset_requested = True
                        session.commit()
                        st.success(t("reset_req_sent"))
                        time.sleep(2)
                        st.session_state.auth_mode = "login"
                        st.rerun()
                    else:
                        st.error(t("email_not_found"))
                    session.close()
            if st.button(t("back_login"), width="stretch"):
                st.session_state.auth_mode = "login"
                st.rerun()

        elif st.session_state.auth_mode == "register":
            st.markdown(t("auth_register_header"))
            with st.form("reg_form"):
                fn = st.text_input(t("first_name"))
                ln = st.text_input(t("last_name"))
                em = st.text_input(t("email")).strip()
                pw = st.text_input(t("password"), type="password")
                dp = st.text_input(t("dept"))
                if st.form_submit_button(t("btn_send"), type="primary"):
                    if not (fn and ln and em and pw and dp):
                        st.error(t("error_fields"))
                    else:
                        session = SessionLocal()
                        try:
                            existing = session.query(User).filter_by(email=em).first()
                            if existing:
                                st.error(t("mail_already_exists"))
                            else:
                                new_user = User(
                                    email=em,
                                    first_name=fn,
                                    last_name=ln,
                                    password=generate_password_hash(pw),
                                    department=dp,
                                    is_active=False,
                                    role="user",
                                )
                                session.add(new_user)
                                session.commit()
                                st.success(t("msg_registration_send"))
                                time.sleep(1.5)
                                st.session_state.auth_mode = "login"
                                st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"{t("error")}: {e}")
                        finally:
                            session.close()
            if st.button(t("btn_back")):
                st.session_state.auth_mode = "login"
                st.rerun()


# =============================================================================
# TAB | Profile for users to change PW
# =============================================================================
#   TODO implementing further features like changing e-mail, departement, etc.
def render_profile_tab():
    st.subheader(t("tab_profile"))
    with st.form("change_password_form"):
        st.markdown(f"**{t('change_pw_header')}**")
        old_pw = st.text_input(t("old_pw"), type="password")
        new_pw = st.text_input(t("new_pw"), type="password")
        confirm_pw = st.text_input(t("confirm_pw"), type="password")
        if st.form_submit_button(t("save_changes"), type="primary"):
            if new_pw != confirm_pw:
                st.error(t("pw_mismatch"))
            elif not new_pw:
                st.error(t("error_fields"))
            else:
                session = SessionLocal()
                user = session.query(User).get(st.session_state.user_id)
                if user and check_password_hash(user.password, old_pw):
                    user.password = generate_password_hash(new_pw)
                    session.commit()
                    st.success(t("pw_updated"))
                else:
                    st.error(t("pw_wrong_old"))
                session.close()


# =============================================================================
# TAB | Lab information
# =============================================================================
#   ! Needs to be moved to logic.py and translation.py for logic integrity. But did not feel like it, yet...
def render_labor_info():

    st.markdown(f"### {t('lab_info_header')}")
    st.write(t("lab_info_intro"))
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**👤 {t('lab_info_contact_person')}**")
        st.markdown(t("lab_info_personnel"))
        st.divider()
        st.markdown(f"**📍 {t('lab_info_location')}**")

    with col2:
        st.markdown(f"**⏰ {t('lab_info_opening_hours')}**")

    st.divider()

    with st.container():
        st.caption(f"**{t('lab_info_imprint_text')}**")
        st.markdown(f"#### Impressum")


# =============================================================================
# TAB | Main dashboard with statistical metrices
# =============================================================================
def dashboard_page():
    inject_custom_css()

    with st.sidebar:
        st.markdown(get_logo_html(), unsafe_allow_html=True)
        render_language_selector()
        st.divider()
        st.markdown(f"👤 **{st.session_state.username}** ({st.session_state.role})")

        if st.button(t("logout"), type="primary", width="stretch"):
            st.session_state.page = "login"
            st.rerun()
        st.markdown(
            get_footer_html(
                t("Version"),
                APP_VERSION,
                t("Release date"),
                RELEASE_DATE,
                t("Contact & Feedback"),
                CONTACT_INFO,
            ),
            unsafe_allow_html=True,
        )

    if st.session_state.role in ["admin", "superadmin"]:
        tab_list = [
            t("status_tab"),
            t("order_mgmt_reporting"),
            t("user_mgmt"),
            t("my_orders"),
            t("method_info"),
            t("tab_labor"),
            t("tab_profile"),
        ]

    else:
        tab_list = [t("my_orders"), t("method_info"), t("tab_labor"), t("tab_profile")]

    tabs = st.tabs(tab_list)
    all_orders = get_orders_data_cached(st.session_state.user_id, st.session_state.role)
    df = pd.DataFrame(all_orders) if all_orders else pd.DataFrame()

    if st.session_state.role in ["admin", "superadmin"]:
        with tabs[0]:
            render_dashboard_fragment(all_orders, df)
        with tabs[1]:
            admin_reporting_view(all_orders)
        with tabs[2]:
            admin_user_view()
        with tabs[3]:
            render_user_orders(df, "admin")
        with tabs[4]:
            method_catalog_view()
        with tabs[5]:
            render_labor_info()
        with tabs[6]:
            render_profile_tab()

    else:
        with tabs[0]:
            render_user_orders(df, "user")
        with tabs[1]:
            method_catalog_view()
        with tabs[2]:
            render_labor_info()
        with tabs[3]:
            render_profile_tab()


# =============================================================================
# TAB | Order
# =============================================================================
def render_user_orders(df, key_prefix):

    if not df.empty:
        user_email = st.session_state.get("user_email")
        df = df[df["user_email"] == user_email]
    c1, c2 = st.columns([3, 1])
    c1.subheader(f"📒 {t('my_orders')}")

    if c2.button(
        f"➕ {t('new_order')}",
        type="primary",
        key=f"new_{key_prefix}",
        width="stretch",
    ):
        st.session_state.wizard_step = 1
        st.session_state.page = "wizard"
        st.rerun()

    if df.empty:
        return

    for _, r in df.iterrows():
        with st.expander(
            f"📦 {r['order_number']} - {r['project_name']} | {t(r['status'])}"
        ):
            st.write(f"**{t('inbox_date')}:** {r['created_at']:%d.%m.%Y}")
            st.write(f"**{t('sample_count')}:** {r['sample_count']}")
            st.markdown(f"**{t('sample_details')}:**")

            if r.get("samples"):
                table_data = []

                for s in r["samples"]:
                    p_raw = s.get("cat_preparation") or s.get("preparation") or ""
                    m_raw = s.get("cat_analyses") or s.get("methods") or ""
                    all_ids = []

                    p_translated = (
                        ", ".join([t(i.strip()) for i in p_raw.split(",") if i.strip()])
                        if p_raw
                        else "-"
                    )

                    m_translated = (
                        ", ".join([t(i.strip()) for i in m_raw.split(",") if i.strip()])
                        if m_raw
                        else "-"
                    )

                    col_prep = t("preparation_col")
                    col_services = t("analyses_col")
                    col_ext = t("external_id")

                    table_data.append(
                        {
                            t("order_table"): s.get("customer_sample_name")
                            or s.get("name")
                            or t("unknown"),
                            col_prep: p_translated,
                            col_services: m_translated,
                            col_ext: s.get("external_id", "-"),
                        }
                    )
                table_data.sort(key=lambda x: natural_sort_key(x[t("order_table")]))
                st.dataframe(
                    pd.DataFrame(table_data),
                    column_config={
                        t("order_table"): st.column_config.TextColumn(width="small"),
                        col_prep: st.column_config.TextColumn(width="medium"),
                        col_services: st.column_config.TextColumn(width="medium"),
                        col_ext: st.column_config.TextColumn(width="small"),
                    },
                    hide_index=True,
                    width="stretch",
                )

            else:
                st.caption(t("no_samples_found"))

            if r.get("lab_note"):
                st.info(f"💬 **{t('lab_feedback')}:**\n\n{r['lab_note']}")
            cols = st.columns([4, 1.5])

            with cols[1]:
                if r["status"] == "cat_order_released" and r["has_report"]:
                    session = SessionLocal()

                    try:
                        obj = session.get(Order, r["id"])
                        if obj and obj.result_file_blob:
                            st.download_button(
                                label=f"⬇️ {t('report_btn')}",
                                data=obj.result_file_blob,
                                file_name=(
                                    r["result_file_name"]
                                    if r.get("result_file_name")
                                    else f"{r['project_name']}_{r['order_number']}_{t('report_filename')}.xlsx"
                                ),
                                key=f"dl_{key_prefix}_{r['id']}",
                                width="stretch",
                            )

                    finally:
                        session.close()

        st.markdown(
            "<hr style='margin: 0.5em 0; border: none; border-bottom: 1px solid rgba(255,255,255,0.05);'>",
            unsafe_allow_html=True,
        )


# =============================================================================
# Application router & View control
# =============================================================================
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "dashboard":
    dashboard_page()
elif st.session_state.page == "wizard":
    render_wizard_page()
