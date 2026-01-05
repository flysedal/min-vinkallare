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

# --- 2. KONFIGURATION (HÄR ÄR FIXEN!) ---
def get_google_sheet_client():
    try:
        # VI LÄGGER TILL 'DRIVE' I LISTAN HÄR:
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

# --- 3. DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    section[data-testid="stSidebar"] .stRadio div[role='radiogroup'] > label {
        background-color: #1c1f26; padding: 15px 20px; border-radius: 10px; margin-bottom: 8px; border-left: 5px solid #2e3036; cursor: pointer;
    }
    section[data-testid="stSidebar"] .stRadio div[role='radiogroup'] > label[data-checked="true"] {
        background-color: #5c1a22; border-left: 5px solid #e6c200; color: white;
    }
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; background-color: #5c1a22; color: white; border: none; font-weight: bold; }
    .wine-card { padding: 15px; background-color: #1c1f26; border-radius: 12px; border-left: 4px solid #5c1a22; margin-bottom: 10px; }
    .stat-box { background-color: #1c1f26; padding: 15px; border-radius: 12px; text-align: center; }
    .stat-num { font-size: 24px; font-weight: bold; color: #e6c200; }
    </style>
""", unsafe_allow_html=True)

# --- 4. MASTER CONTEXT ---
MASTER_CONTEXT = """
Du är en personlig sommelier och lagerchef. 
Användaren gillar: Nebbiolo, Barolo, Godello. Hatar: Amarone.
Husvin: Elio Altare Dolcetto.
VIKTIGT: Tala alltid om var flaskan ligger (Plats och Hylla).
"""

# --- 5. DATAFUNKTIONER ---
def load_data():
    """Hämtar data från Google Sheets"""
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
        return df
    except Exception as e:
        st.error(f"Kunde inte läsa Google Sheets: {e}")
        return pd.DataFrame(columns=expected_cols)

def save_data(df):
    """Sparar data till Google Sheets"""
    client = get_google_sheet_client()
    if not client:
        st.error("Kunde inte ansluta till Google.")
        return False

    try:
        sheet = client.open("Min Vinkällare").sheet1
        sheet.clear()
        
        # Fyll tomma värden för att undvika fel
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
            full_prompt = f"Du är ett strikt uppslagsverk om vin. Ge ENDAST intressant fakta om vinet. Inga åsikter. Max 2 meningar.\n\nVIN: {prompt}"
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
    with c1: st.markdown(f"<div class='stat-box'>Totalt<div class='stat-num'>{int(df['antal'].sum()) if not df.empty else 0}</div></div>", unsafe_allow_html=True)
    with c2:
        val = df['pris'].sum() if not df.empty else 0
        visnings_pris = f"{val/1000:.1f}k" if val > 10000 else f"{val:.0f}"
        st.markdown(f"<div class='stat-box'>Värde<div class='stat-num'>{visnings_pris} kr</div></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    col_triv, col_btn = st.columns([3, 1])
    with col_btn:
        st.write("") 
        ny_trivia = st.button("🔄 Ny")
    if 'trivia_text' not in st.session_state or ny_trivia:
        trivia_vin = df.sample(1).iloc[0] if not df.empty else None
        if trivia_vin is not None:
            with st.spinner("Hämtar fakta..."):
                fakta = f"{trivia_vin['namn']} ({trivia_vin['argang']})"
                st.session_state['trivia_text'] = get_ai_response(fakta, '', is_trivia=True)
        else: st.session_state['trivia_text'] = "Källaren verkar tom..."
    with col_triv: st.info(f"💡 **Trivia:** {st.session_state['trivia_text']}")

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
                st.markdown(f"<div class='wine-card'>🍾 <b>{row['namn']}</b><br><small>{row['argang']} | {row['antal']} st</small></div>", unsafe_allow_html=True)
    st.subheader("Nedre Zon (16°C)")
    for i in range(1, 5): 
        hylla = f"Hylla {i}"
        viner = df[(df['plats'] == "Vinkylen") & (df['hylla'] == hylla)]
        count = int(viner['antal'].sum())
        with st.expander(f"{hylla} ({count} st)", expanded=False):
            if viner.empty: st.caption("Tomt")
            for _, row in viner.iterrows():
                st.markdown(f"<div class='wine-card'>🍷 <b>{row['namn']}</b><br><small>{row['argang']} | {row['antal']} st</small></div>", unsafe_allow_html=True)

elif page == "Bokhyllan":
    st.title("📚 Bokhyllan")
    hyllor = ["Övre", "Undre"]
    for h in hyllor:
        viner = df[(df['plats'] == "Bokhyllan") & (df['hylla'] == h)]
        count = int(viner['antal'].sum())
        st.subheader(f"{h} Hylla ({count})")
        if viner.empty: st.caption("Tomt")
        for _, row in viner.iterrows():
            st.markdown(f"<div class='wine-card'><b>{row['namn']}</b> {row['argang']}</div>", unsafe_allow_html=True)

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
    user_input = st.text_input("Vad vill du dricka?", placeholder="Grillat kött...")
    if user_input:
        with st.spinner("Letar i Google Sheets..."):
            relevant_data = df[['namn', 'argang', 'antal', 'plats', 'hylla']].to_string(index=False)
            svar = get_ai_response(user_input, relevant_data, is_trivia=False)
            st.info(svar)
