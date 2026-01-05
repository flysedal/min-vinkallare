import streamlit as st
import pandas as pd
import json
import os
import google.generativeai as genai
from datetime import datetime

st.set_page_config(page_title="Min Vinkällare", page_icon="🍷", layout="wide")

# --- SÄKERHET & LÖSENORD ---
def check_password():
    """Returnerar True om användaren har loggat in korrekt."""
    # Om inga secrets finns (körs lokalt utan config), släpp in direkt eller använd standard
    if "password" not in st.secrets:
        return True

    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Radera lösen från minnet
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Visa inloggning
        st.text_input("Lösenord", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Fel lösenord
        st.text_input("Lösenord", type="password", on_change=password_entered, key="password")
        st.error("😕 Fel lösenord")
        return False
    else:
        # Rätt lösenord
        return True

if not check_password():
    st.stop()  # Stanna här om man inte är inloggad

# --- KONFIGURATION (Hämta nyckel från Secrets) ---
# Lokalt kan du ha kvar din nyckel i secrets.toml eller os.environ, 
# men på webben hämtas den från st.secrets.
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except:
    api_key = "DIN_NYCKEL_HÄR_OM_DU_KÖR_LOKALT" # Fallback

os.environ["GOOGLE_API_KEY"] = api_key

# --- DESIGN (MOBILANPASSAD) ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    
    /* Mobilvänlig meny */
    section[data-testid="stSidebar"] .stRadio div[role='radiogroup'] > label {
        background-color: #1c1f26;
        padding: 15px 20px;
        border-radius: 10px;
        margin-bottom: 8px;
        border-left: 5px solid #2e3036;
        transition: all 0.2s;
        cursor: pointer;
    }
    section[data-testid="stSidebar"] .stRadio div[role='radiogroup'] > label:hover {
        background-color: #2e3036;
        border-left: 5px solid #5c1a22;
    }
    section[data-testid="stSidebar"] .stRadio div[role='radiogroup'] > label[data-checked="true"] {
        background-color: #5c1a22;
        border-left: 5px solid #e6c200;
        color: white;
    }
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; background-color: #5c1a22; color: white; border: none; font-weight: bold; }
    .wine-card { padding: 15px; background-color: #1c1f26; border-radius: 12px; border-left: 4px solid #5c1a22; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .stat-box { background-color: #1c1f26; padding: 15px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .stat-num { font-size: 24px; font-weight: bold; color: #e6c200; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { height: 50px; flex-grow: 1; text-align: center; background-color: #1c1f26; border-radius: 8px; margin-bottom: 5px; }
    .stTabs [aria-selected="true"] { background-color: #5c1a22; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- MASTER CONTEXT ---
MASTER_CONTEXT = """
Du är en personlig sommelier och lagerchef. 
Användaren gillar: Nebbiolo, Barolo, Godello. Hatar: Amarone (om det inte är till gäster).
Husvin: Elio Altare Dolcetto.

Dina uppgifter:
1. Rekommendera BÄSTA matchningen från listan baserat på mat eller humör.
2. VIKTIGT: Du MÅSTE tala om var flaskan ligger (Plats och Hylla). Användaren vill inte leta.
   Exempel: "Ta fram Barolon (Vinkylen, Hylla 2). Den passar utmärkt."

Svara kort, koncist och passionerat.
"""

# --- FUNKTIONER ---
def load_data():
    try:
        with open('vinlagret.json', 'r', encoding='utf-8') as f:
            df = pd.read_json(f)
            df['argang'] = df['argang'].astype(str) 
            return df
    except:
        return pd.DataFrame(columns=["id", "namn", "argang", "typ", "antal", "plats", "sektion", "hylla", "pris"])

def save_data(df):
    df.to_json('vinlagret.json', orient='records', indent=4, force_ascii=False)

def get_ai_response(prompt, inventory_str, is_trivia=False):
    if "DIN_NYCKEL" in os.environ["GOOGLE_API_KEY"]:
        return "⚠️ Ingen API-nyckel konfigurerad i Secrets."
    try:
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        if is_trivia:
            full_prompt = f"Du är ett strikt uppslagsverk om vin. Ge ENDAST intressant fakta (historia, druva, region) om vinet nedan. Inga åsikter om användarens smak. Max 2 meningar.\n\nVIN: {prompt}"
        else:
            full_prompt = f"{MASTER_CONTEXT}\n\nLAGER:\n{inventory_str}\n\nFRÅGA: {prompt}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"🍷 AI:n tar en tupplur. (Fel: {str(e)})"

# --- APP START ---
df = load_data()

with st.sidebar:
    st.header("🍷 Vinkällaren")
    st.write("") 
    page = st.radio("Meny", ["Översikt", "Vinkylen", "Bokhyllan", "Lagerhantering", "Sommelieren"], label_visibility="collapsed")

# --- SIDA: ÖVERSIKT ---
if page == "Översikt":
    st.title("Översikt")
    c1, c2 = st.columns(2)
    with c1: st.markdown(f"<div class='stat-box'>Totalt<div class='stat-num'>{int(df['antal'].sum()) if not df.empty else 0}</div></div>", unsafe_allow_html=True)
    with c2:
        val = df['pris'].sum() if not df.empty else 0
        visnings_pris = f"{val/1000:.1f}k" if val > 10000 else f"{val:.0f}"
        st.markdown(f"<div class='stat-box'>Värde<div class='stat-num'>{visnings_pris} kr</div></div>", unsafe_allow_html=True)
    st.write("")
    osorterade = df[df['plats'] == 'Osorterat']['antal'].sum()
    if osorterade > 0: st.error(f"⚠️ Du har {int(osorterade)} flaskor att sortera in!")
    else: st.success("✅ Allt är i ordning i källaren.")
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
        else: st.session_state['trivia_text'] = "Lägg in lite viner först!"
    with col_triv: st.info(f"💡 **Trivia:** {st.session_state['trivia_text']}")
    
    st.markdown("---")
    st.subheader("🕰️ Drickdags?")
    if not df.empty:
        numeric_argang = pd.to_numeric(df['argang'], errors='coerce')
        old_wines = df[ (numeric_argang.notna()) & (numeric_argang < 2016) ]
        if not old_wines.empty:
            for _, row in old_wines.head(5).iterrows():
                 st.warning(f"**{row['namn']} {row['argang']}** ({row['plats']})")
        else: st.caption("Inga viner äldre än 2016.")

# --- SIDA: VINKYLEN ---
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

# --- SIDA: BOKHYLLAN ---
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

# --- SIDA: LAGERHANTERING ---
elif page == "Lagerhantering":
    st.title("Lagerhantering")
    tab_add, tab_sort, tab_edit = st.tabs(["➕ Lägg till", "📦 Sortera", "✏️ Ändra"])
    
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
            st.write("---")
            st.write("**Placering**")
            vald_plats = st.selectbox("Plats", ["Osorterat", "Vinkylen", "Bokhyllan"])
            vald_hylla = ""
            if vald_plats == "Vinkylen": vald_hylla = st.selectbox("Hylla", ["Hylla 1", "Hylla 2", "Hylla 3", "Hylla 4"])
            elif vald_plats == "Bokhyllan": vald_hylla = st.selectbox("Hylla", ["Övre", "Undre"])
            st.write("")
            submit_ny = st.form_submit_button("Spara vin")
            if submit_ny and ny_namn:
                new_id = df['id'].max() + 1 if not df.empty else 1
                new_row = {"id": new_id, "namn": ny_namn, "argang": ny_arg, "typ": ny_typ, "antal": ny_antal, "plats": vald_plats, "sektion": "", "hylla": vald_hylla, "pris": ny_pris}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
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
                st.write("")
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

# --- SIDA: SOMMELIEREN ---
elif page == "Sommelieren":
    st.title("Din Sommelier")
    st.write("Vad vill du dricka ikväll?")
    c1, c2, c3 = st.columns(3)
    if c1.button("🥩 Kött"): fraga = "Jag ska äta en rejäl köttbit. Vad i källaren passar bäst?"
    elif c2.button("🍝 Pasta"): fraga = "Jag lagar pasta ikväll. Ge mig ett bra italienskt alternativ."
    elif c3.button("🥂 Bubbel"): fraga = "Jag vill fira! Vilket bubbel är bäst just nu?"
    else: fraga = None
    user_input = st.text_input("", placeholder="Eller skriv din fråga här...")
    if user_input: fraga = user_input
    if fraga:
        with st.spinner("Sommelieren letar i hyllorna..."):
            relevant_data = df[['namn', 'argang', 'antal', 'plats', 'hylla']].to_string(index=False)
            svar = get_ai_response(fraga, relevant_data, is_trivia=False)
            st.markdown(f"**Fråga:** {fraga}")
            st.info(svar)