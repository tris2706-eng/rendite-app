import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import newton
import plotly.graph_objects as go

st.set_page_config(page_title="Finanz Dashboard", layout="centered")
st.title("📈 Finanz Dashboard")

uploaded_file = st.file_uploader("Trade Republic CSV hochladen", type="csv")

if uploaded_file is not None:
    try:
        # Einlesen für das neue Format
        df = pd.read_csv(uploaded_file)
        df['date'] = pd.to_datetime(df['date'])
        df['year'] = df['date'].dt.year
        
        # Bereinigung der Beträge (die sind hier schon Zahlen!)
        # Positive 'amount' bei INBOUND sind Einzahlungen
        # Negative 'amount' bei CARD/OUTBOUND sind Ausgaben/Auszahlungen
        
        # --- TAB 1: ÜBERSICHT ---
        tab1, tab2 = st.tabs(["💶 Gesamt-Übersicht", "📊 Rendite (XIRR)"])
        
        with tab1:
            current_value = st.number_input("Aktueller Depotwert (in €):", value=776.10, step=10.0)
            
            # Nettoberechnung (Einzahlungen minus Auszahlungen/Kartenzahlungen)
            inflows = df[df['type'].isin(['TRANSFER_INBOUND'])].copy()
            outflows = df[df['type'].isin(['TRANSFER_OUTBOUND', 'CARD_TRANSACTION'])].copy()
            
            # Wichtig: Wir summieren die 'amount' Spalte
            net_invested = inflows['amount'].sum() + outflows['amount'].sum()
            total_gain = current_value - net_invested
            
            c1, c2 = st.columns(2)
            c1.metric("Netto Investiert", f"{net_invested:.2f} €")
            c2.metric("Gesamter Gewinn", f"{total_gain:+.2f} €")
            
            st.markdown("### Realisierte Erträge pro Jahr")
            # Wir filtern nach 'DIVIDEND' oder 'INTEREST'
            yields = df[df['type'].isin(['DIVIDEND', 'INTEREST'])].groupby('year')['amount'].sum().reset_index()
            
            fig = go.Figure(go.Bar(x=yields['year'].astype(str), y=yields['amount'], 
                                   marker_color='#2ECC71', text=yields['amount'].apply(lambda x: f"{x:.2f} €"),
                                   textposition='outside'))
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', 
                              xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True), dragmode=False)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        with tab2:
            if st.button("Rendite berechnen"):
                # Alle Cashflows (Ein/Auszahlungen)
                cf = df[df['type'].isin(['TRANSFER_INBOUND', 'TRANSFER_OUTBOUND', 'CARD_TRANSACTION'])].copy()
                cf = cf.groupby('date')['amount'].sum().reset_index()
                cf.loc[len(cf)] = {'date': pd.to_datetime("today"), 'amount': current_value}
                
                dates = (cf['date'] - cf['date'].min()).dt.days / 365.25
                irr = newton(lambda r: np.sum(cf['amount'] / (1 + r)**dates), 0.1)
                st.metric("Echte Rendite p.a.", f"{irr*100:.2f} %")
                
    except Exception as e:
        st.error(f"Fehler: {e}. Prüfe, ob es die richtige Datei ist.")
