import simpy
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

# ----- Simulation Parameters -----
TRAVEL_TIME_PER_UNIT = 1    # time per distance unit
DROP_TIME = 2               # time to drop a rack
DWELL_TIME = 6             # dwell (wait) time in the bath
DRIP_TIME = 3              # time to wait for dripping after picking up

# Positions (units)
ENTRY = 0
BATH5 = 5
BATH10 = 10
BATH15 = 15  # Final bath
EXIT = 17    # Exit position for stacking

# Manipulator home positions.
HOME_M1 = 0
HOME_M2 = 6
HOME_M3 = 11

NUM_RACKS = 3
finished_racks = []

# ----- Global State for Animation -----
# For each rack, store its current position (if in transit, we may record None)
rack_positions = {}
# For each manipulator, store its current position.
manip_positions = {}
# Store which rack is being carried by which manipulator
carried_racks = {}
# Store dwell times for each rack in each bath
dwell_times = {
    'bath5': {},  # {rack_id: start_time}
    'bath10': {},
    'bath15': {}
}
# Track which baths are currently occupied
bath_occupied = {
    'bath5': False,
    'bath10': False,
    'bath15': False
}

# Stack height at EXIT (y-coordinate for each rack)
stack_height = {}

# Add after global variables
SAFETY_DISTANCE = 0  # Minimum distance between manipulators

# Add this after the global variables
simulation_running = True

# Initialize positions.
for i in range(NUM_RACKS):
    rack_positions[i] = ENTRY
manip_positions[1] = HOME_M1
manip_positions[2] = HOME_M2
manip_positions[3] = HOME_M3
carried_racks = {}

# List to store snapshots of the state.
snapshots = []

def record_state(env):
    """Record a snapshot of the current simulation state every 0.1 time units."""
    while len(finished_racks) < NUM_RACKS:
        snapshot = {
            'time': env.now,
            'rack_positions': rack_positions.copy(),
            'manip_positions': manip_positions.copy(),
            'carried_racks': carried_racks.copy(),
            'dwell_times': {
                'bath5': dwell_times['bath5'].copy(),
                'bath10': dwell_times['bath10'].copy(),
                'bath15': dwell_times['bath15'].copy()
            }
        }
        snapshots.append(snapshot)
        yield env.timeout(0.1)  # More frequent snapshots
    # Add final snapshot
    snapshot = {
        'time': env.now,
        'rack_positions': rack_positions.copy(),
        'manip_positions': manip_positions.copy(),
        'carried_racks': carried_racks.copy(),
        'dwell_times': {
            'bath5': dwell_times['bath5'].copy(),
            'bath10': dwell_times['bath10'].copy(),
            'bath15': dwell_times['bath15'].copy()
        }
    }
    snapshots.append(snapshot)

def is_path_clear(start_pos, end_pos, current_manip_id):
    """Check if the path is clear of other manipulators with safety distance."""
    for m_id, pos in manip_positions.items():
        if m_id != current_manip_id:  # Don't check against self
            # Check if any point along the path would be too close to another manipulator
            if start_pos <= pos <= end_pos or end_pos <= pos <= start_pos:
                return False
            # Check safety distance
            if abs(pos - start_pos) < SAFETY_DISTANCE or abs(pos - end_pos) < SAFETY_DISTANCE:
                return False
    return True

def move_manipulator(env, manip_id, start_pos, end_pos, rack=None):
    """Helper function to move manipulator (and rack if carried) smoothly"""
    # Wait until path is clear
    while not is_path_clear(start_pos, end_pos, manip_id):
        yield env.timeout(0.1)
    
    distance = abs(end_pos - start_pos)
    steps = distance * 10  # 10 steps per unit distance
    if steps == 0:
        return
        
    step_size = (end_pos - start_pos) / steps
    current_pos = start_pos
    
    for _ in range(int(steps)):
        current_pos += step_size
        manip_positions[manip_id] = current_pos
        if rack is not None:
            rack_positions[rack] = current_pos
        yield env.timeout(0.1)

# ----- Helper Functions for Bath Operations -----

def dwell_and_store(env, rack, bath_name, store, dwell_time):
    """Helper process to handle dwelling and store transfer."""
    yield env.timeout(dwell_time)
    print(f"Time {env.now}: Rack {rack} finished dwelling in {bath_name}")
    # Keep bath occupied until manipulator picks up the rack
    yield store.put(rack)

def dwell_and_wait(env, rack, bath_name, dwell_time):
    """Helper process to handle dwelling for Bath15."""
    yield env.timeout(dwell_time)
    print(f"Time {env.now}: Rack {rack} finished dwelling in {bath_name}")
    # End bath15 dwell timer
    dwell_times[bath_name].pop(rack, None)

