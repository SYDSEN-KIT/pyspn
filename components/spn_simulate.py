import random
import os

from .spn import *
from .spn_io import *
from .RNGFactory import *

SIMULATION_TIME = 0
SIMULATION_TIME_UNIT = None
VERBOSITY = 0
PROTOCOL = False
SCHEDULE_ITERATOR = 0

def marking(place: Place) -> int:
    return place.n_tokens

def mean_tokens(place: Place) -> float:
    return place.total_tokens/SIMULATION_TIME

def p_not_empty(place: Place) -> float:
    return place.time_non_empty/SIMULATION_TIME

def p_enabled(transition: Transition) -> float:
    return transition.time_enabled/SIMULATION_TIME

def n_firings(transtion: Transition) -> int:
    return transtion.n_times_fired

def throughput(transition: Transition) -> float:
    return transition.n_times_fired/SIMULATION_TIME

def add_tokens(place: Place, n_tokens: int):
    # Assuming `tokens` is a list of token IDs in the Place class

    if PROTOCOL == True:
        # Write the protocol with the ID of the last added token, if any, or 'None'
        write_to_protocol(place.label, SIMULATION_TIME, len(place.tokens))

    # Update statistics calculations using the current_number_of_tokens instead of place.n_tokens
    place.total_tokens += len(place.tokens) * (SIMULATION_TIME - place.time_changed)
    if len(place.tokens) > 0:
        place.time_non_empty += SIMULATION_TIME - place.time_changed

    place.time_changed = SIMULATION_TIME
    place.n_tokens=len(place.tokens)
    place.n_tokens += n_tokens

    # Handle the addition of new tokens
    for _ in range(n_tokens):
        new_token_id = ... # Generate a new token ID here, as per your token generation logic
        place.tokens.append(new_token_id)

    if len(place.tokens) > place.max_tokens:
        place.max_tokens = len(place.tokens)

    # Correctly calling write_to_protocol at the end of the function
    if PROTOCOL:
        write_to_protocol(place.label, SIMULATION_TIME, place.n_tokens)


def sub_tokens(place: Place, n_tokens: int):
    if PROTOCOL == True:
        write_to_protocol(place.label,SIMULATION_TIME,place.n_tokens)
    place.total_tokens += place.n_tokens*(SIMULATION_TIME-place.time_changed)
    if place.n_tokens > 0:
        place.time_non_empty += (SIMULATION_TIME-place.time_changed)
    place.time_changed = SIMULATION_TIME
    place.n_tokens -= n_tokens
    if place.n_tokens < 0:
        print("Negative number of tokens in Place {}".format(place))
    if PROTOCOL == True:
        write_to_protocol(place.label,SIMULATION_TIME,place.n_tokens)

def get_initial_marking(spn: SPN):
    marking = {}
    for place in spn.places:
        place: Place
        # Instead of n_tokens, we store a copy of the current token IDs for each place
        marking[place] = list(place.tokens)  # Assuming `tokens` is a list of token IDs
    return marking


def set_initial_marking(spn: SPN, marking):
    for place in spn.places:
        place:Place
        place.n_tokens = marking[place]

def reset_state(spn: SPN, marking):
    for place in spn.places:
        place:Place
        place.n_tokens = 0
        place.time_changed = 0.0
        place.total_tokens = 0.0
        place.time_non_empty = 0.0

    for transition in spn.transitions:
        transition:Transition
        transition.time_enabled = 0
        transition.n_times_fired = 0
        transition.enabled_at = 0
        transition.enabled = False
        # ADDED: clear any pending parallel instances
        if hasattr(transition, "pt_instances"):
            transition.pt_instances = []

    set_initial_marking(spn, marking)

def complete_statistics(spn: SPN):
    for place in spn.places:
        add_tokens(place, 0)
    for transition in spn.transitions:
        transition: Transition
        if transition.enabled == True:
            transition.time_enabled += SIMULATION_TIME - transition.enabled_at
