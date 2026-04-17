import streamlit as st
import time
from datetime import datetime
from database import SessionLocal, Order, User, OrderLog
from translation import t
from logic import ORDER_STATUSES, notify_user_status_change
from werkzeug.security import generate_password_hash
from xhtml2pdf import pisa


def get_routing_slip_html(order):
    """Generiert den HTML-Laufzettel für den Browser-Druck."""

    # Proben-Zeilen generieren (inkl. External ID)
    rows = ""
    for i, s in enumerate(order["samples"]):
        # 1. Vorbereitung übersetzen
        prep_raw = s.get("preparation", "")
        prep_list = [t(p.strip()) for p in prep_raw.split(",") if p.strip()]
        prep_translated = ", ".join(prep_list) if prep_list else "-"

        # 2. Methoden übersetzen
        meth_raw = s.get("methods", "")
        meth_list = [t(m.strip()) for m in meth_raw.split(",") if m.strip()]
        meth_translated = ", ".join(meth_list) if meth_list else "-"

        # 3. Zeile zusammenbauen
        rows += f"""
            <tr>
                <td>{i+1}</td>
                <td><strong>{s['name']}</strong></td>
                <td>{prep_translated}</td>
                <td>{meth_translated}</td>
            </tr>
        """

    # Das "Pompöse" HTML-Template
    return f"""
    <html>
    <head>
        <meta charset='UTF-8'>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; color: #333; }}
            .header {{ 
                display: flex; 
                justify-content: space-between; 
                align-items: center;
                border-bottom: 4px solid #CFA071; 
                padding-bottom: 15px; 
                margin-bottom: 30px; 
            }}
            .brand {{ color: #CFA071; font-weight: bold; font-size: 24px; }}
            .order-meta {{ text-align: right; font-size: 0.9em; color: #666; }}
            h2 {{ margin: 0; color: #111; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ border: 1px solid #eee; padding: 12px 10px; text-align: left; }}
            th {{ background-color: #fcf8f3; color: #CFA071; font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; }}
            tr:nth-child(even) {{ background-color: #fafafa; }}
            .footer {{ margin-top: 50px; font-size: 0.8em; color: #aaa; border-top: 1px solid #eee; padding-top: 10px; text-align: center; }}
            
            @media print {{ 
                .no-print {{ display: none !important; }} 
                body {{ padding: 0; }}
            }}
            
            .print-button {{ 
                background: #CFA071; 
                color: white; 
                border: none; 
                padding: 12px 25px; 
                border-radius: 5px; 
                cursor: pointer; 
                font-weight: bold;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                transition: transform 0.1s;
            }}
            .print-button:active {{ transform: scale(0.98); }}
        </style>
    </head>
    <body>
        <div class='header'>
            <div>
                <div class='brand'>HAFL SOIL LAB</div>
                <h2>{t('routing_slip_title')}</h2>
            </div>
            <div class='order-meta'>
                <strong>{order['order_number']}</strong><br>
                {t('project_label')}: {order['project_name']}<br>
                {t('date_mark')}: {order['created_at'].strftime('%d.%m.%Y')}
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>{t('table_sample')}</th>
                    <th>{t('table_preparation')}</th>
                    <th>{t('table_analyses')}</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>

        <div class='footer'>
            Generiert am {order['created_at'].strftime('%d.%m.%Y %H:%M')} | {order.get('user_fullname', '')}
        </div>

        <div style='margin-top: 30px; text-align: right;'>
            <button class='no-print print-button' onclick='window.print()'>
                🖨️ {t('print_btn')}
            </button>
        </div>
    </body>
    </html>
    """


