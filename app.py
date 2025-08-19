# app.py
# Wirtschaftlichkeitsvergleich Heizung: Öl / Gas / Wärmepumpe + PV + Speicher
# Autor: (c) 2025 – Vorlage für Marek / Qrauts
# Lizenz: MIT (bei Bedarf anpassen)

import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px

# ----------------------------
# Default-Annahmen (kannst du unten im UI überschreiben)
# ----------------------------
DEFAULTS = {
    "spez_ertrag_pv": 950,        # kWh/kWp*a
    "heizwert_oel_kwh_l": 10.0,   # kWh je Liter Heizöl EL
    "heizwert_gas_kwh_m3": 10.0,  # kWh je m³ Erdgas (Brennwert ~10-11)
    "eta_oel": 0.85,              # Gesamtwirkungsgrad Öl (Kessel+Verteilung)
    "eta_gas": 0.95,              # Gesamtwirkungsgrad Gas (Brennwert)
    "jaz_wp": 3.2,                # Jahresarbeitszahl der Wärmepumpe (anpassbar)
    "pv_deckung_wp": 0.20,        # Anteil WP-Strom, den PV+Speicher im Jahresmittel deckt
    "strompreis_wp": 0.26,        # €/kWh WP-Tarif (Netz)
    "lcoe_pv": 0.12,              # €/kWh Levelized Cost of Electricity PV (Kostenäquivalenz)
    "preis_oel_eur_l": 1.05,      # €/L Öl (Vorgabe Nutzer)
    "preis_gas_eur_m3": 1.20,     # €/m³ Gas (Vorgabe Nutzer)
    "co2_oel_kg_l": 2.65,         # kg CO2 pro Liter Heizöl
    "co2_gas_kg_m3": 2.00,        # kg CO2 pro m³ Erdgas
    "co2_strom_kg_kwh": 0.35,     # kg CO2 pro kWh Netzstrom (DE-Mix grob)
    "spez_heizwaermebedarf": 110  # kWh/m²*a (Baujahr 1994, teilsaniert – konservativ)
}

st.set_page_config(
    page_title="Heizungs-Wirtschaftlichkeit (Öl/Gas vs. WP+PV+Speicher)",
    page_icon="♨️",
    layout="wide"
)

# ----------------------------
# Hilfsfunktionen
# ----------------------------
def jahres_heizwaermebedarf(kwh_pro_m2a: float, wohnflaeche_m2: float) -> float:
    return kwh_pro_m2a * wohnflaeche_m2

def oel_verbrauch_l(q_h_kwh: float, heizwert_kwh_l: float, eta: float) -> float:
    return q_h_kwh / (eta * heizwert_kwh_l)

def gas_verbrauch_m3(q_h_kwh: float, heizwert_kwh_m3: float, eta: float) -> float:
    return q_h_kwh / (eta * heizwert_kwh_m3)

def wp_strombedarf_kwh(q_h_kwh: float, jaz: float) -> float:
    return q_h_kwh / jaz

def pv_jahreserzeugung_kwh(pv_kwp: float, spez_ertrag: float) -> float:
    return pv_kwp * spez_ertrag

def kosten_wp(strombedarf_wp: float, pv_deck: float, strompreis: float, lcoe_pv: float) -> float:
    pv_kwh = strombedarf_wp * pv_deck
    netz_kwh = max(strombedarf_wp - pv_kwh, 0)
    return pv_kwh * lcoe_pv + netz_kwh * strompreis

def co2_wp(strombedarf_wp: float, pv_deck: float, co2_strom: float) -> float:
    netz_kwh = max(strombedarf_wp * (1 - pv_deck), 0)
    return netz_kwh * co2_strom

def euro(x, nd=0):
    return f"{x:,.{nd}f} €".replace(",", " ").replace(".", ",").replace(" ", ".")

def kwh_fmt(x, nd=0):
    return f"{x:,.{nd}f} kWh".replace(",", " ").replace(".", ",").replace(" ", ".")

def liter_fmt(x, nd=0):
    return f"{x:,.{nd}f} L".replace(",", " ").replace(".", ",").replace(" ", ".")

def m3_fmt(x, nd=0):
    return f"{x:,.{nd}f} m³".replace(",", " ").replace(".", ",").replace(" ", ".")

# ----------------------------
# Sidebar – Projekt / Gebäude / Systeme
# ----------------------------
st.sidebar.header("🧱 Projekt & Objekt")