def _sync(place: Place):
    place.n_tokens = len(place.tokens)

def set_firing_time(transition: Transition):
    """Sets the firing time of a transition based on the transition type and distribution"""
    global SCHEDULE_ITERATOR

    transition.enabled_at = SIMULATION_TIME

    if transition.t_type == "I":
        transition.firing_delay = 0.0
    elif transition.t_type == "T":
        dist = list(transition.distribution.keys())[0]
        parameters = list(transition.distribution[dist].values())
        match dist:
            case "det":
                transition.firing_delay = get_delay("det", parameters[0])
            case "uniform":
                transition.firing_delay = get_delay("uniform", parameters[0], parameters[1])
            case "expon":
                transition.firing_delay = get_delay("expon", parameters[0], parameters[1])
            case "norm":
                transition.firing_delay = get_delay("norm", parameters[0], parameters[1])
            case "lognorm":
                transition.firing_delay = get_delay("lognorm", parameters[0], parameters[1], parameters[2])
            case "triang":
                transition.firing_delay = get_delay("triang", parameters[0], parameters[1], parameters[2])
            case "cauchy":
                transition.firing_delay = get_delay("cauchy", parameters[0], parameters[1])
            case "exponpow":
                transition.firing_delay = get_delay("exponpow", parameters[0], parameters[1], parameters[2])
            case "gamma":
                transition.firing_delay = get_delay("gamma", parameters[0], parameters[1], parameters[2])
            case "weibull_min":
                transition.firing_delay = get_delay("weibull_min", parameters[0], parameters[1], parameters[2])
            case _:
                raise Exception("Distribution undefined for transition {}".format(transition))

    if transition.handicap != 1:
        if transition.handicap_type == "increase":
            transition.firing_delay = round(transition.handicap,2)*transition.firing_delay
        elif transition.handicap_type == "decrease":
            transition.firing_delay = transition.firing_delay/round(transition.handicap,2)

    if transition.t_type == "T" and SIMULATION_TIME_UNIT != None:
        transition.firing_delay = convert_delay(transition.firing_delay, time_unit=transition.time_unit, simulation_time_unit=SIMULATION_TIME_UNIT)

    transition.firing_time = transition.enabled_at + transition.firing_delay


# ADDED: per-instance delay sampler (does NOT touch transition.enabled_at/firing_delay)
def sample_firing_delay(transition: Transition) -> float:
    """Samples a firing delay for a timed transition without modifying its single-clock fields."""
    if transition.t_type != "T":
        return 0.0

    dist = list(transition.distribution.keys())[0]
    parameters = list(transition.distribution[dist].values())
    match dist:
        case "det":
            delay = get_delay("det", parameters[0])
        case "uniform":
            delay = get_delay("uniform", parameters[0], parameters[1])
        case "expon":
            delay = get_delay("expon", parameters[0], parameters[1])
        case "norm":
            delay = get_delay("norm", parameters[0], parameters[1])
        case "lognorm":
            delay = get_delay("lognorm", parameters[0], parameters[1], parameters[2])
        case "triang":
            delay = get_delay("triang", parameters[0], parameters[1], parameters[2])
        case "cauchy":
            delay = get_delay("cauchy", parameters[0], parameters[1])
        case "exponpow":
            delay = get_delay("exponpow", parameters[0], parameters[1], parameters[2])
        case "gamma":
            delay = get_delay("gamma", parameters[0], parameters[1], parameters[2])
        case "weibull_min":
            delay = get_delay("weibull_min", parameters[0], parameters[1], parameters[2])
        case _:
            raise Exception("Distribution undefined for transition {}".format(transition))

    if transition.handicap != 1:
        if transition.handicap_type == "increase":
            delay = round(transition.handicap, 2) * delay
        elif transition.handicap_type == "decrease":
            delay = delay / round(transition.handicap, 2)

    if SIMULATION_TIME_UNIT != None:
        delay = convert_delay(delay, time_unit=transition.time_unit, simulation_time_unit=SIMULATION_TIME_UNIT)

    return delay


