import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import google.generativeai as genai
import json

st.set_page_config(page_title="Min Vinkällare", page_icon="🍷", layout="wide")

# --- 1. SÄKERHET & LÖSENORD ---
def check_password():
    if "password" not in st.secrets:
        return True 

    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Lösenord", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Lösenord", type="password", on_change=password_entered, key="password")
        st.error("😕 Fel lösenord")
        return False
    else:
        return True

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
        background-color: #F1F3F5; padding: 15px 20px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #DEE2E6; transition: all 0.2s; cursor: pointer; color: #495057; font-weight: 500;
    }
    section[data-testid="stSidebar"] .stRadio div[role='radiogroup'] > label:hover {
        background-color: #E9ECEF; border-left: 5px solid #722F37; 
    }
    section[data-testid="stSidebar"] .stRadio div[role='radiogroup'] > label[data-checked="true"] {
        background-color: #722F37; border-left: 5px solid #4A1A21; color: white; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #722F37; color: white; border: none; font-weight: 600; font-size: 16px; transition: background-color 0.2s; }
    .stButton>button:hover { background-color: #5a232b; color: white; }
    .stButton>button:active { background-color: #4a1a21; }

    .wine-card { padding: 20px; background-color: #FFFFFF; border-radius: 12px; margin-bottom: 15px; border-left: 5px solid #722F37; box-shadow: 0 4px 12px rgba(0,0,0,0.05); transition: transform 0.2s; }
    .wine-card:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0,0,0,0.1); }
    .wine-title { font-size: 18px; font-weight: bold; color: #2C3E50; margin-bottom: 5px; }
    .wine-info { color: #6C757D; font-size: 14px; }

    .stat-box { background-color: #FFFFFF; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #E9ECEF; }
    .stat-label { font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #6C757D; }
    .stat-num { font-size: 32px; font-weight: 700; color: #722F37; margin-top: 5px; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E9ECEF; color: #495057; }
    .stTabs [aria-selected="true"] { background-color: #722F37; color: white; border: none; }
    .stAlert { border-radius: 8px; }
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
        
        if df.empty or 'plats' not in df.columns:
            return pd.DataFrame(columns=expected_cols)

        df['argang'] = df['argang'].astype(str)
        # Säkerställ att pris är siffror för sortering/filtrering
        df['pris'] = pd.to_numeric(df['pris'], errors='coerce').fillna(0)
        return df
    except Exception as e:
        return pd.DataFrame(columns=expected_cols)

def save_data(df):
    client = get_google_sheet_client()
    if not client:
        st.error("Kunde inte ansluta till Google.")
        return False

    try:
        sheet = client.open("Min Vinkällare").sheet1
        sheet.clear()
        df_clean = df.fillna("")
        data_to_write = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        sheet.update(range_name='A1', values=data_to_write)
        return True
    except Exception as e:
        st.error(f"Kunde inte spara till Google Sheets: {e}")
        return False

def get_ai_response(prompt, inventory_str, is_trivia=False):
    if "GOOGLE_API_KEY" not in os.environ: return "⚠️ Ingen API-nyckel."
    try:
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        if is_trivia:
            # Uppdaterad prompt för mer frihet och koppling till flaskan
            full_prompt = f"Du är en vinkännare. Ge en intressant, fascinerande eller nördig fakta/anekdot kopplat till vinet nedan (dess druva, region eller historia). Var kreativ! Max 2 meningar.\n\nVIN: {prompt}"
        else:
            full_prompt = f"{MASTER_CONTEXT}\n\nLAGER:\n{inventory_str}\n\nFRÅGA: {prompt}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"🍷 AI:n sover. (Fel: {str(e)})"

# --- 6. APP START ---
if 'df' not in st.session_state:
    st.session_state['df'] = load_data()

df = st.session_state['df']

with st.sidebar:
    st.header("🍷 Vinkällaren")
    st.write("") 
    page = st.radio("Meny", ["Översikt", "Vinkylen", "Bokhyllan", "Lagerhantering", "Sommelieren"], label_visibility="collapsed")
    st.write("---")
    if st.button("🔄 Ladda om data"):
        st.session_state['df'] = load_data()
        st.rerun()

# --- SIDOR ---
if page == "Översikt":
    st.title("Översikt")
    
    c1, c2 = st.columns(2)
    with c1: 
        st.markdown(f"""
        <div class='stat-box'>
            <div class='stat-label'>Totalt i lager</div>
            <div class='stat-num'>{int(df['antal'].sum()) if not df.empty else 0} fl</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        val = df['pris'].sum() if not df.empty else 0
        visnings_pris = f"{val/1000:.1f}k" if val > 10000 else f"{val:.0f}"
        st.markdown(f"""
        <div class='stat-box'>
            <div class='stat-label'>Estimerat värde</div>
            <div class='stat-num'>{visnings_pris} kr</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Trivia-sektionen
    col_triv, col_btn = st.columns([3, 1])
    with col_btn:
        st.write("") 
        ny_trivia = st.button("🔄 Ny Trivia")
    
    if 'trivia_vin_namn' not in st.session_state or ny_trivia:
        trivia_vin = df.sample(1).iloc[0] if not df.empty else None
        if trivia_vin is not None:
            # Spara vinet i session state så det inte byts om sidan laddas om av misstag
            st.session_state['trivia_vin_namn'] = f"{trivia_vin['namn']} ({trivia_vin['argang']})"
            with st.spinner("Hämtar fakta..."):
                fakta_prompt = f"{trivia_vin['namn']} {trivia_vin['argang']} från {trivia_vin['typ']}"
                st.session_state['trivia_text'] = get_ai_response(fakta_prompt, '', is_trivia=True)
        else: 
            st.session_state['trivia_vin_namn'] = "Tomt i källaren"
            st.session_state['trivia_text'] = "Lägg in viner för att få fakta!"
    
    with col_triv: 
        # Här visar vi flaskans namn tydligt ovanför texten
        st.info(f"💡 **{st.session_state['trivia_vin_namn']}**\n\n{st.session_state['trivia_text']}")

elif page == "Vinkylen":
    st.title("🧊 mQuvée 126")
    st.subheader("Övre Zon (8°C)")
    for i in range(1, 4): 
        hylla = f"Hylla {i}"
        viner = df[(df['plats'] == "Vinkylen") & (df['hylla'] == hylla)]
        count = int(viner['antal'].sum())
        with st.expander(f"{hylla} ({count} st)", expanded=False):
            if viner.empty: st.caption("Tomt")
            for _, row in viner.iterrows():
                st.markdown(f"""
                <div class='wine-card'>
                    <div class='wine-title'>🍾 {row['namn']}</div>
                    <div class='wine-info'>Årgång: {row['argang']} | Antal: <b>{row['antal']} st</b></div>
                </div>
                """, unsafe_allow_html=True)
                
    st.subheader("Nedre Zon (16°C)")
    for i in range(1, 5): 
        hylla = f"Hylla {i}"
        viner = df[(df['plats'] == "Vinkylen") & (df['hylla'] == hylla)]
        count = int(viner['antal'].sum())
        with st.expander(f"{hylla} ({count} st)", expanded=False):
            if viner.empty: st.caption("Tomt")
            for _, row in viner.iterrows():
                st.markdown(f"""
                <div class='wine-card'>
                    <div class='wine-title'>🍷 {row['namn']}</div>
                    <div class='wine-info'>Årgång: {row['argang']} | Antal: <b>{row['antal']} st</b></div>
                </div>
                """, unsafe_allow_html=True)

elif page == "Bokhyllan":
    st.title("📚 Bokhyllan")
    hyllor = ["Övre", "Undre"]
    for h in hyllor:
        viner = df[(df['plats'] == "Bokhyllan") & (df['hylla'] == h)]
        count = int(viner['antal'].sum())
        st.subheader(f"{h} Hylla ({count})")
        if viner.empty: st.caption("Tomt")
        for _, row in viner.iterrows():
            st.markdown(f"""
            <div class='wine-card'>
                <div class='wine-title'>{row['namn']}</div>
                <div class='wine-info'>Årgång: {row['argang']} | Antal: <b>{row['antal']} st</b></div>
            </div>
            """, unsafe_allow_html=True)

elif page == "Lagerhantering":
    st.title("Lagerhantering")
    tab_add, tab_sort, tab_edit, tab_import = st.tabs(["➕ Lägg till", "📦 Sortera", "✏️ Ändra", "📥 Importera"])
    
    with tab_add:
        st.subheader("Nytt inköp")
        with st.form("add_wine_form"):
            ny_namn = st.text_input("Vinnamn")
            c1, c2 = st.columns(2)
            ny_arg = c1.text_input("Årgång", value="2025")
            ny_antal = c2.number_input("Antal", min_value=1, value=1)
            c3, c4 = st.columns(2)
            ny_typ = c3.selectbox("Typ", ["Rött", "Vitt", "Mousserande", "Rosé", "Sött"])
            ny_pris = c4.number_input("Pris", min_value=0)
            st.write("**Placering**")
            vald_plats = st.selectbox("Plats", ["Osorterat", "Vinkylen", "Bokhyllan"])
            vald_hylla = ""
            if vald_plats == "Vinkylen": vald_hylla = st.selectbox("Hylla", ["Hylla 1", "Hylla 2", "Hylla 3", "Hylla 4"])
            elif vald_plats == "Bokhyllan": vald_hylla = st.selectbox("Hylla", ["Övre", "Undre"])
            submit_ny = st.form_submit_button("Spara till Google Sheets")

            if submit_ny and ny_namn:
                new_id = df['id'].max() + 1 if not df.empty else 1
                new_row = {"id": new_id, "namn": ny_namn, "argang": ny_arg, "typ": ny_typ, "antal": ny_antal, "plats": vald_plats, "sektion": "", "hylla": vald_hylla, "pris": ny_pris}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state['df'] = df
                save_data(df)
                st.success(f"✅ {ny_namn} sparad!")
                st.rerun()

    with tab_sort:
        st.subheader("Sortera in viner")
        osorterade = df[df['plats'] == "Osorterat"]
        if osorterade.empty: st.info("Allt är sorterat!")
        else:
            vin_val = osorterade.apply(lambda x: f"{x['namn']} {x['argang']} (ID: {x['id']})", axis=1)
            vin_att_flytta = st.selectbox("Välj flaska:", vin_val)
            if vin_att_flytta:
                valt_id = int(vin_att_flytta.split("(ID: ")[1].replace(")", ""))
                valt_vin = df[df['id'] == valt_id].iloc[0]
                ny_plats = st.selectbox("Till:", ["Vinkylen", "Bokhyllan", "Annat"], key="p_select")
                if ny_plats == "Vinkylen": ny_hylla = st.selectbox("Hylla:", ["Hylla 1", "Hylla 2", "Hylla 3", "Hylla 4"], key="h_select")
                elif ny_plats == "Bokhyllan": ny_hylla = st.selectbox("Hylla:", ["Övre", "Undre"], key="h_select_b")
                else: ny_hylla = st.text_input("Plats:", placeholder="T.ex. Köksbänken")
                if st.button("Flytta flaskan"):
                    df.loc[df['id'] == valt_id, 'plats'] = ny_plats
                    df.loc[df['id'] == valt_id, 'hylla'] = ny_hylla
                    save_data(df)
                    st.success("Flyttad!")
                    st.rerun()

    with tab_edit:
        st.subheader("Ändra / Ta bort")
        sok_lista = df.apply(lambda x: f"{x['namn']} {x['argang']} (ID: {x['id']})", axis=1)
        edit_vin_str = st.selectbox("Sök vin:", sok_lista, key="edit_search")
        if edit_vin_str:
            valt_id_edit = int(edit_vin_str.split("(ID: ")[1].replace(")", ""))
            idx = df[df['id'] == valt_id_edit].index[0]
            with st.form("edit_form"):
                nytt_namn = st.text_input("Namn", df.at[idx, 'namn'])
                c1, c2 = st.columns(2)
                nytt_antal = c1.number_input("Antal", value=int(df.at[idx, 'antal']))
                ny_plats_edit = c2.text_input("Plats", df.at[idx, 'plats'])
                col_save, col_del = st.columns(2)
                spara = col_save.form_submit_button("Spara ändringar")
                ta_bort = col_del.form_submit_button("🗑️ Ta bort", type="primary")
                if spara:
                    df.at[idx, 'namn'] = nytt_namn
                    df.at[idx, 'antal'] = nytt_antal
                    df.at[idx, 'plats'] = ny_plats_edit
                    save_data(df)
                    st.success("Uppdaterat!")
                    st.rerun()
                if ta_bort:
                    df = df.drop(idx)
                    save_data(df)
                    st.success("Borta!")
                    st.rerun()
                    
    with tab_import:
        st.subheader("Importera från JSON")
        st.warning("⚠️ Detta skriver över allt i Google Sheets med innehållet i vinlagret.json!")
        if st.button("🚀 Läs in från vinlagret.json till Sheets"):
            st.info("Läser in data från fil...")
            try:
                with open('vinlagret.json', 'r', encoding='utf-8') as f:
                    json_data = pd.read_json(f)
                
                st.info(f"Hittade {len(json_data)} viner. Sparar till molnet...")
                
                if save_data(json_data):
                    st.session_state['df'] = json_data
                    st.success("Succé! Vinerna är uppladdade.")
                    st.balloons()
                else:
                    st.error("Kunde inte spara till Google. Kolla loggarna.")
            except Exception as e:
                st.error(f"Kunde inte importera: {e}")

elif page == "Sommelieren":
    st.title("Din Sommelier")
    
    # --- NYA KNAPPARNA ---
    c1, c2, c3 = st.columns(3)
    
    fraga = None

    if c1.button("🕰️ Drickfönster"):
        fraga = "Analysera mitt lager. Vilka flaskor börjar bli gamla eller är i sitt perfekta drickfönster nu? Ge mig en topp 3-lista som jag bör öppna snart."
    
    if c2.button("🎁 Gå-bort-present"):
        fraga = "Jag ska bort på middag. Föreslå tre flaskor ur källaren att ge bort i present: en Enkel (vardag), en Mellan (helg) och en Lyxig (speciell). Motivera valen."
    
    if c3.button("🎲 Överraska mig!"):
        # HÄR ÄR SPÄRREN: Välj bara viner under 800 kr för "slumpen"
        vardagsviner = df[df['pris'] < 800]
        
        if not vardagsviner.empty:
            # Välj en slumpmässig rad
            slump_vin = vardagsviner.sample(1).iloc[0]
            fraga = f"Jag vill bli överraskad ikväll och har plockat fram {slump_vin['namn']} ({slump_vin['argang']}). Varför är det ett kul val just nu? (Berätta också exakt var den ligger)."
        else:
            fraga = "Välj en slumpmässig flaska ur källaren som är drickfärdig nu."

    # Manuellt inmatningsfält
    user_input = st.text_input("Eller skriv din fråga:", placeholder="T.ex. Vad passar till asiatiskt?")
    if user_input:
        fraga = user_input

    if fraga:
        with st.spinner("Sommelieren tänker..."):
            relevant_data = df[['namn', 'argang', 'antal', 'plats', 'hylla']].to_string(index=False)
            svar = get_ai_response(fraga, relevant_data, is_trivia=False)
            if user_input: # Visa bara frågan om man skrev den själv
                st.markdown(f"**Fråga:** {fraga}")
            st.info(svar)