def render_order_management_card(o):
    """Management-Karte mit Audit Trail und Kommunikations-Logik."""
    with st.expander(
        f"📦 {o['order_number']} - {o['project_name']} | {t(o['status'])}"
    ):
        st.info(f"👤 **{t('creator_info')}:** {o['user_fullname']} ({o['user_email']})")

        if o.get("customer_note"):
            st.warning(f"📝 **{t('customer_note')}:**\n\n{o['customer_note']}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{t('status_change')}**")
            active_statuses = [
                s
                for s in ORDER_STATUSES
                if s not in ["cat_order_released", "cat_order_annulated"]
            ]
            current_status = o["status"]

            if current_status in ["cat_order_released", "cat_order_annulated"]:
                st.success(f"{t('status_label')}: {t(current_status)}")
            else:
                idx = (
                    active_statuses.index(current_status)
                    if current_status in active_statuses
                    else 0
                )
                ns = st.selectbox(
                    t("set_status"),
                    active_statuses,
                    index=idx,
                    key=f"s_{o['id']}",
                    format_func=t,
                )

                if st.button(t("save_changes"), key=f"sv_{o['id']}", width="stretch"):
                    if ns == "cat_order_complete" and not o["has_report"]:
                        st.error(t("upload_first_info"))
                    else:
                        session = SessionLocal()
                        try:
                            odb = session.get(Order, o["id"])
                            if odb and odb.status != ns:
                                session.add(
                                    OrderLog(
                                        order_id=o["id"],
                                        action="act_status_change",
                                        status_from=odb.status,
                                        status_to=ns,
                                        changed_by=st.session_state.username,
                                    )
                                )
                                odb.status = ns
                                session.commit()
                                st.cache_data.clear()
                                st.success(t("success"))
                                time.sleep(0.5)
                                st.rerun()
                        finally:
                            session.close()

        with c2:
            st.markdown(f"**{t('note_report_section')}**")
            lab_note = st.text_area(
                t("lab_note"),
                value=o.get("lab_note", ""),
                key=f"ln_{o['id']}",
                height=70,
            )
            if st.button(
                f"💾 {t('save_note_btn')}", key=f"sln_{o['id']}", width="stretch"
            ):
                session = SessionLocal()
                try:
                    odb = session.get(Order, o["id"])
                    if odb:
                        odb.lab_note = lab_note
                        session.commit()
                        st.success(t("note_saved_success"))
                finally:
                    session.close()

            st.divider()
            up = st.file_uploader(t("upload_report"), type=["xlsx"], key=f"u_{o['id']}")
            if up and st.button(
                f"⬆️ {t('save_report_btn')}", key=f"bs_{o['id']}", width="stretch"
            ):
                session = SessionLocal()
                try:
                    odb = session.get(Order, o["id"])
                    if odb:
                        odb.result_file_blob, odb.result_file_name = up.read(), up.name
                        odb.status = "cat_order_complete"
                        session.add(
                            OrderLog(
                                order_id=o["id"],
                                action="act_report_uploaded",
                                status_to="cat_order_complete",
                                changed_by=st.session_state.username,
                            )
                        )
                        session.commit()
                        st.cache_data.clear()
                        st.success(t("report_uploaded_success"))
                        st.rerun()
                finally:
                    session.close()

            if o["has_report"] and o["status"] != "cat_order_released":
                if st.button(
                    f"🚀 {t('finalize_order')}",
                    type="primary",
                    key=f"f_{o['id']}",
                    width="stretch",
                ):
                    session = SessionLocal()
                    try:
                        odb = session.get(Order, o["id"])
                        if odb:
                            odb.status = "cat_order_released"
                            odb.completed_at = datetime.now()
                            session.add(
                                OrderLog(
                                    order_id=o["id"],
                                    action="act_order_finalized",
                                    status_to="cat_order_released",
                                    changed_by=st.session_state.username,
                                )
                            )
                            session.commit()
                            st.cache_data.clear()
                            notify_user_status_change(
                                o["order_number"], o["user_email"], "cat_order_released"
                            )
                            st.rerun()
                    finally:
                        session.close()

        st.divider()
        with st.expander(f"📅 {t('order_log')}"):
            session = SessionLocal()
            logs = (
                session.query(OrderLog)
                .filter_by(order_id=o["id"])
                .order_by(OrderLog.timestamp.desc())
                .all()
            )
            if not logs:
                st.caption(t("no_logs_found"))
            for l in logs:
                s_from = t(l.status_from) if l.status_from else "-"
                s_to = t(l.status_to)
                st.caption(
                    f"**{l.timestamp:%d.%m. %H:%M}** | {t(l.action)}: `{s_from}` ➔ `{s_to}` ({t('by_user')} {l.changed_by})"
                )
            session.close()

        st.download_button(
            f"📄 {t('print_routing_slip_btn')}",
            get_routing_slip_html(o),
            f"{t('routing_slip_filename')}_{o['order_number']}.html",
            mime="text/html",
            key=f"print_{o['id']}",
            width="stretch",
        )


