import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import google.generativeai as genai
import time

st.set_page_config(page_title="Min Vinkällare", page_icon="🍷", layout="wide")

# --- 1. SÄKERHET & LÖSENORD (ROBUST VERSION) ---
def check_password():
    """Säkerställer inloggning utan att krascha vid omladdning."""
    if "password" not in st.secrets:
        return True

    # Om vi redan är inloggade, kör på
    if st.session_state.get("password_correct", False):
        return True

    # Kolla om användaren skrivit in något (callback körs före denna kod)
    if "password_input" in st.session_state:
        if st.session_state["password_input"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            # Rensa input för säkerhet (men krascha inte om den redan är borta)
            del st.session_state["password_input"] 
            return True
        else:
            st.error("😕 Fel lösenord")
            
    # Visa inloggningsruta
    st.text_input("Lösenord", type="password", key="password_input")
    return False

if not check_password():
    st.stop()

# --- 2. KONFIGURATION ---
def get_google_sheet_client():
    try:
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return None

if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]

# --- 3. DESIGN: MODERN SOMMELIER ---
st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA; color: #2C3E50; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    
    section[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E9ECEF; }
    section[data-testid="stSidebar"] .stRadio div[role='radiogroup'] > label {
        background-color: #F1F3F5; padding: 15px 20px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #DEE2E6; cursor: pointer; color: #495057; font-weight: 500;
    }
    section[data-testid="stSidebar"] .stRadio div[role='radiogroup'] > label[data-checked="true"] {
        background-color: #722F37; border-left: 5px solid #4A1A21; color: white; font-weight: bold;
    }

    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #722F37; color: white; border: none; font-weight: 600; font-size: 16px; }
    .stButton>button:hover { background-color: #5a232b; color: white; }
    
    .wine-card { padding: 20px; background-color: #FFFFFF; border-radius: 12px; margin-bottom: 15px; border-left: 5px solid #722F37; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .wine-title { font-size: 18px; font-weight: bold; color: #2C3E50; margin-bottom: 5px; }
    .wine-info { color: #6C757D; font-size: 14px; }
    
    .stat-box { background-color: #FFFFFF; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #E9ECEF; }
    .stat-label { font-size: 14px; text-transform: uppercase; color: #6C757D; }
    .stat-num { font-size: 32px; font-weight: 700; color: #722F37; margin-top: 5px; }

    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E9ECEF; color: #495057; }
    .stTabs [aria-selected="true"] { background-color: #722F37; color: white; border: none; }
    </style>
""", unsafe_allow_html=True)

# --- 4. MASTER CONTEXT ---
MASTER_CONTEXT = """
Du är en objektiv, kreativ och kunnig sommelier.
Din uppgift är att hitta den ABSOLUT BÄSTA matchningen i lagret baserat på användarens fråga.
Instruktioner:
1. Utforska hela källaren.
2. Våga föreslå oväntade val.
3. VIKTIGT: Tala alltid om var flaskan ligger (Plats och Hylla).
Svara kort, inspirerande och hjälp användaren att hitta flaskan.
"""

# --- 5. DATAFUNKTIONER ---
def load_data():
    expected_cols = ["id", "namn", "argang", "typ", "antal", "plats", "sektion", "hylla", "pris"]
    client = get_google_sheet_client()
    if not client: return pd.DataFrame(columns=expected_cols)
    try:
        sheet = client.open("Min Vinkällare").sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if df.empty or 'plats' not in df.columns: return pd.DataFrame(columns=expected_cols)
        df['argang'] = df['argang'].astype(str)
        df['pris'] = pd.to_numeric(df['pris'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame(columns=expected_cols)

def save_data(df):
    client = get_google_sheet_client()
    if not client: return False
    try:
        sheet = client.open("Min Vinkällare").sheet1
        sheet.clear()
        df_clean = df.fillna("")
        data_to_write = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        sheet.update(range_name='A1', values=data_to_write)
        return True
    except: return False

def get_ai_response(prompt, inventory_str, is_trivia=False):
    if "GOOGLE_API_KEY" not in os.environ: return "⚠️ Ingen API-nyckel."
    try:
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        if is_trivia:
            full_prompt = f"Du är en vinkännare. Ge en intressant fakta om: {prompt}. Max 2 meningar."
        else:
            full_prompt = f"{MASTER_CONTEXT}\n\nLAGER:\n{inventory_str}\n\nFRÅGA: {prompt}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e: return f"🍷 AI:n sover. ({str(e)})"

# --- 6. APP LOGIK ---
if 'df' not in st.session_state:
    st.session_state['df'] = load_data()

df = st.session_state['df']

# Meny
with st.sidebar:
    st.header("🍷 Vinkällaren")
    page = st.radio("Meny", ["Översikt", "Vinkylen", "Bokhyllan", "Lagerhantering", "Sommelieren"], label_visibility="collapsed")
    st.write("---")
    if st.button("🔄 Ladda om data"):
        st.session_state['df'] = load_data()
        st.rerun()

# --- SIDOR ---
if page == "Översikt":
    st.title("Översikt")
    c1, c2 = st.columns(2)
    with c1: st.markdown(f"<div class='stat-box'><div class='stat-label'>Totalt</div><div class='stat-num'>{int(df['antal'].sum()) if not df.empty else 0}</div></div>", unsafe_allow_html=True)
    with c2: 
        val = df['pris'].sum() if not df.empty else 0
        st.markdown(f"<div class='stat-box'><div class='stat-label'>Värde</div><div class='stat-num'>{val/1000:.1f}k kr</div></div>", unsafe_allow_html=True)
    
    st.write("---")
    
    # Trivia (laddas bara om man vill)
    col_tr, col_btn = st.columns([3,1])
    with col_btn: 
        if st.button("Ny Trivia"):
             st.session_state.pop('trivia_vin_namn', None) # Tvinga ny

    if 'trivia_vin_namn' not in st.session_state:
        trivia_vin = df.sample(1).iloc[0] if not df.empty else None
        if trivia_vin is not None:
            st.session_state['trivia_vin_namn'] = f"{trivia_vin['namn']} ({trivia_vin['argang']})"
            with st.spinner("Hämtar fakta..."):
                fakta = f"{trivia_vin['namn']} {trivia_vin['argang']}"
                st.session_state['trivia_text'] = get_ai_response(fakta, '', True)
        else:
            st.session_state['trivia_vin_namn'] = "Tomt"
            st.session_state['trivia_text'] = "Lägg in lite viner först!"
            
    with col_tr:
        st.info(f"💡 **{st.session_state['trivia_vin_namn']}**\n\n{st.session_state['trivia_text']}")

elif page == "Vinkylen":
    st.title("🧊 mQuvée 126")
    
    st.subheader("Övre Zon (8°C)")
    for i in range(1, 4): 
        hylla = f"Hylla {i}"
        viner = df[(df['plats'] == "Vinkylen") & (df['hylla'] == hylla) & (df['sektion'] == "Övre")]
        count = int(viner['antal'].sum())
        with st.expander(f"{hylla} ({count} st)", expanded=False):
            if viner.empty: st.caption("Tomt")
            for _, row in viner.iterrows():
                st.markdown(f"<div class='wine-card'><div class='wine-title'>🍾 {row['namn']}</div><div class='wine-info'>{row['argang']} | {row['antal']} st</div></div>", unsafe_allow_html=True)

    st.subheader("Nedre Zon (16°C)")
    for i in range(1, 5): 
        hylla = f"Hylla {i}"
        viner = df[(df['plats'] == "Vinkylen") & (df['hylla'] == hylla) & (df['sektion'] == "Nedre")]
        count = int(viner['antal'].sum())
        with st.expander(f"{hylla} ({count} st)", expanded=False):
            if viner.empty: st.caption("Tomt")
            for _, row in viner.iterrows():
                st.markdown(f"<div class='wine-card'><div class='wine-title'>🍷 {row['namn']}</div><div class='wine-info'>{row['argang']} | {row['antal']} st</div></div>", unsafe_allow_html=True)

elif page == "Bokhyllan":
    st.title("📚 Bokhyllan")
    for h in ["Övre", "Undre"]:
        viner = df[(df['plats'] == "Bokhyllan") & (df['hylla'] == h)]
        with st.expander(f"{h} Hylla ({int(viner['antal'].sum())})", expanded=True):
            if viner.empty: st.caption("Tomt")
            for _, row in viner.iterrows():
                st.markdown(f"<div class='wine-card'><div class='wine-title'>{row['namn']}</div><div class='wine-info'>{row['argang']} | {row['antal']} st</div></div>", unsafe_allow_html=True)

elif page == "Lagerhantering":
    st.title("Lagerhantering")
    tab_add, tab_sort, tab_edit = st.tabs(["➕ Lägg till", "📦 Flytta/Sortera", "✏️ Ändra"])
    
    # 1. LÄGG TILL
    with tab_add:
        st.subheader("Nytt inköp")
        with st.form("add_form"):
            namn = st.text_input("Namn")
            c1, c2 = st.columns(2)
            arg = c1.text_input("Årgång", "2025")
            antal = c2.number_input("Antal", 1, 100, 1)
            typ = st.selectbox("Typ", ["Rött", "Vitt", "Bubbel", "Rosé", "Sött"])
            pris = st.number_input("Pris (kr)", 0, 100000, 0)
            
            st.markdown("---")
            st.markdown("**Placering**")
            plats = st.selectbox("Var?", ["Vinkylen", "Bokhyllan", "Osorterat"])
            
            sektion = ""
            hylla = ""
            
            if plats == "Vinkylen":
                zon = st.radio("Zon", ["Övre (8°C)", "Nedre (16°C)"], horizontal=True)
                if "Övre" in zon:
                    sektion = "Övre"
                    hylla = st.selectbox("Hylla", ["Hylla 1", "Hylla 2", "Hylla 3"])
                else:
                    sektion = "Nedre"
                    hylla = st.selectbox("Hylla", ["Hylla 1", "Hylla 2", "Hylla 3", "Hylla 4"])
            elif plats == "Bokhyllan":
                hylla = st.selectbox("Hylla", ["Övre", "Undre"])
            
            if st.form_submit_button("Spara Vin"):
                if namn:
                    new_id = df['id'].max() + 1 if not df.empty else 1
                    new_row = {"id": new_id, "namn": namn, "argang": arg, "typ": typ, "antal": antal, 
                               "plats": plats, "sektion": sektion, "hylla": hylla, "pris": pris}
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    st.session_state['df'] = df
                    if save_data(df):
                        st.success(f"✅ Sparat! **{namn}** ligger nu på **{plats} {hylla}**")
                        time.sleep(1) # Ge användaren tid att se
                        st.rerun()
                else:
                    st.error("Skriv ett namn!")

    # 2. FLYTTA
    with tab_sort:
        st.subheader("Flytta flaskor")
        # Lista alla viner
        sok = st.selectbox("Välj vin att flytta:", df.apply(lambda x: f"{x['namn']} {x['argang']} ({x['plats']}) ID:{x['id']}", axis=1))
        
        if sok:
            valt_id = int(sok.split("ID:")[1])
            vin_data = df[df['id'] == valt_id].iloc[0]
            
            st.info(f"Nuvarande: {vin_data['plats']} - {vin_data['hylla']}")
            
            with st.form("move_form"):
                ny_plats = st.selectbox("Ny Plats", ["Vinkylen", "Bokhyllan", "Annat"])
                ny_sektion = ""
                ny_hylla = ""
                
                if ny_plats == "Vinkylen":
                    ny_zon = st.radio("Zon", ["Övre", "Nedre"], horizontal=True, key="move_zone")
                    ny_sektion = "Övre" if ny_zon == "Övre" else "Nedre"
                    opts = ["Hylla 1", "Hylla 2", "Hylla 3"] if ny_zon == "Övre" else ["Hylla 1", "Hylla 2", "Hylla 3", "Hylla 4"]
                    ny_hylla = st.selectbox("Ny Hylla", opts)
                elif ny_plats == "Bokhyllan":
                    ny_hylla = st.selectbox("Ny Hylla", ["Övre", "Undre"])
                else:
                    ny_hylla = st.text_input("Beskrivning", "Köksbänken")

                if st.form_submit_button("Flytta"):
                    df.loc[df['id'] == valt_id, ['plats', 'sektion', 'hylla']] = [ny_plats, ny_sektion, ny_hylla]
                    st.session_state['df'] = df
                    save_data(df)
                    st.success(f"✅ Flyttad! Ligger nu på **{ny_plats} {ny_hylla}**")
                    time.sleep(1)
                    st.rerun()

    # 3. ÄNDRA
    with tab_edit:
        st.write("Redigera antal eller ta bort")
        sok_edit = st.selectbox("Välj vin:", df.apply(lambda x: f"{x['namn']} {x['argang']} ID:{x['id']}", axis=1), key="edit_sel")
        if sok_edit:
            eid = int(sok_edit.split("ID:")[1])
            idx = df[df['id'] == eid].index[0]
            
            c1, c2 = st.columns(2)
            nytt_antal = c1.number_input("Antal", 0, 100, int(df.at[idx, 'antal']))
            
            if c1.button("Uppdatera antal"):
                df.at[idx, 'antal'] = nytt_antal
                save_data(df)
                st.success("✅ Antal uppdaterat!")
                st.rerun()
                
            if c2.button("🗑️ TA BORT VIN", type="primary"):
                df = df.drop(idx)
                save_data(df)
                st.warning("🗑️ Vinet raderat.")
                st.rerun()

elif page == "Sommelieren":
    st.title("Din Sommelier")
    c1, c2, c3 = st.columns(3)
    fraga = None
    if c1.button("🕰️ Drickfönster"): fraga = "Vilka flaskor börjar bli gamla? Ge mig topp 3 att dricka nu."
    if c2.button("🎁 Gåva"): fraga = "Föreslå tre gå-bort-viner: Budget, Mellan, Lyx."
    if c3.button("🎲 Överraska"): fraga = "Välj en slumpmässig flaska (max 800kr) och sälj in den!"
    
    inp = st.text_input("Din fråga:", placeholder="Vad passar till pizza?")
    if inp: fraga = inp
    
    if fraga:
        with st.spinner("Sommelieren tänker..."):
            data = df[['namn', 'argang', 'antal', 'plats', 'sektion', 'hylla']].to_string(index=False)
            st.info(get_ai_response(fraga, data))
