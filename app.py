import streamlit as st

# -- Seznam technologií (receptur) pro ukázku --
technologies = [
    "Technologie 1 – Fe + moř",
    "Technologie 2 – Fe bez moř",
    "Technologie 3 – Zn + moř"
]

# -- Defaultní parametry manipulátorů (pro ukázku) --
default_manipulators = {
    "num_manipulators": 3,
    "preejezd_rampa": 100,
    "draha_ponor_zdvih": 1000,
    "ponor_rychlost": 100,
    "zdvih_rychlost": 100,
    "ponor_zpomaleni": 10,
    "rychlost_pred_zalozenim": 10,
    "vyska_zastaveni_okapu": 50,
    "zdvih_zastaveni_okapu": 50
}

# -- Příklad defaultů pro jednotlivé operace a technologie --
NUM_OPERATIONS = 23
default_values = {
    "Technologie 1 – Fe + moř": {
        1:  {"used_in_tech": True,  "double_position": False, "time_min": 100, "time_opt": 150, "time_max": 200, "drip_time": 30, "crossing_distance": 100,  "priority": 1},
        2:  {"used_in_tech": True,  "double_position": False, "time_min": 120, "time_opt": 160, "time_max": 220, "drip_time": 40, "crossing_distance": 1900, "priority": 2},
        3:  {"used_in_tech": True,  "double_position": False, "time_min": 90,  "time_opt": 100, "time_max": 130, "drip_time": 20, "crossing_distance": 150,  "priority": 3},
        # ... atd. pro operace 4–23
    },
    "Technologie 2 – Fe bez moř": {
        1:  {"used_in_tech": True,  "double_position": False, "time_min": 80,  "time_opt": 90,  "time_max": 120, "drip_time": 25, "crossing_distance": 100,  "priority": 1},
        # ... atd.
    },
    "Technologie 3 – Zn + moř": {
        # ... atd.
    }
}

st.title("Konfigurace lakovací linky")

# ----------------------------------------------------------------------
# 1) NASTAVENÍ MANIPULÁTORŮ
# ----------------------------------------------------------------------
with st.expander("Nastavení manipulátorů", expanded=True):
    st.write("Zde můžeš upravit parametry manipulátorů.")

    colA, colB, colC = st.columns(3)
    with colA:
        num_manipulators = st.number_input(
            "Počet manipulátorů", 
            min_value=1, 
            value=default_manipulators["num_manipulators"], 
            step=1
        )
        preejezd_rampa = st.number_input(
            "Přejezd (rampa zpomalení) [mm]", 
            value=default_manipulators["preejezd_rampa"]
        )
        draha_ponor_zdvih = st.number_input(
            "Dráha ponoření/zdvihu [mm]", 
            value=default_manipulators["draha_ponor_zdvih"]
        )

    with colB:
        ponor_rychlost = st.number_input(
            "Ponoření rychlost [mm/s]", 
            value=default_manipulators["ponor_rychlost"]
        )
        zdvih_rychlost = st.number_input(
            "Zdvih rychlost [mm/s]", 
            value=default_manipulators["zdvih_rychlost"]
        )
        ponor_zpomaleni = st.number_input(
            "Ponoření (zpomalení) [mm/s²]", 
            value=default_manipulators["ponor_zpomaleni"]
        )

    with colC:
        rychlost_pred_zalozenim = st.number_input(
            "Rychlost před založením [mm/s]", 
            value=default_manipulators["rychlost_pred_zalozenim"]
        )
        vyska_zastaveni_okapu = st.number_input(
            "Výška zastavení okapu [mm]", 
            value=default_manipulators["vyska_zastaveni_okapu"]
        )
        zdvih_zastaveni_okapu = st.number_input(
            "Zastavení zdvihu v mezipozici pro okap [mm]", 
            value=default_manipulators["zdvih_zastaveni_okapu"]
        )