def set_reset_time(transition: Transition):
    transition.reset_time = transition.enabled_at + transition.reset_threshold

def convert_delay(delay, time_unit = None, simulation_time_unit = None):
    if time_unit == "d" and simulation_time_unit == "h":
        return delay * 24
    else:
        return delay


def is_enabled(transition: Transition):
    """Checks whether a transition is currently enabled"""
    input_arcs = transition.input_arcs
    inhibitor_arcs = transition.inhibitor_arcs

    # Check each input arc to see if the from_place has any tokens
    for arc in input_arcs:
        if len(arc.from_place.tokens) >= arc.multiplicity:  # Ensure enough tokens are available
            continue
        else:
            return False

    # Assuming the logic for inhibitor arcs remains the same, unless they also use the tokens list
    for arc in inhibitor_arcs:
        if len(arc.from_place.tokens) >= arc.multiplicity:  # Adjusted for token list handling
            return False

    # If the transition has a guard function, its logic might also need adjustment
    if transition.guard_function is not None:
        return transition.guard_function()

    return True


# ADDED: parallel timing support (one timer per reserved token/instance)
def start_parallel_instances(transition: Transition):
    """Start as many independent timer instances as possible for a timed transition.

    Semantics:
      - Each instance reserves its input tokens immediately (they are removed from the input place).
      - Each instance completes independently at (SIMULATION_TIME + sampled_delay) and moves its reserved tokens to outputs.
    """
    if getattr(transition, "parallel_timing", False) != True:
        return
    if transition.t_type != "T":
        return

    if not hasattr(transition, "pt_instances") or transition.pt_instances is None:
        transition.pt_instances = []

    # Minimal implementation: only non-Join/non-Fork with exactly 1 input arc.
    # Minimal implementation: allow Fork (multiple outputs), but still forbid Join (multiple inputs)
    if transition.Join == True:
        raise Exception(
            "parallel_timing is only implemented for transitions with exactly 1 input arc (no Join): {}".format(
                transition.label))
    if len(transition.input_arcs) != 1:
        raise Exception("parallel_timing currently requires exactly 1 input arc: {}".format(transition.label))

    iarc = transition.input_arcs[0]

    # Start as many instances as possible right now.
    while is_enabled(transition) == True:
        if len(iarc.from_place.tokens) < iarc.multiplicity:
            break

        reserved = []
        for _ in range(iarc.multiplicity):
            reserved.append(iarc.from_place.tokens.pop(0))

        delay = sample_firing_delay(transition)
        transition.pt_instances.append({
            "fire_time": SIMULATION_TIME + delay,
            "delay": delay,
            "tokens": reserved,
        })


def fire_parallel_instance(transition: Transition, instance: dict):
    """Complete a single scheduled parallel instance (and REMOVE it!)."""

    # --- CRITICAL: remove the instance so it cannot fire again ---
    if not hasattr(transition, "pt_instances") or transition.pt_instances is None:
        transition.pt_instances = []
    try:
        transition.pt_instances.remove(instance)
    except ValueError:
        # already removed; nothing to do
        return

    tokens = instance.get("tokens", [])

    # If no outputs, just log and finish
    if not transition.output_arcs:
        for tok in tokens:
            write_to_event_log(SIMULATION_TIME, tok, transition.label)
        transition.n_times_fired += 1
        transition.time_enabled += instance.get("delay", 0.0)
        transition.enabled = False
        return

    # FORK semantics:
    # - send the reserved entity token to the FIRST produced output token
    # - create new tokens for the remaining produced outputs
    if transition.Fork == True:
        entity = tokens[0] if tokens else Token()

        used_entity = False
        for oarc in transition.output_arcs:
            for _ in range(oarc.multiplicity):
                if not used_entity:
                    oarc.to_place.tokens.append(entity)
                    write_to_event_log(SIMULATION_TIME, entity, transition.label)
                    used_entity = True
                else:
                    new_tok = Token()
                    oarc.to_place.tokens.append(new_tok)
                    write_to_event_log(SIMULATION_TIME, new_tok, transition.label)
                _sync(oarc.to_place)

    else:
        # Non-fork: move each reserved token to each output
        for tok in tokens:
            for oarc in transition.output_arcs:
                oarc.to_place.tokens.append(tok)
                _sync(oarc.to_place)
            write_to_event_log(SIMULATION_TIME, tok, transition.label)

    transition.n_times_fired += 1
    transition.time_enabled += instance.get("delay", 0.0)
    transition.enabled = False



