
from ortools.sat.python import cp_model
import pandas as pd

# Parametry
num_baths = 4
num_materials = 4
num_manipulators = 2
move_time = 10  # čas pohybu manipulátoru (s)

# Délka ponoření v jednotlivých lázních
bath_durations = {
    1: 15,
    2: 45,
    3: 60,
    4: 30
}

stations = list(range(num_baths + 2))  # 0 = vstup, 1–4 = lázně, 5 = výstup
transfers = [(i, i + 1) for i in range(len(stations) - 1)]

model = cp_model.CpModel()
horizon = sum(bath_durations.values()) * 2 * num_materials
task_vars = {}

# Vygeneruj úkoly: pro každý materiál, převoz mezi stanicemi
for material_id in range(num_materials):
    for step, (from_station, to_station) in enumerate(transfers):
        suffix = f"_{material_id}_{step}"
        transport_start = model.NewIntVar(0, horizon, "trans_start" + suffix)
        transport_end = model.NewIntVar(0, horizon, "trans_end" + suffix)
        transport_interval = {}

        for m in range(num_manipulators):
            bool_var = model.NewBoolVar(f"trans_m{m}_{suffix}")
            interval = model.NewOptionalIntervalVar(transport_start, move_time, transport_end, bool_var, f"trans_int_m{m}_{suffix}")
            transport_interval[m] = (bool_var, interval)

        task_vars[(material_id, step)] = {
            "transport_start": transport_start,
            "transport_end": transport_end,
            "from": from_station,
            "to": to_station,
            "assigned_transport": transport_interval
        }

# Pro každou lázeň vytvoř úkol ponoření (leží v ní bath_duration)
bath_tasks = []
for material_id in range(num_materials):
    for step, (from_station, to_station) in enumerate(transfers):
        if to_station in bath_durations:
            suffix = f"_{material_id}_{step}"
            bath_start = model.NewIntVar(0, horizon, "bath_start" + suffix)
            bath_dur = bath_durations[to_station]
            bath_end = model.NewIntVar(0, horizon, "bath_end" + suffix)
            bath_interval = model.NewIntervalVar(bath_start, bath_dur, bath_end, "bath_interval" + suffix)

            task_vars[(material_id, step)]["bath_start"] = bath_start
            task_vars[(material_id, step)]["bath_end"] = bath_end
            task_vars[(material_id, step)]["bath_interval"] = bath_interval
            task_vars[(material_id, step)]["bath_station"] = to_station
            bath_tasks.append((bath_interval, to_station))

# Omezení: návaznost transport → koupel → další transport
for material_id in range(num_materials):
    for step in range(len(transfers)):
        # návaznost: transport před lázní musí končit před koupelí
        if "bath_start" in task_vars[(material_id, step)]:
            model.Add(task_vars[(material_id, step)]["bath_start"] >= task_vars[(material_id, step)]["transport_end"])

        # návaznost: další transport začíná až po koupeli
        if step + 1 < len(transfers):
            if "bath_end" in task_vars[(material_id, step)]:
                model.Add(task_vars[(material_id, step + 1)]["transport_start"] >= task_vars[(material_id, step)]["bath_end"])
            else:
                model.Add(task_vars[(material_id, step + 1)]["transport_start"] >= task_vars[(material_id, step)]["transport_end"])

# Omezení: každá koupel (lázeň) – max 1 rám současně
for bath_station in bath_durations:
    bath_intervals = []
    for bt, st in bath_tasks:
        if st == bath_station:
            bath_intervals.append(bt)
    model.AddNoOverlap(bath_intervals)

# Omezení: každý transport přiřazen právě jednomu manipulátoru
for key, task in task_vars.items():
    bools = [b for b, _ in task["assigned_transport"].values()]
    model.AddExactlyOne(bools)

# Manipulátorové kolize (NoOverlap)
for m in range(num_manipulators):
    intervals = []
    for task in task_vars.values():
        if m in task["assigned_transport"]:
            intervals.append(task["assigned_transport"][m][1])
    model.AddNoOverlap(intervals)

# Cíl: minimalizace taktu linky
last_ends = [task_vars[(material_id, len(transfers) - 1)]["transport_end"] for material_id in range(num_materials)]
makespan = model.NewIntVar(0, horizon, "makespan")
model.AddMaxEquality(makespan, last_ends)
model.Minimize(makespan)

# Solve
solver = cp_model.CpSolver()
status = solver.Solve(model)

# Výstup
if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
    result = []
    for (material_id, step), task in task_vars.items():
        start = solver.Value(task["transport_start"])
        end = solver.Value(task["transport_end"])
        from_label = "Vstup" if task["from"] == 0 else f"Lázeň {task['from']}" if task["from"] <= num_baths else "Výstup"
        to_label = "Výstup" if task["to"] == num_baths + 1 else f"Lázeň {task['to']}"
        manip_used = None
        for m, (b, _) in task["assigned_transport"].items():
            if solver.BooleanValue(b):
                manip_used = m + 1
        result.append({
            "Materiál": material_id + 1,
            "Krok": f"{from_label} → {to_label}",
            "Začátek (s)": start,
            "Konec (s)": end,
            "Manipulátor": manip_used
        })

    df = pd.DataFrame(result).sort_values(by=["Začátek (s)", "Materiál"])
    print(df.to_string(index=False))
    print(f"\n✅ Minimální takt linky: {solver.Value(makespan)} sekund")
else:
    print("❌ Řešení nebylo nalezeno.")