# ----------------------------------------------------------------------
# 2) VÝBĚR TECHNOLOGIE (RECEPTURY)
# ----------------------------------------------------------------------
selected_tech = st.selectbox("Vyber technologii (recepturu):", technologies)

st.write(f"Zvolená technologie: **{selected_tech}**")

# ----------------------------------------------------------------------
# 3) PARAMETRY 23 OPERACÍ (pro vybranou technologii)
# ----------------------------------------------------------------------
st.subheader("Parametry jednotlivých operací")

operations_data = []

for i in range(1, NUM_OPERATIONS + 1):
    # Načteme defaulty, pokud existují
    if (selected_tech in default_values) and (i in default_values[selected_tech]):
        dv = default_values[selected_tech][i]
    else:
        dv = {
            "used_in_tech": False,
            "double_position": False,
            "time_min": 100,
            "time_opt": 150,
            "time_max": 200,
            "drip_time": 30,
            "crossing_distance": 100,
            "priority": 1
        }

    # Každou operaci dáme do expanderu pro přehlednost
    with st.expander(f"Operace {i}", expanded=(i == 1)):
        # Tři sloupce pro logické rozdělení parametrů
        col1, col2, col3 = st.columns(3)

        with col1:
            used_in_tech = st.checkbox(
                f"Je využita v dané technologii? (Operace {i})",
                value=dv["used_in_tech"],
                key=f"used_in_tech_{i}"
            )
            double_position = st.checkbox(
                f"Zdvojená pozice? (Operace {i})",
                value=dv["double_position"],
                key=f"double_position_{i}"
            )
            priority = st.number_input(
                f"Priorita (Operace {i})",
                value=dv["priority"],
                step=1,
                key=f"priority_{i}"
            )

        with col2:
            time_min = st.number_input(
                f"Čas v lázni (min) (Operace {i})",
                value=dv["time_min"],
                key=f"time_min_{i}"
            )
            time_opt = st.number_input(
                f"Čas v lázni (optimální) (Operace {i})",
                value=dv["time_opt"],
                key=f"time_opt_{i}"
            )
            time_max = st.number_input(
                f"Čas v lázni (max) (Operace {i})",
                value=dv["time_max"],
                key=f"time_max_{i}"
            )

        with col3:
            drip_time = st.number_input(
                f"Čas okapu (Operace {i})",
                value=dv["drip_time"],
                key=f"drip_time_{i}"
            )
            crossing_distance = st.number_input(
                f"Přejezd z předcházející pozice [mm] (Operace {i})",
                value=dv["crossing_distance"],
                key=f"crossing_distance_{i}"
            )

        operations_data.append({
            "operation_index": i,
            "used_in_tech": used_in_tech,
            "double_position": double_position,
            "time_min": time_min,
            "time_opt": time_opt,
            "time_max": time_max,
            "drip_time": drip_time,
            "crossing_distance": crossing_distance,
            "priority": priority
        })

# ----------------------------------------------------------------------
# 4) TLAČÍTKO PRO ULOŽENÍ / ZOBRAZENÍ
# ----------------------------------------------------------------------
if st.button("Uložit / Zobrazit recepturu"):
    st.write("### Parametry manipulátorů")
    manipulator_data = {
        "num_manipulators": num_manipulators,
        "preejezd_rampa": preejezd_rampa,
        "draha_ponor_zdvih": draha_ponor_zdvih,
        "ponor_rychlost": ponor_rychlost,
        "zdvih_rychlost": zdvih_rychlost,
        "ponor_zpomaleni": ponor_zpomaleni,
        "rychlost_pred_zalozenim": rychlost_pred_zalozenim,
        "vyska_zastaveni_okapu": vyska_zastaveni_okapu,
        "zdvih_zastaveni_okapu": zdvih_zastaveni_okapu
    }
    st.json(manipulator_data)

    st.write("### Výsledné parametry operací:")
    st.json(operations_data)
