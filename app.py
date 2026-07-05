import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import newton
import plotly.graph_objects as go

# Design
st.set_page_config(page_title="Finanz Dashboard", layout="centered")
st.markdown("""<style>.stApp { background-color: #0B0E14; } .stMetric { background-color: #1A1D24; padding: 15px; border-radius: 10px; }</style>""", unsafe_allow_html=True)

st.title("📈 Finanz Dashboard")

uploaded_file = st.file_uploader("Trade Republic CSV hochladen", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()
    df['date'] = pd.to_datetime(df['Datum'], format='mixed', dayfirst=True)
    df['year'] = df['date'].dt.year
    
    # Beträge bereinigen
    def clean(val):
        try: return float(str(val).replace(',', '.'))
        except: return 0.0
        
    df['amount_clean'] = df['Total'].apply(clean)

    # --- TAB 1: ÜBERSICHT ---
    tab1, tab2 = st.tabs(["💶 Gesamt-Übersicht", "📊 Rendite (XIRR)"])
    
    with tab1:
        st.subheader("Performance & Jahres-Erträge")
        current_value = st.number_input("Aktueller Depotwert in €:", value=776.10, step=10.0)
        
        # Inflows (Einzahlungen) vs Outflows (Auszahlungen)
        inflows = df[df['Transaktionen'].isin(['TRANSFER_INBOUND', 'TRANSFER_INSTANT_INBOUND', 'CUSTOMER_INPAYMENT'])]
        outflows = df[df['Transaktionen'].isin(['TRANSFER_INSTANT_OUTBOUND', 'CARD_TRANSACTION'])]
        
        net_invested = abs(inflows['amount_clean'].sum()) - abs(outflows['amount_clean'].sum())
        total_gain = current_value - net_invested
        
        c1, c2 = st.columns(2)
        c1.metric("Netto Investiert", f"{net_invested:.2f} €")
        c2.metric("Gesamter Gewinn", f"{total_gain:+.2f} €")
        
        st.markdown("### Entwicklung (Realisiert)")
        # Hier zeigen wir die realisierten Erträge aus der CSV an (Dividenden/Zinsen)
        realized = df[df['Transaktionen'].isin(['DIVIDEND', 'INTEREST'])].groupby('year')['amount_clean'].sum().reset_index()
        
        fig = go.Figure(go.Bar(
            x=realized['year'].astype(str), y=realized['amount_clean'],
            text=realized['amount_clean'].apply(lambda x: f"{x:+.2f} €"),
            marker_color='#2ECC71', textposition='outside'
        ))
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', 
                          xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True, showgrid=True, gridcolor='#333'),
                          margin=dict(l=0, r=0, t=20, b=0), dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        st.info("Der XIRR berechnet deine Rendite unter Berücksichtigung der Zeitpunkte deiner Einzahlungen.")
        if st.button("Berechnen"):
            cfs = []
            for _, row in inflows.iterrows(): cfs.append({'date': row['date'], 'amount': -abs(row['amount_clean'])})
            for _, row in outflows.iterrows(): cfs.append({'date': row['date'], 'amount': abs(row['amount_clean'])})
            cf_grouped = pd.DataFrame(cfs).groupby('date')['amount'].sum().reset_index()
            cf_grouped.loc[len(cf_grouped)] = {'date': pd.to_datetime("today"), 'amount': current_value}
            
            def xirr(cf):
                dates = (cf['date'] - cf['date'].min()).dt.days / 365.25
                return newton(lambda r: np.sum(cf['amount'] / (1 + r)**dates), 0.1)
            
            st.metric("Echte Rendite p.a.", f"{xirr(cf_grouped)*100:.2f} %")
