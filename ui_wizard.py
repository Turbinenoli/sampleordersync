import streamlit as st
import pandas as pd
import time
from datetime import datetime
import io
import re
from database import SessionLocal, Order, Sample, OrderLog
from translation import t
from logic import (
    METHOD_CATALOG,
    PREPARATION_CATALOG,
    METHOD_DETAILS,
    PROJECT_TYPE,
    PREPARATION_PACKAGES,
    ANALYSES_PACKAGES,
)


def clean_sample_name(val):
    """Bereinigt Probenbezeichnungen für Dateisicherheit und Eindeutigkeit."""
    if pd.isna(val) or not str(val).strip():
        return ""
    name = str(val).strip()
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for k, v in replacements.items():
        name = name.replace(k, v)
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name


def validate_psp(psp):
    """Prüft das PSP-Format: X.000000-00-XXXX-00"""
    if not isinstance(psp, str):
        return False
    pattern = r"^[A-Z]\.\d{6}-\d{2}-[A-Z]{4}-\d{2}$"
    return bool(re.match(pattern, psp))


def generate_template():
    """Erstellt das Experten-Template mit fixen Soildat-Headern und technischen Keys."""

    all_preps = [m for sub in PREPARATION_CATALOG.values() for m in sub]
    all_meths = [m for sub in METHOD_CATALOG.values() for m in sub]

    cols = ["field_code", "id_sample_soildat", "project"] + all_preps + all_meths

    if st.session_state.language == "de":
        example_field_code = "Probe_1"
        example_project = "Musterdorf"
    else:
        example_field_code = "Echantillons_1"
        example_project = "Trifouilly-les-Oies"

    example_data = {
        "field_code": example_field_code,
        "id_sample_soildat": "123456",
        "project": example_project,
    }

    for m in all_preps + all_meths:
        example_data[m] = "x" if m in ["ph_cacl", "humus", "drying_60"] else ""

    df = pd.DataFrame([example_data], columns=cols)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:

        df.to_excel(writer, index=False, sheet_name="Import_Template")

        legend_data = []
        for m in all_preps:
            legend_data.append(
                {
                    "Key": m,
                    "Zweck": "Aufbereitung",
                    "Anzeige im LIMS": t(m),
                }
            )
        for m in all_meths:
            legend_data.append(
                {"Key/Spaltentitel": m, "Zweck": "Analyse", "Anzeige im LIMS": t(m)}
            )

        pd.DataFrame(legend_data).to_excel(
            writer, index=False, sheet_name="HELP_LEGEND"
        )

    return output.getvalue()


def process_uploaded_df(df):
    """
    Verarbeitet den Excel-Import.
    Erkennt Spalten sowohl anhand technischer Keys (ph_cacl)
    als auch anhand übersetzter Labels (🟢 pH CaCl2).
    """
    try:

        if "field_code" not in df.columns:
            st.error(t("upload_error_msg"))
            return False

        def norm(txt):
            return (
                "".join(str(txt).split())
                .lower()
                .replace("_", "")
                .replace("-", "")
                .replace("🟢", "")
            )

        id_aliases = [
            "id_sample_soildat",
            "ext_id",
            "soildat_id",
            "external_id",
            "id_extern",
        ]
        norm_id_aliases = [norm(a) for a in id_aliases]

        actual_id_col = None
        for col in df.columns:
            if norm(col) in norm_id_aliases:
                actual_id_col = col
                break

        all_meths = [m for sub in METHOD_CATALOG.values() for m in sub]
        all_preps = [m for sub in PREPARATION_CATALOG.values() for m in sub]

        lookup = {}
        for m in all_meths + all_preps:
            lookup[norm(m)] = m  # Technischer Key (ph_cacl -> phcacl)
            lookup[norm(t(m))] = m  # Übersetzung (🟢 pH CaCl2 -> phcacl2)

        found_mapping = {}
        for col in df.columns:
            n_col = norm(col)
            if n_col in lookup:
                found_mapping[col] = lookup[n_col]

        valid_confirmations = ["x", "1", "ja", "yes", "true", "v", "oui", "1.0"]

        new_samples = []

        for _, r in df.iterrows():
            name = str(r["field_code"]).strip()

            if not name or name.lower() in ["nan", "beispiel_01", "example_01"]:
                continue

            ext_id_raw = ""
            if actual_id_col:
                val = r[actual_id_col]
                if pd.notna(val):
                    ext_id_raw = str(val).split(".")[0]

            methods_found = []
            preps_found = []

            for col, internal_key in found_mapping.items():
                val = str(r[col]).strip().lower()
                if val in valid_confirmations:
                    if internal_key in all_meths:
                        methods_found.append(internal_key)
                    elif internal_key in all_preps:
                        preps_found.append(internal_key)

            new_samples.append(
                {
                    "name": name,
                    "type": "material_soil",
                    "external_id": (
                        str(r.get("id_sample_soildat", "")).split(".")[0]
                        if str(r.get("id_sample_soildat", "")) != "nan"
                        else ""
                    ),
                    "methods": ",".join(methods_found),
                    "preparations": ",".join(preps_found),
                }
            )

        if new_samples:
            st.session_state.samples = new_samples
            return True  # Erfolg!

        return False

    except Exception as e:
        st.error(f"🚨 Import-Fehler: {e}")
        return False