# CHANGED: update_enabled_flag now schedules parallel instances
def update_enabled_flag(spn: SPN):
    """Updates the enabled flag for all transitions in a SPN.

    If a timed transition has parallel_timing=True, this will also start per-token timer instances.
    """
    transition: Transition
    found_enabled = False

    # 1) Schedule parallel instances first (so they exist even if no transition is enabled)
    for transition in spn.transitions:
        if getattr(transition, "parallel_timing", False) == True and transition.t_type == "T":
            start_parallel_instances(transition)
            # Keep enabled flag as "can start a new instance right now"
            transition.enabled = is_enabled(transition)
            if (hasattr(transition, "pt_instances") and len(transition.pt_instances) > 0) or transition.enabled == True:
                found_enabled = True

    # 2) Original disable logic for non-parallel transitions
    for transition in spn.transitions:
        if getattr(transition, "parallel_timing", False) == True and transition.t_type == "T":
            continue

        if is_enabled(transition) == False:
            #Transition is Race Enable and has just become disabled
            if transition.enabled == True and transition.memory_policy == "AGE":
                transition.disabled_at = SIMULATION_TIME
                transition.clock_active = True

            transition.enabled = False

    # 3) Original enable logic for non-parallel transitions
    for transition in spn.transitions:
        if getattr(transition, "parallel_timing", False) == True and transition.t_type == "T":
            continue

        if is_enabled(transition) == True:
            #Transition has just become enabled
            if transition.enabled == False:
                if transition.clock_active == True:
                    transition.disabled_time += SIMULATION_TIME - transition.disabled_at
                else: set_firing_time(transition)
            transition.enabled = True
            found_enabled = True

    return found_enabled


