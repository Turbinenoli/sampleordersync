import streamlit as st


def inject_custom_css():
    """Injeziert das CSS für Animationen und das Branding-Design."""
    st.markdown(
        """
<style>
    /* Die Basis-Animation: Einfliegen von links */
    @keyframes fadeInLeft {
        from {
            opacity: 0;
            transform: translateX(-30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    /* Globale Fade-In Animation für den Hauptinhalt gegen das Ruckeln */
    @keyframes fadeInContent {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    /* Anwendung der Animation auf den Hauptcontainer */
    .main .block-container {
        animation: fadeInContent 0.8s ease-in-out;
    }

    /* Gemeinsame Basis für alle Logo-Elemente */
    .animated-logo {
        letter-spacing: 5px;
        text-transform: uppercase;
        display: block; 
        opacity: 0;     
        animation: fadeInLeft 1s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
    }

    /* --- HAFL SOIL LAB (Das Institutions-Logo) --- */
    .logo-hafl {
        font-weight: 500; 
        font-size: 18px;  
        color: #89A6B3;   
        margin-bottom: 5px;
        animation-delay: 0.1s; 
    }

    /* --- SOIL ORDER SYNC (Der SOS Block) --- */
    .logo-main {
        font-weight: 800; 
        font-size: 40px;  
        line-height: 0.9;
    }

    .l-soil { 
        color: #CFA071; 
        animation-delay: 0.3s; 
    }
    
    .l-order { 
        color: #E8E3DF; 
        animation-delay: 0.5s; 
    }
    
    .l-sync { 
        color: #CFA071; 
        animation-delay: 0.7s; 
    }

    /* Die User-Kachel Animation */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        animation: fadeInLeft 0.6s ease-out 1.0s backwards;
    }
    
    /* Diskreter Sidebar-Footer am unteren Rand fixiert */
    .sidebar-footer {
        position: fixed;
        bottom: 15px;
        left: 1.1rem;
        width: 14rem;
        padding-top: 10px;
        border-top: 1px solid rgba(232, 227, 223, 0.1);
        font-size: 0.7rem;
        color: rgba(232, 227, 223, 0.4);
        text-align: left;
        background-color: transparent;
        z-index: 100;
    }

    /* Styling für die Metriken zur Reduktion von Layout-Shifts */
    div[data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.03);
        padding: 15px;
        border-radius: 10px;
    }
</style>
""",
        unsafe_allow_html=True,
    )


def get_logo_html():
    """Gibt das HTML-Gerüst für das animierte Logo zurück."""
    return """
    <div style="margin-bottom: 30px; line-height: 1;">
        <span class="animated-logo logo-hafl">| HAFL SOIL LAB</span>            
        <span class="animated-logo logo-main l-soil">Sample</span>
        <span class="animated-logo logo-main l-order">Order</span>
        <span class="animated-logo logo-main l-sync">Sync</span>
    </div>
    """


def get_footer_html(
    version_label, version_val, release_label, release_val, contact_label, contact_val
):
    """Gibt den HTML-Footer für die Sidebar zurück."""
    return f"""
    <div class="sidebar-footer">
        <div>{version_label}: {version_val}</div>
        <div>{release_label}: {release_val}</div>
        <div>{contact_label}: {contact_val}</div>
    </div>
    """
