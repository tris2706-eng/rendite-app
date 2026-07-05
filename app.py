import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import newton
import plotly.graph_objects as go
import plotly.express as px

# --- Seiten-Konfiguration & Modernes Dark-Theme ---
st.set_page_config(page_title="Meine Rendite", page_icon="📈", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    h1, h2, h3 { color: #FFFFFF !important; font-family: 'Segoe UI', Tahoma, sans-serif; }
    .stMetric label { color: #A0AEC0 !important; font-weight: bold; }
    .stMetric value { color: #FFFFFF !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #1E2329; border-radius: 8px 8px 0 0; padding: 10px 20px; }
    .stTabs [aria-selected="true"] { background-color: #2ECC71 !important; color: #000000 !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("📈 Mein Finanz-Dashboard")

# --- Datei-Upload ---
uploaded_file = st.file_uploader("Trade Republic CSV hochladen (Am besten den kompletten 'Aktivitäten'-Export)", type="csv")

if uploaded_file is not None:
    try:
        # Robustes Einlesen (Komma oder Semikolon, UTF-8)
        try:
            df = pd.read_csv(uploaded_file)
            if 'date' not in df.columns and 'Datum' not in df.columns:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, sep=';', on_bad_lines='skip')
        except:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=';', on_bad_lines='skip')

        # Spaltennamen normalisieren (Englisch & Deutsch)
        col_mapping = {
            'Datum': 'date', 'Transaktionen': 'type', 'Typ': 'type',
            'Summe': 'amount', 'Betrag': 'amount', 'Total': 'total',
            'Gewinn/Verlust': 'profit'
        }
        df = df.rename(columns=lambda x: col_mapping.get(x, x))
        
        # Datum umwandeln
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=True)
            df['year'] = df['date'].dt.year
        else:
            st.error("Fehler: Konnte keine Datums-Spalte finden.")
            st.stop()

        # Tabs erstellen
        tab1, tab2, tab3 = st.tabs(["💶 Jahres-Performance", "📊 Rendite (IZF)", "💰 Cashflow"])

        # === TAB 1: eToro-Style Chart (Realisierter Gewinn) ===
        with tab1:
            st.subheader("Dein realisierter Gewinn nach Jahren")
            
            yearly_profit = pd.DataFrame()
            
            # Wir nutzen die exakte Gewinn/Verlust Spalte von Trade Republic für absolute Genauigkeit
            if 'profit' in df.columns:
                # Kommas in Punkte umwandeln für die Mathematik
                df['profit'] = pd.to_numeric(df['profit'].astype(str).replace(',', '.', regex=True), errors='coerce')
                yearly_profit = df.groupby('year')['profit'].sum().reset_index()
            else:
                st.warning("In dieser CSV fehlt die 'Gewinn/Verlust' Spalte. Zeige nur Dividenden/Zinsen als Ertrag.")
                yields = df[df['type'].isin(['DIVIDEND', 'INTEREST', 'Dividende', 'Zinsen', 'CORPORATE_ACTION'])]
                if not yields.empty:
                    yields['amount'] = pd.to_numeric(yields['amount'].astype(str).replace(',', '.', regex=True), errors='coerce')
                    yearly_profit = yields.groupby('year')['amount'].sum().reset_index()
                    yearly_profit.rename(columns={'amount': 'profit'}, inplace=True)

            if not yearly_profit.empty:
                # Die eToro Logik: Grün für Plus, Rot für Minus
                yearly_profit['color'] = np.where(yearly_profit['profit'] >= 0, '#00C853', '#FF3D00')
                
                # Der moderne Chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=yearly_profit['year'].astype(str),
                    y=yearly_profit['profit'],
                    marker_color=yearly_profit['color'],
                    text=yearly_profit['profit'].apply(lambda x: f"{x:+.2f} €"),
                    textposition='outside', # Text über den Balken
                    textfont=dict(color='white', size=16, family="Arial Black"),
                    cliponaxis=False
                ))
                
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#A0AEC0'),
                    xaxis=dict(showgrid=False, showline=True, linewidth=2, linecolor='#555', tickfont=dict(size=14)),
                    yaxis=dict(showgrid=True, gridcolor='#333', zeroline=True, zerolinecolor='#888', zerolinewidth=2),
                    margin=dict(l=20, r=20, t=40, b=20)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                total_profit = yearly_profit['profit'].sum()
                st.metric(label="Realisierter Gesamtgewinn (All-Time)", value=f"{total_profit:+.2f} €")
            else:
                st.info("Es konnten keine Gewinne oder Dividenden berechnet werden.")

        # === TAB 2: RENDITE (XIRR) ===
        with tab2:
            st.subheader("Dein Interner Zinsfuß (XIRR)")
            
            # Ein- und Auszahlungen filtern (sehr breit gefasst, schließt alles außer Trades aus)
            trade_types = ['BUY', 'SELL', 'DIVIDEND', 'INTEREST', 'CORPORATE_ACTION', 'TAX_OPTIMIZATION', 
                           'Kauf', 'Verkauf', 'Dividende', 'Zinsen', 'Steuer']
            
            transfers = df[~df['type'].isin(trade_types)].copy()
            
            if transfers.empty or len(transfers) < 2:
                st.warning("⚠️ **Hinweis:** Um die XIRR % Rendite zu berechnen, benötigt die App deine Ein- und Auszahlungen. Diese scheinen in dieser spezifischen CSV zu fehlen (Trade Republic lagert diese oft in eine separate 'Cash'-Datei aus).")
            else:
                current_value = st.number_input("Aktueller Depotwert (inkl. Cash) in €:", min_value=0.0, value=730.04, step=10.0)
                
                if st.button("Rendite berechnen"):
                    cfs = []
                    for _, row in transfers.iterrows():
                        if pd.notna(row['amount']):
                            amt = float(str(row['amount']).replace(',', '.'))
                            cfs.append({'date': row['date'], 'amount': -amt})
                            
                    cf_df = pd.DataFrame(cfs)
                    cf_grouped = cf_df.groupby('date')['amount'].sum().reset_index()
                    cf_grouped = cf_grouped.sort_values('date')
                    cf_grouped.loc[len(cf_grouped)] = {'date': pd.to_datetime("today"), 'amount': current_value}
                    
                    def xirr(cashflows):
                        dates = cashflows['date'].values
                        amounts = cashflows['amount'].values
                        t0 = dates[0]
                        years = np.array([(d - t0).astype('timedelta64[D]').astype(int) / 365.25 for d in dates])
                        def npv(rate):
                            return np.sum(amounts / ((1 + rate) ** years))
                        return newton(npv, 0.1)
                    
                    try:
                        irr = xirr(cf_grouped)
                        st.metric(label="Echte Rendite p.a.", value=f"{irr * 100:.2f} %")
                        st.balloons()
                    except:
                        st.error("Berechnung fehlgeschlagen (Mathematischer Fehler).")

        # === TAB 3: DIVIDENDEN DASHBOARD ===
        with tab3:
            st.subheader("Dividenden & Zinsen (Passives Einkommen)")
            yields = df[df['type'].isin(['DIVIDEND', 'INTEREST', 'Dividende', 'Zinsen', 'CORPORATE_ACTION'])].copy()
            
            if not yields.empty:
                yields['amount'] = pd.to_numeric(yields['amount'].astype(str).replace(',', '.', regex=True), errors='coerce')
                yields['month_year'] = yields['date'].dt.to_period('M').dt.start_time
                monthly_yields = yields.groupby('month_year')['amount'].sum().reset_index()
                
                fig_month = px.bar(
                    monthly_yields, 
                    x='month_year', 
                    y='amount',
                    labels={'month_year': 'Monat', 'amount': 'Ausschüttung in €'},
                    color_discrete_sequence=['#3498db']
                )
                fig_month.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#A0AEC0'))
                st.plotly_chart(fig_month, use_container_width=True)
            else:
                st.info("Noch keine Daten vorhanden.")
                
    except Exception as e:
        st.error(f"Ein Fehler ist aufgetreten: {e}")