colA, colB = st.sidebar.columns(2)
with colA:
    proj_nr = st.text_input("Projektnummer", value="PRJ-2025-001")
    we_anz = st.number_input("Wohneinheiten", min_value=1, step=1, value=5)
with colB:
    baujahr = st.number_input("Baujahr", min_value=1850, max_value=2100, step=1, value=1994)
    bauart = st.text_input("Bauart/Standard", value="teilsaniert")

adresse = st.sidebar.text_input("Adresse (Straße, Hausnummer)", value="Musterstraße 1")
plz = st.sidebar.text_input("PLZ", value="79098")
stadt = st.sidebar.text_input("Stadt", value="Freiburg im Breisgau")

wohnflaeche = st.sidebar.number_input("Gesamtwohnfläche (m²)", min_value=1.0, value=350.9, step=1.0, format="%.1f")

st.sidebar.header("🔆 PV & Speicher")
pv_kwp = st.sidebar.number_input("PV-Leistung (kWp)", min_value=0.0, value=24.5, step=0.1, format="%.1f")
speicher_kwh = st.sidebar.number_input("Stromspeicher (kWh)", min_value=0.0, value=40.0, step=1.0, format="%.0f")
spez_ertrag = st.sidebar.number_input("Spezifischer PV-Ertrag (kWh/kWp·a)", min_value=500, max_value=1300, value=DEFAULTS["spez_ertrag_pv"], step=10)

st.sidebar.header("🧊 Wärmepumpe")
wp_kw = st.sidebar.number_input("Wärmepumpen-Leistung (kW)", min_value=1.0, value=13.0, step=0.5, format="%.1f")
jaz_wp = st.sidebar.slider("Jahresarbeitszahl (JAZ)", min_value=2.0, max_value=5.0, value=DEFAULTS["jaz_wp"], step=0.1)
pv_deckung_wp = st.sidebar.slider("PV-Deckung WP (Jahresmittel, %)", 0, 60, int(DEFAULTS["pv_deckung_wp"]*100), step=5) / 100.0

st.sidebar.header("💶 Preise & CO₂")
preis_oel = st.sidebar.number_input("Ölpreis (€/L)", min_value=0.0, value=DEFAULTS["preis_oel_eur_l"], step=0.01, format="%.2f")
preis_gas = st.sidebar.number_input("Gaspreis (€/m³)", min_value=0.0, value=DEFAULTS["preis_gas_eur_m3"], step=0.01, format="%.2f")
strompreis_wp = st.sidebar.number_input("Strompreis WP (€/kWh)", min_value=0.0, value=DEFAULTS["strompreis_wp"], step=0.01, format="%.2f")
lcoe_pv = st.sidebar.number_input("PV-Kostenäquivalenz (€/kWh)", min_value=0.0, value=DEFAULTS["lcoe_pv"], step=0.01, format="%.2f")
co2_strom = st.sidebar.number_input("CO₂ Netzstrom (kg/kWh)", min_value=0.0, value=DEFAULTS["co2_strom_kg_kwh"], step=0.01, format="%.2f")

st.sidebar.header("📐 Energetik")
spez_bedarf = st.sidebar.slider("Spez. Heizwärmebedarf (kWh/m²·a)", min_value=60, max_value=220, value=DEFAULTS["spez_heizwaermebedarf"], step=5)
eta_oel = st.sidebar.slider("η Öl (Gesamtwirkungsgrad)", min_value=0.65, max_value=0.95, value=DEFAULTS["eta_oel"], step=0.01)
eta_gas = st.sidebar.slider("η Gas (Gesamtwirkungsgrad)", min_value=0.80, max_value=1.00, value=DEFAULTS["eta_gas"], step=0.01)

# ----------------------------
# Kopfbereich
# ----------------------------
st.title("Wirtschaftlichkeit Heizung – Öl / Gas vs. Wärmepumpe + PV + Speicher")
st.caption("Eingabemaske für Projekt- und Systemdaten, gefolgt von einem transparenten Variantenvergleich (Kosten & CO₂).")

