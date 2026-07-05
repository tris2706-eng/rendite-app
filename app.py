import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import newton
import plotly.express as px

# --- Seiten-Konfiguration ---
st.set_page_config(page_title="Meine Rendite", page_icon="📈", layout="centered")
st.title("📈 Mein Finanz-Dashboard")

# --- Datei-Upload ---
uploaded_file = st.file_uploader("Lade hier deine Trade Republic CSV hoch", type="csv")

if uploaded_file is not None:
    try:
        # CSV robust einlesen (Komma oder Semikolon)
        try:
            df = pd.read_csv(uploaded_file)
            if 'date' not in df.columns and 'Datum' not in df.columns:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, sep=';')
        except:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=';')
            
        # Spaltennamen übersetzen, falls die CSV auf Deutsch ist
        df = df.rename(columns={
            'Datum': 'date', 
            'Transaktionen': 'type',
            'Typ': 'type',
            'Summe': 'amount',
            'Betrag': 'amount'
        })
        
        df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=True)
        
        # --- Daten filtern (Englische & Deutsche Begriffe) ---
        inflows = df[df['type'].isin(['TRANSFER_INBOUND', 'TRANSFER_INSTANT_INBOUND', 'CUSTOMER_INPAYMENT', 'Einzahlung'])]
        outflows = df[df['type'].isin(['TRANSFER_INSTANT_OUTBOUND', 'CARD_TRANSACTION', 'CARD_TRANSACTION_INTERNATIONAL', 'Auszahlung', 'Kartenzahlung'])]
        
        # Erträge (Dividenden & Zinsen)
        yields = df[df['type'].isin(['DIVIDEND', 'INTEREST', 'Dividende', 'Zinsen'])].copy()
        
        if not yields.empty:
            yields['year'] = yields['date'].dt.year
            yields['month_year'] = yields['date'].dt.to_period('M').dt.start_time
        
        # --- Tabs erstellen ---
        tab1, tab2, tab3 = st.tabs(["📊 Rendite (IZF)", "💶 Jahres-Erträge", "💰 Dividenden & Zinsen"])
        
        # === TAB 1: RENDITE (XIRR) ===
        with tab1:
            st.subheader("Dein Interner Zinsfuß (XIRR)")
            current_value = st.number_input("Aktueller Depotwert (inkl. Cash) in €:", min_value=0.0, value=730.04, step=10.0)
            
            if st.button("Rendite berechnen"):
                cfs = []
                for _, row in inflows.iterrows():
                    cfs.append({'date': row['date'], 'amount': -row['amount']})
                for _, row in outflows.iterrows():
                    cfs.append({'date': row['date'], 'amount': -row['amount']})
                    
                cf_df = pd.DataFrame(cfs)
                
                if cf_df.empty:
                    st.warning("Keine Ein- oder Auszahlungen in der CSV gefunden. Lade bitte den kompletten 'Aktivitäten'-Export von Trade Republic herunter.")
                else:
                    cf_grouped = cf_df.groupby('date')['amount'].sum().reset_index()
                    cf_grouped = cf_grouped.sort_values('date')
                    
                    today = pd.to_datetime("today")
                    cf_grouped.loc[len(cf_grouped)] = {'date': today, 'amount': current_value}
                    
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
                        st.success("Berechnung erfolgreich!")
                        st.balloons()
                    except:
                        st.error("Rendite konnte nicht berechnet werden. Prüfe deine Eingaben.")

        # === TAB 2: JAHRES-DIAGRAMM ===
        with tab2:
            st.subheader("Deine Erträge pro Jahr in Euro")
            if not yields.empty:
                yearly_yields = yields.groupby('year')['amount'].sum().reset_index()
                
                fig_year = px.bar(
                    yearly_yields, 
                    x='year', 
                    y='amount', 
                    text='amount',
                    labels={'year': 'Jahr', 'amount': 'Ertrag in €'},
                    color_discrete_sequence=['#2ecc71']
                )
                fig_year.update_traces(texttemplate='%{text:.2f} €', textposition='outside')
                fig_year.update_layout(xaxis=dict(tickmode='linear'))
                st.plotly_chart(fig_year, use_container_width=True)
            else:
                st.info("Noch keine Dividenden oder Zinsen in der Historie gefunden.")

        # === TAB 3: DIVIDENDEN DASHBOARD ===
        with tab3:
            st.subheader("Dein Passives Einkommen")
            if not yields.empty:
                total_passive = yields['amount'].sum()
                st.metric(label="Passives Einkommen Gesamt", value=f"{total_passive:.2f} €")
                
                monthly_yields = yields.groupby('month_year')['amount'].sum().reset_index()
                
                fig_month = px.bar(
                    monthly_yields, 
                    x='month_year', 
                    y='amount',
                    labels={'month_year': 'Monat', 'amount': 'Ausschüttung in €'},
                    color_discrete_sequence=['#3498db']
                )
                fig_month.update_layout(xaxis_title="Monat", yaxis_title="Euro")
                st.plotly_chart(fig_month, use_container_width=True)
            else:
                st.info("Noch keine Daten für das Dashboard vorhanden.")
                
    except Exception as e:
        st.error(f"Ein Fehler ist aufgetreten: {e}")