def admin_reporting_view(all_orders):
    """Hauptansicht Management."""
    st.subheader(f"🛠️ {t('order_mgmt_reporting')}")
    if not all_orders:
        st.info(t("database_state"))
        return

    st.divider()

    archive_stati = ["cat_order_released", "cat_order_annulated"]
    active_stati = [
        "cat_order_inbox",
        "cat_order_confirmed",
        "cat_order_processed",
        "cat_order_complete",
    ]

    for status in active_stati:
        orders = [o for o in all_orders if o["status"] == status]
        st.markdown(f"#### {t(status)} ({len(orders)})")
        if not orders:
            st.caption(f"{t('no_orders_status')} '{t(status)}'")
        else:
            for o in orders:
                render_order_management_card(o)
        st.write("")

    st.divider()
    st.markdown(t("mgmt_desc"))

    archived = [o for o in all_orders if o["status"] in archive_stati]
    with st.expander(
        f"📦 {t('archive_history_title')} ({len(archived)})", expanded=False
    ):
        if not archived:
            st.info(t("archive_empty_info"))
        else:
            for o in archived:
                render_order_management_card(o)


def admin_user_view():
    """Benutzerverwaltung mit Kategorisierung."""
    st.subheader(f"🛡️ {t('user_mgmt')}")
    session = SessionLocal()

    try:
        all_users = (
            session.query(User).filter(User.id != st.session_state.user_id).all()
        )

        if not all_users:
            st.info(t("no_user_found"))
            return

        active_users = [u for u in all_users if u.is_active and not u.is_deleted]
        waiting_users = [u for u in all_users if not u.is_active and not u.is_deleted]
        deleted_users = [u for u in all_users if u.is_deleted]

        st.markdown(f"### 🟢 {t('title_active_users')} ({len(active_users)})")
        for u in active_users:
            render_user_row(u, session)

        st.divider()
        st.markdown(f"### ⏳ {t('title_waiting_users')} ({len(waiting_users)})")
        if not waiting_users:
            st.caption(t("info_no_waiting_users"))
        for u in waiting_users:
            render_user_row(u, session)

        st.divider()
        with st.expander(
            f"🗑️ {t('title_deleted_users')} ({len(deleted_users)})", expanded=False
        ):
            if not deleted_users:
                st.caption(t("info_no_deleted_users"))
            for u in deleted_users:
                render_user_row(u, session, is_archived=True)

    finally:
        session.close()


def render_user_row(u, session, is_archived=False):
    """Rendert eine einzelne Zeile in der Benutzerverwaltung."""
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([2, 1.2, 1.8, 1])

        with col1:
            st.write(f"**{u.first_name} {u.last_name}**")
            st.caption(f"{u.email} | {u.department}")
            if u.password_reset_requested:
                st.warning("⚠️ " + t("forgot_pw_warning"))

        with col2:
            if is_archived:
                st.write(f"⚪ {t('user_archived')}")
            else:
                st.write(
                    f"🟢 {t('user_active')}"
                    if u.is_active
                    else f"⏳ {t('user_waiting')}"
                )

        with col3:
            if st.session_state.role == "superadmin" and not is_archived:
                role_options = ["user", "admin", "superadmin"]
                new_role = st.selectbox(
                    t("role_label"),
                    role_options,
                    index=role_options.index(u.role) if u.role in role_options else 0,
                    key=f"role_{u.id}",
                    label_visibility="collapsed",
                    format_func=lambda x: t(f"role_{x}"),
                )
                if new_role != u.role:
                    u.role = new_role
                    session.commit()
                    st.rerun()

            if u.password_reset_requested and not is_archived:
                if st.button(
                    t("reset_pw_btn"),
                    key=f"reset_{u.id}",
                    type="primary",
                    width="stretch",
                ):
                    u.password = generate_password_hash(
                        "HAFL-Reset-2026"
                    )  # Here the default PW gets defined
                    u.password_reset_requested = False
                    session.commit()
                    st.success(t("temp_pw_set_success"))
                    time.sleep(1)
                    st.rerun()

        with col4:
            if not is_archived:
                if not u.is_active:
                    if st.button("✔️", key=f"act_{u.id}", help=t("activate_user_help")):
                        u.is_active = True
                        session.commit()
                        st.rerun()
                else:
                    if st.button("🚫", key=f"lock_{u.id}", help=t("lock_user_help")):
                        u.is_active = False
                        session.commit()
                        st.rerun()

                if st.session_state.role == "superadmin":
                    with st.popover("🗑️", help=t("delete_user_help")):
                        st.warning(t("confirm_delete_msg"))
                        if st.button(
                            t("ultimate_delete_btn"),
                            key=f"del_{u.id}",
                            type="primary",
                            width="stretch",
                        ):
                            u.is_deleted = True
                            u.is_active = False
                            session.commit()
                            st.success(t("user_deleted_success"))
                            time.sleep(0.5)
                            st.rerun()
            else:
                if st.session_state.role == "superadmin":
                    if st.button(
                        "♻️", key=f"restore_{u.id}", help=t("restore_user_help")
                    ):
                        u.is_deleted = False
                        session.commit()
                        st.rerun()