with st.expander("📄 Projektdaten"):
    st.write(
        f"**Projekt:** {proj_nr}  \n"
        f"**Adresse:** {adresse}, {plz} {stadt}  \n"
        f"**Baujahr:** {baujahr} – **Bauart/Standard:** {bauart}  \n"
        f"**Wohneinheiten:** {we_anz} – **Wohnfläche ges.:** {wohnflaeche:.1f} m²  \n"
        f"**PV:** {pv_kwp:.1f} kWp – **Speicher:** {speicher_kwh:.0f} kWh – **WP:** {wp_kw:.1f} kW"
    )

# ----------------------------
# Berechnungen Basisszenario
# ----------------------------
q_h = jahres_heizwaermebedarf(spez_bedarf, wohnflaeche)  # kWh/a
pv_kwh = pv_jahreserzeugung_kwh(pv_kwp, spez_ertrag)

# Öl
oel_l = oel_verbrauch_l(q_h, DEFAULTS["heizwert_oel_kwh_l"], eta_oel)
oel_kosten = oel_l * preis_oel
oel_co2 = oel_l * DEFAULTS["co2_oel_kg_l"]

# Gas
gas_m3 = gas_verbrauch_m3(q_h, DEFAULTS["heizwert_gas_kwh_m3"], eta_gas)
gas_kosten = gas_m3 * preis_gas
gas_co2 = gas_m3 * DEFAULTS["co2_gas_kg_m3"]

# WP
wp_kwh = wp_strombedarf_kwh(q_h, jaz_wp)
wp_kosten = kosten_wp(wp_kwh, pv_deckung_wp, strompreis_wp, lcoe_pv)
wp_co2 = co2_wp(wp_kwh, pv_deckung_wp, co2_strom)

# Zusatzkennzahlen
vollbenutzungsstunden_wp = q_h / max(wp_kw, 0.001)

# ----------------------------
# Ausgabe: KPIs
# ----------------------------
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Jahres-Heizwärmebedarf", kwh_fmt(q_h, 0))
kpi2.metric("PV-Erzeugung (Schätzung)", kwh_fmt(pv_kwh, 0))
kpi3.metric("WP-Vollbenutzungsstunden", f"{vollbenutzungsstunden_wp:,.0f} h".replace(",", "."))
kpi4.metric("PV-Deckung WP (Jahr)", f"{int(pv_deckung_wp*100)} %")

st.markdown("---")

# ----------------------------
# Vergleichstabelle
# ----------------------------
df = pd.DataFrame([
    {
        "Variante": "Öl (Bestand)",
        "Energiebedarf/Träger": liter_fmt(oel_l, 0),
        "Energiekosten/Jahr": oel_kosten,
        "CO₂-Emissionen/Jahr (kg)": oel_co2
    },
    {
        "Variante": "Gas (Brennwert)",
        "Energiebedarf/Träger": m3_fmt(gas_m3, 0),
        "Energiekosten/Jahr": gas_kosten,
        "CO₂-Emissionen/Jahr (kg)": gas_co2
    },
    {
        "Variante": "Wärmepumpe + PV + Speicher",
        "Energiebedarf/Träger": kwh_fmt(wp_kwh, 0),
        "Energiekosten/Jahr": wp_kosten,
        "CO₂-Emissionen/Jahr (kg)": wp_co2
    }
])

st.subheader("Variantenvergleich – jährliche Energiekosten & Emissionen")
st.dataframe(
    df.assign(**{
        "Energiekosten/Jahr (fmt)": df["Energiekosten/Jahr"].apply(lambda x: euro(x, 0)),
        "CO₂-Emissionen/Jahr (t)": df["CO₂-Emissionen/Jahr (kg)"].apply(lambda x: x/1000.0)
    })[["Variante", "Energiebedarf/Träger", "Energiekosten/Jahr (fmt)", "CO₂-Emissionen/Jahr (t)"]],
    use_container_width=True,
    hide_index=True
)

# ----------------------------
# Diagramme
# ----------------------------
col1, col2 = st.columns(2)

with col1:
    chart_cost = px.bar(
        df,
        x="Variante",
        y="Energiekosten/Jahr",
        title="Jährliche Energiekosten (€/a)",
        text=df["Energiekosten/Jahr"].apply(lambda v: euro(v, 0))
    )
    chart_cost.update_traces(textposition="outside")
    chart_cost.update_layout(yaxis_title="€ / Jahr", xaxis_title="")
    st.plotly_chart(chart_cost, use_container_width=True)