def render_wizard_page():
    """Haupt-Wizard Komponente für den Bestellprozess."""

    if "form_key_suffix" not in st.session_state:
        st.session_state.form_key_suffix = 0

    st.title(t("wizard_title"))
    if st.button(f"⬅️ {t('back_to_menu')}"):
        st.session_state.page = "dashboard"
        st.rerun()

    st.progress(st.session_state.wizard_step / 4)

    if st.session_state.wizard_step == 1:
        st.subheader(t("step1"))
        st.caption(t("wizard_page1_desc"))

        proj = st.text_input(
            f"{t('project')} *", value=st.session_state.get("proj_name", "")
        )

        proj_selected = st.selectbox(
            f"{t('proj_type_desc')} *",
            PROJECT_TYPE,
            index=(
                PROJECT_TYPE.index(st.session_state.project_type)
                if st.session_state.get("project_type") in PROJECT_TYPE
                else None
            ),
            placeholder=t("select_proj_msg"),
            format_func=t,
        )

        psp = st.text_input(
            f"{t('psp')} *",
            value=st.session_state.get("psp_element", ""),
            placeholder="B.123456-12-ABCD-12",
            help="B.123456-12-ABCD-12",
        )

        psp_valid = validate_psp(psp)
        if psp and not psp_valid:
            st.warning(f"⚠️ {t('err_psp_invalid')}")

        form_ready = bool(proj) and bool(proj_selected) and psp_valid

        if st.button(
            t("next"), type="primary", width="stretch", disabled=not form_ready
        ):
            st.session_state.proj_name = proj
            st.session_state.project_type = proj_selected
            st.session_state.psp_element = psp
            st.session_state.wizard_step = 2
            st.rerun()

    elif st.session_state.wizard_step == 2:
        if "import_success_msg" in st.session_state:
            st.toast(st.session_state.import_success_msg, icon="✅")
            del st.session_state.import_success_msg
        st.subheader(t("step2"))
        st.markdown(t("wizard_page2_desc"))
        st.divider()
        st.markdown(t("wizard_page2_desc_1"))
        st.markdown(t("wizard_page2_subheader"))
        with st.expander(t("wizard_page2_exp_info")):
            st.write(t("wizard_page2_template_intro"))
            st.info(t("wizard_page2_info"))

        col_dl, col_up = st.columns(2)

        with col_dl:

            date_str = datetime.now().strftime("%Y%m%d")
            file_name = f"{date_str}_Import_Template_SOS.xlsx"

            st.download_button(
                label=f"⬇️ {t('template_dwln_btn')}",
                data=generate_template(),
                file_name=file_name,  # Hier ist das Datum jetzt drin!
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

        with col_up:
            up = st.file_uploader(
                t("label_upload"),
                type=["xlsx"],
                label_visibility="collapsed",
                key=f"uploader_{st.session_state.form_key_suffix}",
            )

            if up:
                file_id = f"{up.name}_{up.size}"
                if st.session_state.get("last_uploaded_file") != file_id:
                    success = False
                    try:
                        df_up = pd.read_excel(up)
                        process_uploaded_df(df_up)
                        success = True
                        st.session_state.last_uploaded_file = file_id

                    except Exception as e:
                        st.error(t("upload_error_msg"))

                    if success:

                        num_samples = len(st.session_state.samples)
                        st.session_state.import_success_msg = (
                            f"{num_samples} {t('sample_import_msg')}"
                        )

                        st.session_state.form_key_suffix += 1
                        st.session_state.import_success = True
                        st.rerun()

        st.caption(t("wizard_page2_disclaimer"))
        st.divider()
        st.markdown(t("wizard_page2_desc_2"))
        st.markdown(t("wizard_page2_subheader_2"))

        if not st.session_state.samples:
            st.session_state.samples = [
                {
                    "name": "",
                    "type": "material_soil",
                    "methods": "",
                    "preparations": "",
                    "external_id": "",
                }
            ]

        edited_df = st.data_editor(
            pd.DataFrame(st.session_state.samples),
            column_config={
                "name": st.column_config.TextColumn(t("order_table"), required=True),
                "type": None,
                "methods": None,
                "preparations": None,
                "external_id": None,
            },
            num_rows="dynamic",
            width="stretch",
            key=f"main_sample_editor_{st.session_state.form_key_suffix}",
            height=400,
        )

        st.divider()

        all_names = edited_df["name"].dropna().astype(str).tolist()
        current_names = [n.strip() for n in all_names if n.strip()]
        duplicates = set([x for x in current_names if current_names.count(x) > 1])
        invalid_names = set([x for x in current_names if x != clean_sample_name(x)])
        has_violations = bool(duplicates or invalid_names)

        if has_violations:
            st.error(f"🚫 {t('err_id_invalid')}")
            with st.container(border=True):
                st.markdown(t("msg_autocorrect"))
                col_fix_man, col_fix_auto = st.columns(2)

                if col_fix_man.button(t("label_correct_by_hand"), width="stretch"):
                    st.session_state.samples = []
                    st.rerun()

                if col_fix_auto.button(
                    t("label_autocorrect"),
                    type="primary",
                    width="stretch",
                ):

                    current_data_from_editor = edited_df.to_dict("records")

                    used_names = set()
                    for s in current_data_from_editor:
                        if not s["name"]:
                            continue

                        base = clean_sample_name(s["name"])
                        if not base:
                            base = t("default_sample_name")

                        final_name = base
                        counter = 1
                        while final_name in used_names:
                            final_name = f"{base}_{counter}"
                            counter += 1

                        used_names.add(final_name)
                        s["name"] = final_name

                    st.session_state.samples = current_data_from_editor
                    st.session_state.form_key_suffix += 1
                    st.rerun()

        st.divider()
        col_b, col_n = st.columns(2)
        if col_b.button(t("back"), width="stretch"):
            st.session_state.wizard_step = 1
            st.rerun()

        can_proceed = len(current_names) > 0 and not has_violations
        if col_n.button(
            t("next"),
            type="primary",
            width="stretch",
            disabled=not can_proceed,
        ):
            st.session_state.samples = edited_df.to_dict("records")

            all_have_methods = all(
                [bool(s.get("methods")) for s in st.session_state.samples]
            )
            if all_have_methods and len(st.session_state.samples) > 0:
                st.session_state.wizard_step = 4  # Überspringe Schritt 3
            else:
                st.session_state.wizard_step = 3  # Gehe normal zu Schritt 3
            st.rerun()

    elif st.session_state.wizard_step == 3:
        st.subheader(t("step3"))

        all_prep = [m for sub in PREPARATION_CATALOG.values() for m in sub]
        all_meths = [m for sub in METHOD_CATALOG.values() for m in sub]

        with st.container(border=True):
            st.markdown(f"### ⚙️ {t('header_preparation')}")

            def toggle_prep_pkg(pkg_key, methods):
                if st.session_state[pkg_key]:  # Paket wurde ANgeklikt
                    for m in methods:
                        if m not in st.session_state.selected_preparation:
                            st.session_state.selected_preparation.append(m)
                else:  # Paket wurde ABgewählt
                    for m in methods:
                        if m in st.session_state.selected_preparation:
                            st.session_state.selected_preparation.remove(m)

            p_cols = st.columns(len(PREPARATION_PACKAGES))
            for idx, (p_name, p_methods) in enumerate(PREPARATION_PACKAGES.items()):
                with p_cols[idx]:
                    pkg_key = f"pkg_prep_{p_name}"
                    st.checkbox(
                        t(p_name),
                        key=pkg_key,
                        on_change=toggle_prep_pkg,
                        args=(pkg_key, p_methods),
                    )

            st.divider()

            def toggle_prep_single(m_key, meth):
                if st.session_state[m_key]:
                    if meth not in st.session_state.selected_preparation:
                        st.session_state.selected_preparation.append(meth)
                else:
                    if meth in st.session_state.selected_preparation:
                        st.session_state.selected_preparation.remove(meth)

                    for p_name, p_methods in PREPARATION_PACKAGES.items():
                        if meth in p_methods:
                            st.session_state[f"pkg_prep_{p_name}"] = False

            cols = st.columns(4)
            for i, m in enumerate(all_prep):
                with cols[i % 4]:
                    m_key = f"prep_single_{m}"

                    st.session_state[m_key] = m in st.session_state.selected_preparation

                    st.checkbox(
                        t(m), key=m_key, on_change=toggle_prep_single, args=(m_key, m)
                    )

        with st.container(border=True):
            st.markdown(f"### 🔬 {t('header_analyses')}")

            def toggle_ana_pkg(pkg_key, methods):
                if st.session_state[pkg_key]:  # Paket wurde ANgeklikt
                    for m in methods:
                        if m not in st.session_state.selected_analyses:
                            st.session_state.selected_analyses.append(m)
                else:  # Paket wurde ABgewählt
                    for m in methods:
                        if m in st.session_state.selected_analyses:
                            st.session_state.selected_analyses.remove(m)

            a_cols = st.columns(len(ANALYSES_PACKAGES))
            for idx, (a_name, a_methods) in enumerate(ANALYSES_PACKAGES.items()):
                with a_cols[idx]:
                    pkg_key = f"pkg_ana_{a_name}"
                    st.checkbox(
                        t(a_name),
                        key=pkg_key,
                        on_change=toggle_ana_pkg,
                        args=(pkg_key, a_methods),
                    )

            st.divider()

            def toggle_ana_single(m_key, meth):
                if st.session_state[m_key]:
                    if meth not in st.session_state.selected_analyses:
                        st.session_state.selected_analyses.append(meth)
                else:
                    if meth in st.session_state.selected_analyses:
                        st.session_state.selected_analyses.remove(meth)

                    for a_name, a_methods in ANALYSES_PACKAGES.items():
                        if meth in a_methods:
                            st.session_state[f"pkg_ana_{a_name}"] = False

            cols_a = st.columns(4)
            for i, m in enumerate(all_meths):
                with cols_a[i % 4]:
                    m_key = f"anal_single_{m}"

                    st.session_state[m_key] = m in st.session_state.selected_analyses

                    st.checkbox(
                        t(m), key=m_key, on_change=toggle_ana_single, args=(m_key, m)
                    )

        st.divider()
        with st.expander(f"➕ {t('individual_analyses')}"):
            st.info(t("info_individual_analyses"))

            for idx, pkg in enumerate(st.session_state.analysis_packages):
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    pkg["name"] = c1.text_input(
                        f"{t('individual_package_bin')} {idx+1}",
                        pkg.get("name", ""),
                        key=f"pkgn_{idx}",
                    )
                    if c2.button(f"🗑️ {t('delete_sample')}", key=f"pkgd_{idx}"):
                        st.session_state.analysis_packages.pop(idx)
                        st.rerun()

                    safe_prep = [m for m in pkg.get("preparation", []) if m in all_prep]
                    safe_ana = [m for m in pkg.get("methods", []) if m in all_meths]

                    col_p, col_a = st.columns(2)
                    with col_p:
                        pkg["preparation"] = st.multiselect(
                            t("additional_preparation"),
                            options=all_prep,
                            default=safe_prep,
                            format_func=lambda x: t(x),
                            key=f"pkg_p_{idx}",
                        )
                    with col_a:
                        pkg["methods"] = st.multiselect(
                            t("additional_analyses"),
                            options=all_meths,
                            default=safe_ana,
                            format_func=lambda x: t(x),
                            key=f"pkg_a_{idx}",
                        )

                    sample_names = [
                        s["name"] for s in st.session_state.samples if s.get("name")
                    ]
                    pkg["samples"] = st.multiselect(
                        t("label_assign_to_sample"),
                        options=sample_names,
                        default=pkg.get("samples", []),
                        key=f"pkgs_{idx}",
                    )

            if st.button(f"➕ {t('new_individual_package')}"):

                st.session_state.analysis_packages.append(
                    {
                        "name": t("individual_package_name"),
                        "preparation": [],
                        "methods": [],
                        "samples": [],
                    }
                )
                st.rerun()

        st.divider()
        col_b, col_n = st.columns(2)
        if col_b.button(t("back"), width="stretch"):
            st.session_state.wizard_step = 2
            st.rerun()
        if col_n.button(t("summary"), type="primary", width="stretch"):
            st.session_state.wizard_step = 4
            st.rerun()

    elif st.session_state.wizard_step == 4:
        st.subheader(t("step4"))
        final_table = []
        for s in st.session_state.samples:
            if not s["name"].strip():
                continue
            prep = set(st.session_state.selected_preparation)
            meths = set(st.session_state.selected_analyses)

            p_val = str(s.get("preparations", ""))
            if p_val and p_val.lower() not in ["nan", "none", ""]:
                imported_preps = [m.strip() for m in p_val.split(",") if m.strip()]
                prep.update(imported_preps)

            m_val = str(s.get("methods", ""))
            if m_val and m_val.lower() not in ["nan", "none", ""]:
                imported_meths = [m.strip() for m in m_val.split(",") if m.strip()]
                meths.update(imported_meths)

            for pkg in st.session_state.analysis_packages:
                if s["name"] in pkg.get("samples", []):
                    prep.update(pkg.get("preparation", []))
                    meths.update(pkg.get("methods", []))

            total_mass = sum(
                [METHOD_DETAILS.get(m, {}).get("samplemass", 10) for m in meths]
            )

            total_mass = sum(
                [METHOD_DETAILS.get(m, {}).get("samplemass", 10) for m in meths]
            )
            final_table.append(
                {
                    t("sample_id_col"): s["name"],
                    t("preparation_col"): ", ".join(t(m) for m in sorted(list(prep))),
                    t("analyses_col"): ", ".join(t(m) for m in sorted(list(meths))),
                    t("minimal_amt_col"): f"{total_mass} g",
                    "ext_id": s.get("external_id", ""),
                    "raw_prep": ",".join(
                        sorted(list(prep))
                    ),  # REINE KEYS (z.B. "drying_60,ph_cacl")
                    "raw_meths": ",".join(sorted(list(meths))),  # REINE KEYS
                    "ext_id": s.get("external_id", ""),
                    "raw_name": s[
                        "name"
                    ],  # Sicherheitskopie des Namens ohne Übersetzung
                }
            )

        if final_table:
            df_display = pd.DataFrame(final_table)
            cols_to_hide = ["ext_id", "raw_prep", "raw_meths", "raw_name"]

            st.dataframe(
                df_display.drop(columns=cols_to_hide, errors="ignore"),
                width="stretch",
                hide_index=True,
            )
            st.warning(f"⚠️ {t('info_sample_mass_amt')}")

            st.divider()
            c_note = st.text_area(
                t("customer_note"),
                value=st.session_state.get("customer_note", ""),
                max_chars=200,
                help=(t("max_char_val")),
                placeholder=t("note_placeholder"),
                height=100,
            )

            st.session_state.customer_note = c_note

            if c_note:
                v_regex = r"[aeiouyäöüéàèêâîûôëï]+"

                clean_t = c_note.replace("\n", " ").strip()

                parts = re.split(r"([,;./!?:])", clean_t, maxsplit=1)
                if len(parts) >= 3:
                    left_part = parts[0]
                    right_part = parts[2]

                    left_syl = len(re.findall(v_regex, left_part.lower()))
                    right_syl = len(re.findall(v_regex, right_part.lower()))

                    if left_syl == 6 and right_syl in [6, 7]:
                        if st.session_state.get("last_rhyme") != clean_t:
                            st.balloons()
                            st.success(t("alexandriner_party"))
                            st.session_state.last_rhyme = clean_t
                            time.sleep(3)

            key_sample = t("sample_id_col")
            key_analyses = t("analyses_col")
            samples_without_methods = [
                r["raw_name"] for r in final_table if not r["raw_meths"]
            ]
            if samples_without_methods:
                st.error(
                    f"🚫 {t('wrng_analyses_missing')} {', '.join(samples_without_methods)} {t('info_go_back')}"
                )

            col_b, col_n = st.columns(2)
            if col_b.button(t("back"), width="stretch"):
                st.session_state.wizard_step = 3
                st.rerun()

            if col_n.button(
                f"✅ {t('commit_to_order')}", type="primary", width="stretch"
            ):
                session = SessionLocal()
                try:
                    now = datetime.now()

                    gn = f"{now.strftime('%y%m')}-{session.query(Order).count()+1:04d}"

                    new_order = Order(
                        order_number=gn,
                        user_id=st.session_state.user_id,
                        project_name=st.session_state.proj_name,
                        psp_element=st.session_state.psp_element,
                        project_type=st.session_state.get("project_type", ""),
                        customer_note=st.session_state.customer_note,
                        status="cat_order_inbox",  # Nutze den Key aus logic.py
                    )
                    session.add(new_order)
                    session.flush()  # Holt uns die ID von new_order für die Samples

                    for r in final_table:
                        session.add(
                            Sample(
                                order_id=new_order.id,
                                customer_sample_name=r["raw_name"],
                                material_type="material_soil",
                                cat_preparation=r["raw_prep"],
                                cat_analyses=r["raw_meths"],
                                external_id=r["ext_id"],
                            )
                        )

                    session.add(
                        OrderLog(
                            order_id=new_order.id,
                            action="new_order",
                            status_to="cat_order_inbox",
                            changed_by=st.session_state.username,
                        )
                    )

                    session.commit()

                    st.cache_data.clear()
                    st.success(t("success_msg"))
                    time.sleep(1)

                    st.session_state.update(
                        {
                            "wizard_step": 1,
                            "page": "dashboard",
                            "samples": [],
                            "selected_preparation": [],
                            "selected_analyses": [],
                            "analysis_packages": [],
                            "customer_note": "",
                            "proj_name": "",
                            "project_type": "",
                            "psp_element": "",
                            "last_rhyme": "",
                        }
                    )
                    st.rerun()

                except Exception as e:
                    session.rollback()  # Falls was schiefgeht: Alles rückgängig machen!
                    st.error(f"❌ {t('error_save')}: {e}")

                finally:
                    session.close()  # Verbindung zur DB immer sauber trennen


def method_catalog_view():
    """Methodenkatalog Ansicht – Die finale, gereinigte Version."""
    st.subheader(f"📖 {t('method_info')}")

    for category, methods in METHOD_CATALOG.items():

        with st.expander(f"**{t(category)}**"):
            for m in methods:
                info = METHOD_DETAILS.get(m, {})

                st.markdown(f"#### {t(m)}")

                desc_key = info.get("key_desc", "no_desc_available")
                st.write(f"**{t('label_description')}:** {t(desc_key)}")

                mass = info.get("samplemass", 10)
                st.caption(f"{t('label_min_mass')}: {mass}g")

                st.divider()
