import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import google.generativeai as genai
import time
from datetime import datetime

st.set_page_config(page_title="Min Vinkällare", page_icon="🍷", layout="wide")

# --- 1. SÄKERHET ---
def check_password():
    if "password" not in st.secrets: return True
    if st.session_state.get("password_correct", False): return True
    if "password_input" in st.session_state:
        if st.session_state["password_input"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
            return True
        else: st.error("😕 Fel lösenord")
    st.text_input("Lösenord", type="password", key="password_input")
    return False

if not check_password(): st.stop()

# --- 2. KONFIGURATION ---
def get_google_sheet_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client
    except: return None

if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]

# --- 3. DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA; color: #2C3E50; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    section[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E9ECEF; }
    .wine-card { padding: 20px; background-color: #FFFFFF; border-radius: 12px; margin-bottom: 15px; border-left: 5px solid #722F37; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .wine-title { font-size: 18px; font-weight: bold; color: #2C3E50; margin-bottom: 5px; }
    .wine-info { color: #6C757D; font-size: 14px; }
    .stat-box { background-color: #FFFFFF; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #E9ECEF; }
    .stat-num { font-size: 32px; font-weight: 700; color: #722F37; margin-top: 5px; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #722F37; color: white; border: none; font-weight: 600; }
    .stButton>button:hover { background-color: #5a232b; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- 4. MASTER CONTEXT (UPPDATERAD FRÅN DITT DOKUMENT) ---
MASTER_CONTEXT = """
Du är en "Modern Purist" Sommelier. Din uppgift är att matcha användarens strikta profil.

## DIN PROFIL & FILOSOFI
- **Stil:** Du söker elegans, struktur och terroir (svalt klimat, hög syra, mineralitet).
- **Avsky:** "Sminkade" viner (vanilj/ek-bomber, restsötma, syltig frukt), Amarone/Ripasso, Prosecco, "Hipster-naturvin" (stall/defekter) och USA-viner.
- **Motto:** "My House, My Rules". Vi dricker det vi gillar, inte publikfriare.

## REGIONER & PREFERENSER
- **Italien:** - Piemonte: Gillar modern Barolo (Altare, Scavino) men även ren traditionell. 
  - *Husvins-paradoxen:* Hatar Dolcetto generellt, MEN älskar Elio Altare Dolcetto.
  - Toscana: Chianti Classico & Supertoscanare (Sangiovese/Bordeaux-blend).
- **Spanien/Portugal:** "Det Atlantiska Spåret". Gillar Godello, Albariño, sval Garnacha (Gredos). Avskyr traditionell "vanilj-Rioja".
- **Frankrike:** Cru Beaujolais, Champagne (strukturerad/vinös), Jura (Ouillé/toppad), Loire (Cab Franc), Chablis (Hus-stil för vitt).
- **Nya Världen:** Endast Sydafrika (Crystallum).

## REKOMMENDATIONS-REGLER
1. **Drickfönster:** Prio 1 är att varna för viner som håller på att tappa frukten.
2. **Alltid Två Förslag:** - A) Det Trygga (Matchar profilen perfekt, t.ex. Altare/Atlantiskt).
   - B) Utmaningen (Vidgar vyerna, t.ex. udda region men rätt struktur).
3. **Lokalisering:** Tala ALLTID om var flaskan ligger (Plats & Hylla).
"""

# --- 5. DATAFUNKTIONER ---
def load_data():
    """Hämtar data. Förväntar sig en rad per flaska."""
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

def load_history():
    client = get_google_sheet_client()
    if not client: return pd.DataFrame()
    try:
        spreadsheet = client.open("Min Vinkällare")
        try: sheet = spreadsheet.worksheet("Historik")
        except: 
            sheet = spreadsheet.add_worksheet(title="Historik", rows="1000", cols="20")
            sheet.append_row(["Datum", "Namn", "Årgång", "Typ", "Pris", "Kommentar"])
        return pd.DataFrame(sheet.get_all_records())
    except: return pd.DataFrame()

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

def log_to_history(wine_data, comment="Drack ur"):
    client = get_google_sheet_client()
    if not client: return False
    try:
        spreadsheet = client.open("Min Vinkällare")
        try: sheet = spreadsheet.worksheet("Historik")
        except:
            sheet = spreadsheet.add_worksheet(title="Historik", rows="1000", cols="20")
            sheet.append_row(["Datum", "Namn", "Årgång", "Typ", "Pris", "Kommentar"])
        today = datetime.now().strftime("%Y-%m-%d")
        row = [today, wine_data['namn'], str(wine_data['argang']), wine_data['typ'], wine_data['pris'], comment]
        sheet.append_row(row)
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

# --- 6. APP START ---
if 'df' not in st.session_state:
    st.session_state['df'] = load_data()

df = st.session_state['df']

with st.sidebar:
    st.header("🍷 Vinkällaren")
    page = st.radio("Meny", ["Översikt", "Vinkylen", "Bokhyllan", "Lagerhantering", "Sommelieren", "📜 Historik"], label_visibility="collapsed")
    st.write("---")
    if st.button("🔄 Ladda om data"):
        st.session_state['df'] = load_data()
        st.rerun()

# --- SIDOR ---
if page == "Översikt":
    st.title("Översikt")
    c1, c2 = st.columns(2)
    # Räknar nu rader (len) eftersom varje flaska är en rad
    total_count = len(df)
    with c1: st.markdown(f"<div class='stat-box'><div class='stat-label'>Totalt</div><div class='stat-num'>{total_count} st</div></div>", unsafe_allow_html=True)
    with c2: 
        val = df['pris'].sum() if not df.empty else 0
        st.markdown(f"<div class='stat-box'><div class='stat-label'>Värde</div><div class='stat-num'>{val/1000:.1f}k kr</div></div>", unsafe_allow_html=True)
    
    st.write("---")
    col_tr, col_btn = st.columns([3,1])
    with col_btn: 
        if st.button("Ny Trivia"): st.session_state.pop('trivia_vin_namn', None)

    if 'trivia_vin_namn' not in st.session_state:
        trivia_vin = df.sample(1).iloc[0] if not df.empty else None
        if trivia_vin is not None:
            st.session_state['trivia_vin_namn'] = f"{trivia_vin['namn']} ({trivia_vin['argang']})"
            with st.spinner("Hämtar fakta..."):
                fakta = f"{trivia_vin['namn']} {trivia_vin['argang']}"
                st.session_state['trivia_text'] = get_ai_response(fakta, '', True)
    with col_tr:
        if 'trivia_vin_namn' in st.session_state:
            st.info(f"💡 **{st.session_state['trivia_vin_namn']}**\n\n{st.session_state['trivia_text']}")

elif page == "Vinkylen":
    st.title("🧊 mQuvée 126")
    st.subheader("Övre Zon (8°C)")
    for i in range(1, 4): 
        hylla = f"Hylla {i}"
        viner = df[(df['plats'] == "Vinkylen") & (df['hylla'] == hylla) & (df['sektion'] == "Övre")]
        with st.expander(f"{hylla} ({len(viner)} st)", expanded=False):
            for _, row in viner.iterrows():
                st.markdown(f"<div class='wine-card'><div class='wine-title'>🍾 {row['namn']}</div><div class='wine-info'>{row['argang']}</div></div>", unsafe_allow_html=True)

    st.subheader("Nedre Zon (16°C)")
    for i in range(1, 5): 
        hylla = f"Hylla {i}"
        viner = df[(df['plats'] == "Vinkylen") & (df['hylla'] == hylla) & (df['sektion'] == "Nedre")]
        with st.expander(f"{hylla} ({len(viner)} st)", expanded=False):
            for _, row in viner.iterrows():
                st.markdown(f"<div class='wine-card'><div class='wine-title'>🍷 {row['namn']}</div><div class='wine-info'>{row['argang']}</div></div>", unsafe_allow_html=True)

elif page == "Bokhyllan":
    st.title("📚 Bokhyllan")
    for h in ["Övre", "Undre"]:
        viner = df[(df['plats'] == "Bokhyllan") & (df['hylla'] == h)]
        with st.expander(f"{h} Hylla ({len(viner)})", expanded=True):
            for _, row in viner.iterrows():
                st.markdown(f"<div class='wine-card'><div class='wine-title'>{row['namn']}</div><div class='wine-info'>{row['argang']}</div></div>", unsafe_allow_html=True)

elif page == "Lagerhantering":
    st.title("Lagerhantering")
    tab_add, tab_sort, tab_edit = st.tabs(["➕ Lägg till", "📦 Flytta", "✏️ Hantera"])
    
    # LÄGG TILL FLERA FLASKOR (LOOPAR RADER)
    with tab_add:
        st.subheader("Nytt inköp")
        with st.form("add_form"):
            namn = st.text_input("Namn")
            c1, c2 = st.columns(2)
            arg = c1.text_input("Årgång", "2025")
            antal_att_lagga_till = c2.number_input("Antal flaskor", 1, 24, 1)
            typ = st.selectbox("Typ", ["Rött", "Vitt", "Bubbel", "Rosé", "Sött"])
            pris = st.number_input("Pris (kr)", 0, 100000, 0)
            
            st.markdown("**Placering**")
            plats = st.selectbox("Var?", ["Vinkylen", "Bokhyllan", "Osorterat"])
            sektion, hylla = "", ""
            if plats == "Vinkylen":
                zon = st.radio("Zon", ["Övre (8°C)", "Nedre (16°C)"], horizontal=True)
                sektion = "Övre" if "Övre" in zon else "Nedre"
                opts = ["Hylla 1", "Hylla 2", "Hylla 3"] if sektion == "Övre" else ["Hylla 1", "Hylla 2", "Hylla 3", "Hylla 4"]
                hylla = st.selectbox("Hylla", opts)
            elif plats == "Bokhyllan": hylla = st.selectbox("Hylla", ["Övre", "Undre"])
            
            if st.form_submit_button("Spara Viner"):
                if namn:
                    new_rows = []
                    current_max_id = df['id'].max() if not df.empty else 0
                    # Skapar en rad per flaska
                    for i in range(antal_att_lagga_till):
                        new_row = {"id": current_max_id + 1 + i, "namn": namn, "argang": arg, "typ": typ, "antal": 1, 
                                   "plats": plats, "sektion": sektion, "hylla": hylla, "pris": pris}
                        new_rows.append(new_row)
                    
                    df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                    st.session_state['df'] = df
                    if save_data(df):
                        st.success(f"✅ Sparat! {antal_att_lagga_till} st **{namn}** inlagda.")
                        time.sleep(1.5)
                        st.rerun()
                else: st.error("Skriv ett namn!")

    with tab_sort:
        st.subheader("Flytta enskild flaska")
        sok = st.selectbox("Välj flaska:", df.apply(lambda x: f"{x['namn']} {x['argang']} ({x['plats']}) ID:{x['id']}", axis=1))
        if sok:
            valt_id = int(sok.split("ID:")[1])
            with st.form("move_form"):
                ny_plats = st.selectbox("Ny Plats", ["Vinkylen", "Bokhyllan", "Annat"])
                ny_sektion, ny_hylla = "", ""
                if ny_plats == "Vinkylen":
                    ny_zon = st.radio("Zon", ["Övre", "Nedre"], horizontal=True, key="m_zon")
                    ny_sektion = "Övre" if ny_zon == "Övre" else "Nedre"
                    opts = ["Hylla 1", "Hylla 2", "Hylla 3"] if ny_sektion == "Övre" else ["Hylla 1", "Hylla 2", "Hylla 3", "Hylla 4"]
                    ny_hylla = st.selectbox("Ny Hylla", opts)
                elif ny_plats == "Bokhyllan": ny_hylla = st.selectbox("Ny Hylla", ["Övre", "Undre"])
                else: ny_hylla = st.text_input("Beskrivning", "Köksbänken")

                if st.form_submit_button("Flytta"):
                    df.loc[df['id'] == valt_id, ['plats', 'sektion', 'hylla']] = [ny_plats, ny_sektion, ny_hylla]
                    save_data(df)
                    st.success(f"✅ Flyttad!")
                    time.sleep(1)
                    st.rerun()

    with tab_edit:
        st.subheader("Hantera flaska")
        sok_edit = st.selectbox("Välj flaska:", df.apply(lambda x: f"{x['namn']} {x['argang']} ID:{x['id']}", axis=1), key="edit_sel")
        if sok_edit:
            eid = int(sok_edit.split("ID:")[1])
            idx = df[df['id'] == eid].index[0]
            vin_data = df.loc[idx]
            
            c1, c2 = st.columns(2)
            if c1.button("🥂 Drack ur (Historik)", type="primary"):
                log_to_history(vin_data, comment="Drack ur")
                df = df.drop(idx)
                save_data(df)
                st.success(f"✅ Skål! Sparad i historik.")
                time.sleep(1.5)
                st.rerun()
            
            if c2.button("🗑️ Radera (Ingen historik)"):
                df = df.drop(idx)
                save_data(df)
                st.warning("Raderad.")
                time.sleep(1)
                st.rerun()

elif page == "Sommelieren":
    st.title("Din Sommelier")
    c1, c2, c3 = st.columns(3)
    fraga = None
    
    # FILTER-LOGIK: Exkluderar 1989 Champagne för Drickfönster-frågor
    if c1.button("🕰️ Drickfönster"): 
        fraga = "Vilka flaskor börjar bli gamla? Ge mig topp 3 att dricka nu (Prio: Modern Purist)."
        # Vi sätter en flagga för att filtrera datan senare
        st.session_state['filter_1989'] = True
    else:
        if 'filter_1989' not in st.session_state: st.session_state['filter_1989'] = False

    if c2.button("🎁 Gåva"): fraga = "Föreslå tre gå-bort-viner: Budget, Mellan, Lyx."
    if c3.button("🎲 Överraska"): fraga = "Välj en slumpmässig flaska (max 800kr) och sälj in den till en Modern Purist!"
    
    inp = st.text_input("Din fråga:", placeholder="Vad passar till pizza?")
    if inp: fraga = inp
    
    if fraga:
        with st.spinner("Sommelieren tänker..."):
            # Kopiera df för att inte påverka originalet
            df_context = df.copy()
            
            # Applicera filter om det är en Drickfönster-fråga (eller om flaggan är satt)
            if st.session_state.get('filter_1989') or "drickfönster" in fraga.lower() or "gamla" in fraga.lower():
                # Filtrera bort årgång 1989
                df_context = df_context[df_context['argang'] != '1989']
                # Nollställ flaggan
                st.session_state['filter_1989'] = False
            
            data = df_context[['namn', 'argang', 'plats', 'sektion', 'hylla']].to_string(index=False)
            st.info(get_ai_response(fraga, data))

elif page == "📜 Historik":
    st.title("📜 Drinkhistorik")
    df_hist = load_history()
    if df_hist.empty: st.info("Ingen historik än.")
    else:
        try: df_hist = df_hist.sort_values(by="Datum", ascending=False)
        except: pass
        for _, row in df_hist.iterrows():
            st.markdown(f"<div class='wine-card' style='border-left: 5px solid #6C757D;'><div class='wine-title' style='color:#6C757D;'>🍾 {row['Namn']} <span style='font-size:0.8em;'>({row['Årgång']})</span></div><div class='wine-info'>{row['Datum']} | {row['Pris']} kr</div></div>", unsafe_allow_html=True)