with col2:
    df_co2 = df.copy()
    df_co2["CO₂ (t/a)"] = df_co2["CO₂-Emissionen/Jahr (kg)"] / 1000.0
    chart_co2 = px.bar(
        df_co2,
        x="Variante",
        y="CO₂ (t/a)",
        title="Jährliche CO₂-Emissionen (t/a)",
        text=df_co2["CO₂ (t/a)"].map(lambda v: f"{v:,.2f}".replace(",", "."))
    )
    chart_co2.update_traces(textposition="outside")
    chart_co2.update_layout(yaxis_title="t / Jahr", xaxis_title="")
    st.plotly_chart(chart_co2, use_container_width=True)

st.markdown("---")

# ----------------------------
# Sensitivitäten (optional)
# ----------------------------
st.subheader("Sensitivitäten")
colS1, colS2 = st.columns(2)
with colS1:
    sens_bedarf = st.slider("Sensitivität: spez. Heizwärmebedarf (kWh/m²·a)", 60, 220, DEFAULTS["spez_heizwaermebedarf"], 5)
with colS2:
    sens_jaz = st.slider("Sensitivität: JAZ Wärmepumpe", 2.0, 5.0, DEFAULTS["jaz_wp"], 0.1)

q_h_sens = jahres_heizwaermebedarf(sens_bedarf, wohnflaeche)
oel_l_sens = oel_verbrauch_l(q_h_sens, DEFAULTS["heizwert_oel_kwh_l"], eta_oel)
gas_m3_sens = gas_verbrauch_m3(q_h_sens, DEFAULTS["heizwert_gas_kwh_m3"], eta_gas)
wp_kwh_sens = wp_strombedarf_kwh(q_h_sens, sens_jaz)

wp_kosten_sens = kosten_wp(wp_kwh_sens, pv_deckung_wp, strompreis_wp, lcoe_pv)
oel_kosten_sens = oel_l_sens * preis_oel
gas_kosten_sens = gas_m3_sens * preis_gas

df_sens = pd.DataFrame({
    "Variante": ["Öl", "Gas", "WP+PV+Speicher"],
    "Kosten (€/a)": [oel_kosten_sens, gas_kosten_sens, wp_kosten_sens]
})

st.dataframe(df_sens.assign(**{"Kosten (fmt)": df_sens["Kosten (€/a)"].apply(lambda x: euro(x, 0))})[["Variante", "Kosten (fmt)"]], hide_index=True, use_container_width=True)

st.info(
    "💡 **Hinweis**: Die PV-Deckung wirkt überwiegend in Übergangszeit/Sommer. Trotz Speicher ist die Winterdeckung begrenzt. "
    "Eine Optimierung der Vorlauftemperatur, Hydraulikabgleich und intelligente WP-Fahrpläne können die JAZ deutlich verbessern."
)

# ----------------------------
# Downloadbare Ergebnisse
# ----------------------------
st.subheader("Export")
df_export = pd.DataFrame({
    "Projekt": [proj_nr],
    "Adresse": [f"{adresse}, {plz} {stadt}"],
    "Baujahr": [baujahr],
    "Bauart": [bauart],
    "Wohneinheiten": [we_anz],
    "Wohnfläche_m2": [wohnflaeche],
    "PV_kWp": [pv_kwp],
    "Speicher_kWh": [speicher_kwh],
    "WP_kW": [wp_kw],
    "Spez_Heizwaermebedarf_kWh_m2a": [spez_bedarf],
    "QH_kWh_a": [q_h],
    "PV_kWh_a": [pv_kwh],
    "Öl_Liter_a": [oel_l],
    "Öl_Kosten_EUR_a": [oel_kosten],
    "Gas_m3_a": [gas_m3],
    "Gas_Kosten_EUR_a": [gas_kosten],
    "WP_Strom_kWh_a": [wp_kwh],
    "WP_Kosten_EUR_a": [wp_kosten],
    "CO2_Oel_kg_a": [oel_co2],
    "CO2_Gas_kg_a": [gas_co2],
    "CO2_WP_kg_a": [wp_co2],
})

st.download_button(
    label="📥 Ergebnisse als CSV herunterladen",
    data=df_export.to_csv(index=False).encode("utf-8"),
    file_name=f"heizungsvergleich_{proj_nr}.csv",
    mime="text/csv"
)

# ----------------------------
# Fußzeile
# ----------------------------
st.caption("© 2025 – Qrauts / Demo. Diese App liefert überschlägige Wirtschaftlichkeitsindikationen auf Basis transparenter Annahmen.")