# ----- Processes for Manipulators using Resources for Bath Occupancy -----

def manipulator1(env, entry_store, bath5_store, bath5_resource):
    """
    M1: Picks up a rack from the entry and moves it to Bath5.
    """
    while simulation_running:
        try:
            # Wait for Bath5 to be empty before getting next rack
            while bath_occupied['bath5'] and simulation_running:
                yield env.timeout(0.1)
                
            if not simulation_running:
                break
                
            rack = yield entry_store.get()
            print(f"Time {env.now}: M1 picked up Rack {rack} from ENTRY")
            carried_racks[1] = rack
            
            # Move to Bath5
            yield from move_manipulator(env, 1, HOME_M1, BATH5, rack)
            
            with bath5_resource.request() as req:
                yield req
                # Drop the rack
                yield env.timeout(DROP_TIME)
                print(f"Time {env.now}: M1 dropped Rack {rack} into Bath5")
                rack_positions[rack] = BATH5
                carried_racks.pop(1, None)
                
                # Start dwell timer for Bath5 and mark bath as occupied
                dwell_times['bath5'][rack] = env.now
                bath_occupied['bath5'] = True
                
                # Start a separate process for dwelling and store transfer
                env.process(dwell_and_store(env, rack, 'bath5', bath5_store, DWELL_TIME))
                
            # Return to ENTRY immediately after dropping
            yield from move_manipulator(env, 1, BATH5, HOME_M1)
            print(f"Time {env.now}: M1 returned to ENTRY")
        except simpy.Interrupt:
            break

def manipulator2(env, bath5_store, bath10_store, bath10_resource):
    """
    M2: Picks up a rack from Bath5 store and moves it to Bath10.
    """
    while simulation_running:
        try:
            # Wait for Bath10 to be empty before getting next rack
            while bath_occupied['bath10'] and simulation_running:
                yield env.timeout(0.1)
                
            if not simulation_running:
                break
                
            # Wait for a rack to be dwelling in Bath5 AND M1 to be back at home
            while simulation_running:
                if bath_occupied['bath5']:
                    # Check if M1 is at home position
                    if abs(manip_positions[1] - HOME_M1) < 0.1:
                        # Check if rack has been dwelling for 3 seconds
                        for rack, start_time in dwell_times['bath5'].items():
                            if env.now - start_time >= 3:
                                break
                        else:
                            yield env.timeout(0.1)
                            continue
                        break
                yield env.timeout(0.1)
                
            if not simulation_running:
                break
                
            # Move to Bath5 to pick up rack
            yield from move_manipulator(env, 2, HOME_M2, BATH5)
            
            rack = yield bath5_store.get()
            print(f"Time {env.now}: M2 picked up Rack {rack} from Bath5")
            carried_racks[2] = rack
            dwell_times['bath5'].pop(rack, None)
            
            # Wait for dripping
            print(f"Time {env.now}: Waiting for Rack {rack} to drip at Bath5")
            yield env.timeout(DRIP_TIME)
            bath_occupied['bath5'] = False
            
            # Move to Bath10
            yield from move_manipulator(env, 2, BATH5, BATH10, rack)
            
            with bath10_resource.request() as req:
                yield req
                yield env.timeout(DROP_TIME)
                print(f"Time {env.now}: M2 dropped Rack {rack} into Bath10")
                rack_positions[rack] = BATH10
                carried_racks.pop(2, None)
                
                dwell_times['bath10'][rack] = env.now
                bath_occupied['bath10'] = True
                
                env.process(dwell_and_store(env, rack, 'bath10', bath10_store, DWELL_TIME))
                
            yield from move_manipulator(env, 2, BATH10, HOME_M2)
            print(f"Time {env.now}: M2 returned to home")
        except simpy.Interrupt:
            break

