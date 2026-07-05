import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import newton
import plotly.graph_objects as go

# Design
st.set_page_config(page_title="Finanz Dashboard", layout="centered")
st.markdown("<style>.stApp { background-color: #0B0E14; } .stMetric { background-color: #1A1D24; padding: 15px; border-radius: 10px; }</style>", unsafe_allow_html=True)

st.title("📈 Finanz Dashboard")

uploaded_file = st.file_uploader("Trade Republic CSV hochladen", type="csv")

if uploaded_file is not None:
    try:
        # Versuche verschiedene Trennzeichen automatisch zu finden
        df = pd.read_csv(uploaded_file, sep=None, engine='python')
        df.columns = df.columns.str.strip()
        
        # Spalten-Erkennung (sucht nach Inhalten, statt festen Namen)
        date_col = next((c for c in df.columns if 'dat' in c.lower()), df.columns[0])
        total_col = next((c for c in df.columns if 'tot' in c.lower() or 'sum' in c.lower() or 'betr' in c.lower()), df.columns[-1])
        type_col = next((c for c in df.columns if 'trans' in c.lower() or 'typ' in c.lower()), df.columns[1])
            
        df['date'] = pd.to_datetime(df[date_col], format='mixed', dayfirst=True)
        df['year'] = df['date'].dt.year
        
        # Beträge bereinigen (mit Fehlerbehandlung für alles, was keine Zahl ist)
        def clean(val):
            try: 
                s = str(val).replace(',', '.')
                return float(s)
            except: return 0.0
            
        df['amount_clean'] = df[total_col].apply(clean)
        
        # --- TAB 1: ÜBERSICHT ---
        tab1, tab2 = st.tabs(["💶 Gesamt-Übersicht", "📊 Rendite (XIRR)"])
        
        with tab1:
            current_value = st.number_input("Aktueller Depotwert in €:", value=776.10, step=10.0)
            
            # Ein/Aus-Zahlungen
            inflows = df[df[type_col].astype(str).str.contains('INBOUND|Einzahlung', na=False)]
            outflows = df[df[type_col].astype(str).str.contains('OUTBOUND|CARD|Auszahlung', na=False)]
            
            net_invested = abs(inflows['amount_clean'].sum()) - abs(outflows['amount_clean'].sum())
            total_gain = current_value - net_invested
            
            c1, c2 = st.columns(2)
            c1.metric("Netto Investiert", f"{net_invested:.2f} €")
            c2.metric("Gesamter Gewinn", f"{total_gain:+.2f} €")
            
            st.markdown("### Erträge (Dividenden/Zinsen)")
            yields = df[df[type_col].astype(str).str.contains('DIVIDEND|INTEREST|Zinsen', na=False)]
            yearly = yields.groupby('year')['amount_clean'].sum().reset_index()
            
            fig = go.Figure(go.Bar(x=yearly['year'].astype(str), y=yearly['amount_clean'], marker_color='#2ECC71'))
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', dragmode=False)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        with tab2:
            if st.button("Rendite berechnen"):
                cfs = []
                for _, row in inflows.iterrows(): cfs.append({'date': row['date'], 'amount': -abs(row['amount_clean'])})
                for _, row in outflows.iterrows(): cfs.append({'date': row['date'], 'amount': abs(row['amount_clean'])})
                cf_grouped = pd.DataFrame(cfs).groupby('date')['amount'].sum().reset_index()
                cf_grouped.loc[len(cf_grouped)] = {'date': pd.to_datetime("today"), 'amount': current_value}
                
                if len(cf_grouped) > 1:
                    dates = (cf_grouped['date'] - cf_grouped['date'].min()).dt.days / 365.25
                    irr = newton(lambda r: np.sum(cf_grouped['amount'] / (1 + r)**dates), 0.1)
                    st.metric("Echte Rendite p.a.", f"{irr*100:.2f} %")
                else:
                    st.error("Zu wenige Daten für eine Rendite-Berechnung.")
    except Exception as e:
        st.error(f"Fehler beim Laden: {e}. Bitte prüfe, ob die CSV die richtigen Daten enthält.")