def fire_transition(transition: Transition):
    """Fires a transition, moving or generating tokens as described."""
    if transition.Fork == True:
        # Consume ONE input token, distribute it to the first produced token,
        # and create fresh tokens for the remaining produced tokens.
        for iarc in transition.input_arcs:
            if PROTOCOL:
                write_to_protocol(iarc.from_place.label, SIMULATION_TIME, len(iarc.from_place.tokens))
                for oarc in transition.output_arcs:
                    write_to_protocol(oarc.to_place.label, SIMULATION_TIME, len(oarc.to_place.tokens))

            if len(iarc.from_place.tokens) < iarc.multiplicity:
                raise RuntimeError(
                    f"Transition {transition.label} fired but input place {iarc.from_place.label} has not enough tokens.")

            # consume required tokens (usually multiplicity=1)
            consumed = []
            for _ in range(iarc.multiplicity):
                consumed.append(iarc.from_place.tokens.pop(0))
            _sync(iarc.from_place)

            # Use the first consumed token as the "entity token"
            entity_token = consumed[0]

        # Produce tokens on outputs
        used_entity = False
        for oarc in transition.output_arcs:
            for idx in range(oarc.multiplicity):
                if not used_entity:
                    oarc.to_place.tokens.append(entity_token)
                    write_to_event_log(SIMULATION_TIME, entity_token, transition.label)
                    used_entity = True
                else:
                    new_token = Token().id
                    oarc.to_place.tokens.append(new_token)
                    write_to_event_log(SIMULATION_TIME, new_token, transition.label)

                if PROTOCOL and idx == oarc.multiplicity - 1:
                    write_to_protocol(oarc.to_place.label, SIMULATION_TIME, len(oarc.to_place.tokens))


    else:
        for iarc in transition.input_arcs:
            if PROTOCOL:  # Log the state before tokens start moving
                write_to_protocol(iarc.from_place.label, SIMULATION_TIME, len(iarc.from_place.tokens))
                for oarc in transition.output_arcs:
                    write_to_protocol(oarc.to_place.label, SIMULATION_TIME,len(oarc.to_place.tokens))
            if transition.Join == True:
                # Collect token IDs for joined logging
                for _ in range(iarc.multiplicity):
                    if iarc.from_place.tokens:
                        token_id = iarc.from_place.tokens.pop(0)
                transition.counter += 1
                if transition.counter == len(transition.input_arcs):  # Log on last iteration
                    transition.counter = 0
                    for oarc in transition.output_arcs:
                        new_token = Token()
                        oarc.to_place.tokens.append(new_token.id)
                        if PROTOCOL:
                            write_to_protocol(iarc.from_place.label, SIMULATION_TIME, len(iarc.from_place.tokens))
            else:
                for index in range(iarc.multiplicity):
                    if iarc.from_place.tokens:
                        token_id = iarc.from_place.tokens.pop(0)
                        for oarc in transition.output_arcs:
                            oarc.to_place.tokens.append(token_id)
                            write_to_event_log(SIMULATION_TIME, token_id, transition.label)
                            if index == iarc.multiplicity - 1 and PROTOCOL:
                                write_to_protocol(iarc.from_place.label, SIMULATION_TIME, len(iarc.from_place.tokens))
                                write_to_protocol(oarc.to_place.label, SIMULATION_TIME, len(oarc.to_place.tokens))
                        if not transition.output_arcs:
                            write_to_event_log(SIMULATION_TIME, token_id, transition.label)
                            write_to_protocol(iarc.from_place.label, SIMULATION_TIME, len(iarc.from_place.tokens))



    if not transition.input_arcs:
            for oarc in transition.output_arcs:
                for index in range(oarc.multiplicity):
                    write_to_protocol(oarc.to_place.label, SIMULATION_TIME, len(oarc.to_place.tokens))
                    new_token = Token()
                    oarc.to_place.tokens.append(new_token.id)
                    write_to_event_log(SIMULATION_TIME, new_token.id, transition.label)
                    if index == oarc.multiplicity - 1 and PROTOCOL:
                        write_to_protocol(oarc.to_place.label, SIMULATION_TIME, len(oarc.to_place.tokens))  # Log after moving
    # Keep n_tokens consistent with the real token list.
    for iarc in transition.input_arcs:
        _sync(iarc.from_place)
    for oarc in transition.output_arcs:
        _sync(oarc.to_place)

    # Updating the firing counter and other transition-related statistics only once
    transition.n_times_fired += 1
    transition.time_enabled += transition.firing_delay
    transition.enabled = False


