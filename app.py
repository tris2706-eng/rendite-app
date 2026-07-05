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
    .stApp { background-color: #0B0E14; }
    h1, h2, h3 { color: #FFFFFF !important; font-family: 'Inter', sans-serif; }
    .stMetric label { color: #8A92A6 !important; font-weight: 600; }
    .stMetric value { color: #FFFFFF !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #0B0E14; }
    .stTabs [data-baseweb="tab"] { background-color: #1A1D24; border-radius: 8px 8px 0 0; padding: 10px 20px; border: 1px solid #2A2D34; border-bottom: none; }
    .stTabs [aria-selected="true"] { background-color: #2ECC71 !important; color: #000000 !important; font-weight: bold; border-color: #2ECC71; }
</style>
""", unsafe_allow_html=True)

st.title("📈 Mein Finanz-Dashboard")

# --- Datei-Upload ---
uploaded_file = st.file_uploader("Trade Republic CSV hochladen", type="csv")

if uploaded_file is not None:
    try:
        # Einlesen & Leerzeichen aus Spaltennamen entfernen
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = df.columns.str.strip()
            if 'date' not in df.columns and 'Datum' not in df.columns:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, sep=';', on_bad_lines='skip')
                df.columns = df.columns.str.strip()
        except:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=';', on_bad_lines='skip')
            df.columns = df.columns.str.strip()

        # Spalten normalisieren
        col_mapping = {
            'Datum': 'date', 'Transaktionen': 'type', 'Typ': 'type',
            'Summe': 'amount', 'Betrag': 'amount', 'Total': 'total',
            'Gewinn/Verlust': 'profit'
        }
        df = df.rename(columns=lambda x: col_mapping.get(x, x))
        
        if 'date' not in df.columns:
            st.error("Fehler: Konnte keine Datums-Spalte finden.")
            st.stop()

        df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=True)
        df['year'] = df['date'].dt.year

        # --- FEHLERBEHEBUNG: Beträge ZUERST umwandeln ---
        def parse_money(val):
            if pd.isna(val): return 0.0
            s = str(val).strip()
            if not s: return 0.0
            is_negative = s.startswith('-')
            if is_negative: s = s[1:]
            
            if s.count('.') > 0 and s.count(',') > 0:
                if s.find('.') < s.find(','):
                    s = s.replace('.', '').replace(',', '.')
                else:
                    s = s.replace(',', '')
            elif s.count(',') == 1:
                s = s.replace(',', '.')
            
            val = float(s)
            return -val if is_negative else val

        # Erstellen der sauberen Zahlenspalte in der kompletten Liste
        if 'amount' in df.columns:
            df['amount_clean'] = df['amount'].apply(parse_money)
        else:
            st.error("Fehler: Konnte keine Spalte für den Betrag (Summe) finden.")
            st.stop()

        if 'profit' in df.columns:
            df['profit_clean'] = df['profit'].apply(parse_money)
        else:
            df['profit_clean'] = 0.0

        # --- DANACH erst die Ein- und Auszahlungen filtern ---
        inflow_keywords = ['TRANSFER_INBOUND', 'TRANSFER_INSTANT_INBOUND', 'CUSTOMER_INPAYMENT', 'Einzahlung']
        outflow_keywords = ['TRANSFER_INSTANT_OUTBOUND', 'CARD_TRANSACTION', 'CARD_TRANSACTION_INTERNATIONAL', 'Auszahlung', 'Kartenzahlung']
        
        inflows = df[df['type'].isin(inflow_keywords)].copy()
        outflows = df[df['type'].isin(outflow_keywords)].copy()

        # --- Tabs ---
        tab1, tab2, tab3 = st.tabs(["💶 Übersicht", "📊 Rendite (IZF)", "💰 Cashflow"])

        # === TAB 1: GESAMTÜBERSICHT ===
        with tab1:
            st.subheader("Dein wahrer Gewinn & Jahres-Erträge")
            
            current_value = st.number_input("Dein Depotwert in der TR App (inkl. Cash) in €:", min_value=0.0, value=730.04, step=10.0)
            
            # Die echte Mathematik: Eingezahlt minus Ausgezahlt
            total_in = abs(sum(inflows['amount_clean']))
            total_out = abs(sum(outflows['amount_clean']))
            
            net_invested = total_in - total_out
            total_profit_euro = current_value - net_invested
            
            colA, colB = st.columns(2)
            colA.metric("Netto Investiert", f"{net_invested:.2f} €")
            colB.metric("Gesamter Gewinn", f"{total_profit_euro:+.2f} €")
            
            st.markdown("---")
            st.markdown("### Erträge nach Jahren")
            
            if 'profit' not in df.columns:
                st.info("💡 Da in dieser CSV-Datei von TR deine Kursgewinne fehlen, zeigt das Diagramm hier unten streng genommen nur deine harten Cash-Ausschüttungen (Dividenden/Zinsen). Dein kompletter All-Time-Gewinn steht oben rechts!")
                yields = df[df['type'].isin(['DIVIDEND', 'INTEREST', 'Dividende', 'Zinsen', 'CORPORATE_ACTION'])].copy()
                yearly_profit = yields.groupby('year')['amount_clean'].sum().reset_index()
            else:
                yearly_profit = df.groupby('year')['profit_clean'].sum().reset_index()

            if not yearly_profit.empty:
                y_col = 'amount_clean' if 'profit' not in df.columns else 'profit_clean'
                yearly_profit['color'] = np.where(yearly_profit[y_col] >= 0, '#00C853', '#FF3D00')
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=yearly_profit['year'].astype(str),
                    y=yearly_profit[y_col],
                    marker_color=yearly_profit['color'],
                    text=yearly_profit[y_col].apply(lambda x: f"{x:+.2f} €"),
                    textposition='outside',
                    textfont=dict(color='white', size=14, family="Inter")
                ))
                
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', dragmode=False,
                    xaxis=dict(showgrid=False, fixedrange=True, tickfont=dict(color='#A0AEC0')),
                    yaxis=dict(showgrid=True, gridcolor='#2A2D34', fixedrange=True, zeroline=True, zerolinecolor='#444', tickfont=dict(color='#A0AEC0')),
                    margin=dict(l=0, r=0, t=20, b=0)
                )
                
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # === TAB 2: RENDITE (XIRR) ===
        with tab2:
            st.subheader("Dein Interner Zinsfuß (XIRR)")
            
            if inflows.empty and outflows.empty:
                st.warning("Keine externen Ein- oder Auszahlungen in dieser CSV gefunden.")
            else:
                if st.button("Rendite berechnen", type="primary"):
                    cfs = []
                    for _, row in inflows.iterrows():
                        cfs.append({'date': row['date'], 'amount': -abs(row['amount_clean'])})
                    for _, row in outflows.iterrows():
                        cfs.append({'date': row['date'], 'amount': abs(row['amount_clean'])})
                        
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
                        st.error("Rendite konnte nicht berechnet werden.")

        # === TAB 3: DIVIDENDEN DASHBOARD ===
        with tab3:
            st.subheader("Dividenden & Zinsen")
            yields = df[df['type'].isin(['DIVIDEND', 'INTEREST', 'Dividende', 'Zinsen', 'CORPORATE_ACTION'])].copy()
            
            if not yields.empty:
                yields['month_year'] = yields['date'].dt.to_period('M').dt.start_time
                monthly_yields = yields.groupby('month_year')['amount_clean'].sum().reset_index()
                
                fig_month = px.bar(
                    monthly_yields, 
                    x='month_year', 
                    y='amount_clean',
                    labels={'month_year': 'Monat', 'amount_clean': 'Ausschüttung in €'},
                    color_discrete_sequence=['#3498db']
                )
                
                fig_month.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', dragmode=False,
                    xaxis=dict(fixedrange=True, tickfont=dict(color='#A0AEC0')),
                    yaxis=dict(fixedrange=True, gridcolor='#2A2D34', tickfont=dict(color='#A0AEC0')),
                    margin=dict(l=0, r=0, t=20, b=0)
                )
                st.plotly_chart(fig_month, use_container_width=True, config={'displayModeBar': False})

    except Exception as e:
        st.error(f"Ein Fehler ist aufgetreten: {e}")