def manipulator3(env, bath10_store):
    """
    M3: Picks up a rack from Bath10 store, moves it to Bath15, then to EXIT.
    """
    while simulation_running:
        try:
            # Wait for Bath15 to be empty before getting next rack
            while bath_occupied['bath15'] and simulation_running:
                yield env.timeout(0.1)
                
            if not simulation_running:
                break
                
            # Wait for a rack to be dwelling in Bath10 AND M2 to be back at home
            while simulation_running:
                if bath_occupied['bath10']:
                    # Check if M2 is at home position
                    if abs(manip_positions[2] - HOME_M2) < 0.1:
                        # Check if rack has been dwelling for 3 seconds
                        for rack, start_time in dwell_times['bath10'].items():
                            if env.now - start_time >= 3:
                                break
                        else:
                            yield env.timeout(0.1)
                            continue
                        break
                yield env.timeout(0.1)
                
            if not simulation_running:
                break
                
            # Move to Bath10
            yield from move_manipulator(env, 3, HOME_M3, BATH10)
            
            rack = yield bath10_store.get()
            print(f"Time {env.now}: M3 picked up Rack {rack} from Bath10")
            carried_racks[3] = rack
            dwell_times['bath10'].pop(rack, None)
            
            # Wait for dripping
            print(f"Time {env.now}: Waiting for Rack {rack} to drip at Bath10")
            yield env.timeout(DRIP_TIME)
            bath_occupied['bath10'] = False
            
            # Move to Bath15
            yield from move_manipulator(env, 3, BATH10, BATH15, rack)
            
            yield env.timeout(DROP_TIME)
            print(f"Time {env.now}: M3 dropped Rack {rack} into Bath15")
            rack_positions[rack] = BATH15
            carried_racks.pop(3, None)
            
            dwell_times['bath15'][rack] = env.now
            bath_occupied['bath15'] = True
            
            # Wait for dwelling to complete
            yield env.process(dwell_and_wait(env, rack, 'bath15', DWELL_TIME))
            
            # Pick up from Bath15 directly (no return to home)
            print(f"Time {env.now}: M3 picked up Rack {rack} from Bath15")
            carried_racks[3] = rack
            
            # Wait for dripping
            print(f"Time {env.now}: Waiting for Rack {rack} to drip at Bath15")
            yield env.timeout(DRIP_TIME)
            bath_occupied['bath15'] = False
            
            # Move directly to EXIT
            yield from move_manipulator(env, 3, BATH15, EXIT, rack)
            
            stack_pos = 1.0 + (len(finished_racks) * 0.3)
            stack_height[rack] = stack_pos
            
            yield env.timeout(DROP_TIME)
            print(f"Time {env.now}: M3 stacked Rack {rack} at EXIT")
            rack_positions[rack] = EXIT
            carried_racks.pop(3, None)
            finished_racks.append(rack)
            
            # Return to home position after completing the cycle
            if simulation_running:
                yield from move_manipulator(env, 3, EXIT, HOME_M3)
                print(f"Time {env.now}: M3 returned to home")
        except simpy.Interrupt:
            break

# ----- Main Simulation Setup -----

def run_simulation():
    # Clear previous snapshots
    global snapshots, simulation_running
    snapshots = []
    simulation_running = True
    
    env = simpy.Environment()
    # Create stores.
    entry_store = simpy.Store(env)
    bath5_store = simpy.Store(env)
    bath10_store = simpy.Store(env)
    # Create resources to enforce one rack per bath.
    bath5_resource = simpy.Resource(env, capacity=1)
    bath10_resource = simpy.Resource(env, capacity=1)
    
    # Put initial racks into entry
    for i in range(NUM_RACKS):
        entry_store.put(i)
        print(f"Time {env.now}: Rack {i} is at ENTRY")
    
    # Start the state recorder.
    env.process(record_state(env))
    # Start manipulator processes.
    env.process(manipulator1(env, entry_store, bath5_store, bath5_resource))
    env.process(manipulator2(env, bath5_store, bath10_store, bath10_resource))
    env.process(manipulator3(env, bath10_store))
    
    # Monitor process: end simulation when all racks are finished.
    def monitor():
        global simulation_running
        while len(finished_racks) < NUM_RACKS:
            yield env.timeout(1)
        print("\nAll racks are finished!")
        # Give some time for final movements to complete
        yield env.timeout(10)
        simulation_running = False
    env.process(monitor())
    
    # Run until all processes are done
    env.run()