# CHANGED: returns (transition, time, instance_or_None)
def find_next_firing(spn: SPN):

    total_prob = 0.0
    inc_prob = 0.0
    min_time = 1.0e9
    next_trans = None
    next_instance = None

    # 1) Immediate transitions
    for transition in spn.transitions:
        if transition.enabled == True and transition.t_type == "I":
            total_prob = total_prob + transition.weight

    if total_prob > 0:
        min_time = SIMULATION_TIME
        ran = random.uniform(0,total_prob)
        for transition in spn.transitions:
            if transition.enabled == True and transition.t_type == "I":
                inc_prob = inc_prob + transition.weight
                if inc_prob > ran:
                    return transition, min_time, None

    # 2) Parallel instances
    for transition in spn.transitions:
        if getattr(transition, "parallel_timing", False) == True and transition.t_type == "T":
            if hasattr(transition, "pt_instances") and transition.pt_instances is not None and len(transition.pt_instances) > 0:
                inst = min(transition.pt_instances, key=lambda x: x["fire_time"])
                if inst["fire_time"] < min_time:
                    min_time = inst["fire_time"]
                    next_trans = transition
                    next_instance = inst

    # 3) Regular timed transitions
    for transition in spn.transitions:
        if getattr(transition, "parallel_timing", False) == True and transition.t_type == "T":
            continue

        if transition.enabled == True:
            firing_due_at = transition.enabled_at + transition.firing_delay
            if firing_due_at < min_time:
                min_time = firing_due_at
                next_trans = transition
                next_instance = None

    return next_trans, min_time, next_instance


# CHANGED: fires either a parallel instance or a normal transition
def process_next_event(spn: SPN, max_time):

    global SIMULATION_TIME

    next_transition, min_time, next_instance = find_next_firing(spn)

    if next_transition is None:
        SIMULATION_TIME = max_time
        return False

    if min_time > max_time:
        SIMULATION_TIME = max_time
        return True
    else:
        SIMULATION_TIME = min_time

    if next_instance is not None and getattr(next_transition, "parallel_timing", False) == True:
        fire_parallel_instance(next_transition, next_instance)
    else:
        fire_transition(next_transition)

    if VERBOSITY > 1:
        print("\nTransition {} fires at time {}".format(next_transition.label, round(SIMULATION_TIME,2)))

    if VERBOSITY > 2:
        print_marking(spn,SIMULATION_TIME)

    found_enabled = update_enabled_flag(spn)
    return found_enabled


def simulate(spn: SPN, max_time = 10, start_time = 0, time_unit = None, verbosity = 2, protocol = True, event_log = True):

    global SIMULATION_TIME, SIMULATION_TIME_UNIT, VERBOSITY, PROTOCOL

    VERBOSITY = verbosity

    if VERBOSITY > 0:
        print("Starting simulation...")
        print("Simulation time limit = {}".format(max_time))

    SIMULATION_TIME = 0
    SIMULATION_TIME_UNIT = time_unit
    PROTOCOL = protocol

    if protocol == True:

        try:
            path = os.path.join(os.getcwd(), "../output/protocols/protocol.csv")
            with open(path, "w", newline="") as protocol:
                writer = csv.writer(protocol)
                writer.writerow(["Event","Time","Marking"])
        except:
            with open(os.getcwd() + "/output/protocols/protocol.csv", "w", newline="") as protocol:
                writer = csv.writer(protocol)
                writer.writerow(["Place","Time","Marking"])

    if event_log == True:

        try:
            path = os.path.join(os.getcwd(), "../output/event_logs/event_log.csv")
            with open(path, "w", newline="") as event_log:
                writer = csv.writer(event_log)
                writer.writerow(["Time_Stamp","ID","Event"])
        except:
            with open(os.getcwd() + "/output/event_logs/event_log.csv", "w", newline="") as event_log:
                writer = csv.writer(event_log)
                writer.writerow(["Time_Stamp","ID","Event"])

    initial_marking = get_initial_marking(spn)
    reset_state(spn,initial_marking)

    if VERBOSITY > 1:
        print_marking(spn,SIMULATION_TIME)

    ok = update_enabled_flag(spn)

    while SIMULATION_TIME < max_time and ok == True:
        ok = process_next_event(spn, max_time)
        if verbosity > 2:
            print_state(spn,SIMULATION_TIME)

    if ok == False:
        print("No transitions enabled.")

    if VERBOSITY > 0:
        print("\nTime: {}. Simulation terminated.\n".format(SIMULATION_TIME))

    complete_statistics(spn)

    if VERBOSITY > 0:
        print_statistics(spn,SIMULATION_TIME)