def create_animation():
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.set_xlim(-1, 19)
    ax.set_ylim(0, 5)
    ax.set_xlabel("Position")
    ax.set_ylabel("Lane")
    
    # Set x-axis ticks to round numbers with increments of 1
    ax.set_xticks(range(0, 19))  # Creates ticks from 0 to 18
    ax.grid(True)

    # Add bath positions markers
    ax.scatter([ENTRY, BATH5, BATH10, BATH15, EXIT], [1, 1, 1, 1, 1], 
               marker='s', s=100, c='lightgray', alpha=0.3)
    ax.text(ENTRY, 0.5, 'ENTRY')
    ax.text(BATH5, 0.5, 'BATH5')
    ax.text(BATH10, 0.5, 'BATH10')
    ax.text(BATH15, 0.5, 'BATH15')
    ax.text(EXIT, 0.5, 'EXIT')

    # We'll draw racks as blue circles on lane y=1 and manipulators as red squares on lane y=3
    rack_scatter = ax.scatter([], [], s=200, c='blue', label='Racks')
    manip_scatter = ax.scatter([], [], s=300, marker='s', c='red', label='Manipulators')
    ax.legend(loc='upper right')

    # Add status text
    status_text = ax.text(0.02, 0.95, '', transform=ax.transAxes, 
                         bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    completion_text = ax.text(0.02, 0.90, '', transform=ax.transAxes,
                            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))

    # Create rack timer texts
    rack_timer_texts = []
    for _ in range(NUM_RACKS):
        text = ax.text(0, 0, '', ha='center', va='top')
        rack_timer_texts.append(text)

    def init():
        rack_scatter.set_offsets(np.empty((0, 2)))
        manip_scatter.set_offsets(np.empty((0, 2)))
        status_text.set_text('')
        completion_text.set_text('')
        for text in rack_timer_texts:
            text.set_text('')
        return [rack_scatter, manip_scatter, status_text, completion_text] + rack_timer_texts

    def update(frame):
        snap = snapshots[frame]
        current_time = snap['time']
        
        # Prepare rack positions
        rack_xy = []
        for i in range(NUM_RACKS):
            pos = snap['rack_positions'].get(i, ENTRY)
            if pos is None:
                pos = -1
            # If rack is at EXIT, use its stack height
            if pos == EXIT:
                y_pos = stack_height.get(i, 1)
            elif i in snap['carried_racks'].values():
                y_pos = 2  # Height while being carried
            else:
                y_pos = 1  # Normal height
            rack_xy.append([pos, y_pos])
            
            # Update timer text position and content
            if pos != -1:  # Only show timer if rack is visible
                timer_text = ""
                # Check if rack is in any bath (not being carried)
                if i in snap['dwell_times']['bath5']:
                    dwell_time = current_time - snap['dwell_times']['bath5'][i]
                    timer_text = f'{dwell_time:.1f}s'
                elif i in snap['dwell_times']['bath10']:
                    dwell_time = current_time - snap['dwell_times']['bath10'][i]
                    timer_text = f'{dwell_time:.1f}s'
                elif i in snap['dwell_times']['bath15']:
                    dwell_time = current_time - snap['dwell_times']['bath15'][i]
                    timer_text = f'{dwell_time:.1f}s'
                
                if timer_text:  # Only show timer if rack is in a bath
                    rack_timer_texts[i].set_position((pos, y_pos + 0.3))  # Position above the rack
                    rack_timer_texts[i].set_text(timer_text)
                else:
                    rack_timer_texts[i].set_text('')
            else:
                rack_timer_texts[i].set_text('')
        
        # Prepare manipulator positions
        manip_xy = []
        for m in [1, 2, 3]:
            pos = snap['manip_positions'].get(m, HOME_M1 if m==1 else HOME_M2 if m==2 else HOME_M3)
            manip_xy.append([pos, 3])
            
            # If manipulator is carrying a rack, update rack position
            if m in snap['carried_racks']:
                rack_id = snap['carried_racks'][m]
                rack_xy[rack_id] = [pos, 2]  # Show carried racks at y=2
        
        rack_scatter.set_offsets(np.array(rack_xy))
        manip_scatter.set_offsets(np.array(manip_xy))
        
        # Update status texts
        status_text.set_text(f'Time: {current_time:.1f} units')
        finished_count = sum(1 for pos in snap['rack_positions'].values() if pos == EXIT)
        completion_text.set_text(f'Completed: {finished_count}/{NUM_RACKS} racks' + 
                               (' (FINISHED!)' if finished_count == NUM_RACKS else ''))
        
        ax.set_title("Manufacturing Line Simulation")
        return [rack_scatter, manip_scatter, status_text, completion_text] + rack_timer_texts

    # Create the animation with 100ms interval
    anim = FuncAnimation(fig, update, frames=len(snapshots), init_func=init,
                        interval=100, blit=True, repeat=False)
    plt.show()

def main():
    # Clear any previous state
    finished_racks.clear()
    rack_positions.clear()
    manip_positions.clear()
    carried_racks.clear()
    # Clear dwell times for each bath
    for bath in dwell_times.values():
        bath.clear()
    # Reset bath occupied status
    for bath in bath_occupied:
        bath_occupied[bath] = False
    # Initialize positions
    for i in range(NUM_RACKS):
        rack_positions[i] = ENTRY
    manip_positions[1] = HOME_M1
    manip_positions[2] = HOME_M2
    manip_positions[3] = HOME_M3
    
    # Run simulation and create animation
    print("Starting simulation...")
    run_simulation()
    print("\nCreating animation...")
    create_animation()

# Run the main function directly
main()

if __name__ == "__main__":
    pass  # Keep this block for future use
